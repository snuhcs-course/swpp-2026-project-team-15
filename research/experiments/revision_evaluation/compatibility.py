# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Canonical immutable run identities and read-only resume compatibility checks."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

from app.dishes import prompts

from .contract import SUMMARY_SCHEMA, CodeIdentity, InputIdentities, RunMetadata
from .planning import ExecutionPlan

REPO_ROOT = Path(__file__).resolve().parents[3]


def _digest(value: object) -> str:
    """Hash canonical finite JSON; dictionary order is irrelevant but list order is not."""
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def capture_input_identities(
    plan: ExecutionPlan, manifest_path: Path, recipes_path: Path
) -> InputIdentities:
    """Hash current snapshots and exact local fixture/template bytes without rebuilding policy.

    The prompt identity covers the production template module (including re-ask
    wording); schema identity uses the served Revision response schema. File paths
    are not identities: identical fixture bytes can be moved without changing a run.
    """
    return InputIdentities(
        prompt_sha256=hashlib.sha256(Path(prompts.__file__).read_bytes()).hexdigest(),
        response_schema_sha256=_digest(prompts.REVISE_SCHEMA),
        input_sha256={
            case_id: _digest(value.model_dump())
            for case_id, value in plan.inputs.items()
        },
        fixture_sha256={
            "manifest": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "recipes": hashlib.sha256(recipes_path.read_bytes()).hexdigest(),
        },
    )


def capture_code_identity(root: Path = REPO_ROOT) -> CodeIdentity:
    """Read commit and hash effective working-tree bytes, without writing Git objects/index.

    HEAD plus a dirty flag cannot distinguish two different dirty checkouts. Build
    a Git-format tree digest from tracked and nonignored untracked files instead.
    Raw working bytes deliberately bypass clean filters/line-ending conversion, so
    a conversion also invalidates compatibility. Ignored run outputs are excluded.
    Unmerged entries, submodules and unreadable files fail closed.
    """
    root = root.resolve()

    def git(*args: str) -> bytes:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(root), *args],
            check=True,
            capture_output=True,
            timeout=30,
        )
        if result.stderr:
            raise ValueError("could not capture complete code identity")
        return result.stdout

    try:
        if Path(git("rev-parse", "--show-toplevel").decode().strip()).resolve() != root:
            raise ValueError("code identity requires the repository root")
        algorithm = git("rev-parse", "--show-object-format").decode().strip()
        if algorithm not in ("sha1", "sha256"):
            raise ValueError("unsupported Git object format")

        def object_id(kind: bytes, content: bytes) -> bytes:
            return hashlib.new(
                algorithm, kind + b" " + str(len(content)).encode() + b"\0" + content
            ).digest()

        modes = {}
        for entry in git("ls-files", "--stage", "-z").split(b"\0"):
            if not entry:
                continue
            header, name = entry.split(b"\t", 1)
            mode, _, stage = header.split()
            if stage != b"0" or mode == b"160000":
                raise ValueError("unsupported Git index entry")
            modes[name] = mode
        paths = git(
            "ls-files", "--cached", "--others", "--exclude-standard", "-z"
        ).split(b"\0")
        tree = {}
        for name in sorted(set(paths) - {b""}):
            path = root / os.fsdecode(name)
            if path.is_symlink():
                mode, content = b"120000", os.fsencode(os.readlink(path))
            elif path.is_file():
                mode = modes.get(name, b"100644")
                if os.name != "nt":
                    mode = b"100755" if path.stat().st_mode & 0o111 else b"100644"
                content = path.read_bytes()
            elif not path.exists() and name in modes:
                continue  # A tracked deletion is part of the effective tree.
            else:
                raise ValueError("could not read effective source file")
            node = tree
            parts = name.split(b"/")
            for part in parts[:-1]:
                node = node.setdefault(part, {})
            node[parts[-1]] = (mode, object_id(b"blob", content))

        def tree_id(node: dict) -> bytes:
            entries = []
            for name, value in node.items():
                directory = isinstance(value, dict)
                mode, digest = (b"40000", tree_id(value)) if directory else value
                entries.append(
                    (
                        name + (b"/" if directory else b""),
                        mode + b" " + name + b"\0" + digest,
                    )
                )
            return object_id(b"tree", b"".join(entry for _, entry in sorted(entries)))

        return CodeIdentity(
            commit=git("rev-parse", "HEAD").decode().strip(),
            tree=tree_id(tree).hex(),
            dirty=bool(git("status", "--porcelain=v1", "--untracked-files=all")),
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        raise ValueError("could not capture complete code identity") from None


def compatibility_fingerprint(metadata: RunMetadata) -> str:
    """Hash immutable settings only; progress, refs, counters and timestamps may evolve."""
    value = RunMetadata.model_validate(metadata.model_dump())
    return _digest(
        {
            "definition": "revision-evaluation-compatibility/v1",
            "artifact_schemas": [
                value.artifact_schema,
                value.observation_schema,
                SUMMARY_SCHEMA,
            ],
            "plan": [[unit.case_id, unit.repetition] for unit in value.plan],
            "identities": value.identities.model_dump(),
            "effective_assumed_staples": value.effective_assumed_staples,
            "model": value.model,
            "pricing": value.pricing,
            "code_identity": value.code_identity.model_dump(),
            "http_attempt_maximum": value.http_attempt_budget.maximum,
        }
    )


def load_resume_metadata(root: Path) -> RunMetadata:
    """Read an existing index without opening a writable RunStore or following an external link."""
    root = root.resolve()
    path = root / "metadata.json"
    if path.resolve().parent != root:
        raise ValueError("resume metadata must stay inside the run")
    return RunMetadata.model_validate_json(path.read_text(encoding="utf-8"))


def validate_resume(
    stored: RunMetadata,
    plan: ExecutionPlan,
    identities: InputIdentities,
    code_identity: CodeIdentity,
    *,
    model: dict | None = None,
    pricing: dict | None = None,
) -> None:
    """Compare current configuration with the original fingerprint, without modifying artifacts.

    Absent overrides retain stored model/pricing settings as the requested settings.
    First recompute stored immutable data to catch stale/tampered metadata, then
    recompute with current inputs/code. Completed runs cannot be resumed.
    """
    if (
        stored.state == "completed"
        or compatibility_fingerprint(stored) != stored.compatibility_fingerprint
    ):
        raise ValueError("resume compatibility check failed")
    current = stored.model_copy(deep=True)
    current.plan = [unit.model_copy(deep=True) for unit in plan.units]
    current.effective_assumed_staples = list(plan.effective_assumed_staples)
    current.identities = identities.model_copy(deep=True)
    current.code_identity = code_identity.model_copy(deep=True)
    if model is not None:
        current.model = model
    if pricing is not None:
        current.pricing = pricing
    if compatibility_fingerprint(current) != stored.compatibility_fingerprint:
        raise ValueError("resume compatibility check failed")
