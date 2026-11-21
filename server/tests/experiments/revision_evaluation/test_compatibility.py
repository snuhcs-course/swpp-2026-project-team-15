# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Offline fingerprint tests covering immutable settings and dirty source identity."""

import json
import subprocess
from copy import deepcopy

import pytest
from experiments.revision_evaluation.compatibility import (
    capture_code_identity,
    capture_input_identities,
    compatibility_fingerprint,
    load_resume_metadata,
    validate_resume,
)
from experiments.revision_evaluation.contract import CodeIdentity, RunMetadata
from experiments.revision_evaluation.generate_contract import fixture_metadata, fixture_observations
from experiments.revision_evaluation.planning import (
    FROZEN_MANIFEST,
    ExecutionPlan,
    build_plan,
    load_manifest,
)
from experiments.revision_evaluation.staples import StaplesSnapshot

from app.dishes.recipes import RecipeStore


def compatible_run():
    """Build an interrupted test run using actual frozen input/template hashes."""
    snapshot = StaplesSnapshot()
    plan = build_plan(
        load_manifest(),
        ["R02a", "R01a"],
        2,
        recipes=RecipeStore.load(FROZEN_MANIFEST.with_name("fixtures.json")),
        catalog=snapshot.catalog(),
        snapshot=snapshot,
    )
    identities = capture_input_identities(
        plan, FROZEN_MANIFEST, FROZEN_MANIFEST.with_name("fixtures.json")
    )
    code = CodeIdentity(commit="a" * 40, tree="b" * 40, dirty=False)
    metadata = RunMetadata.model_validate(fixture_metadata(fixture_observations()))
    metadata.state = "interrupted"
    metadata.plan = [unit.model_copy(deep=True) for unit in plan.units]
    metadata.identities = identities.model_copy(deep=True)
    metadata.code_identity = code.model_copy(deep=True)
    metadata.effective_assumed_staples = list(plan.effective_assumed_staples)
    metadata.http_attempt_budget.consumed = 0
    metadata.http_attempt_budget.remaining = metadata.http_attempt_budget.maximum
    metadata.resume_history = []
    metadata.compatibility_fingerprint = compatibility_fingerprint(metadata)
    return metadata, plan, identities, code


def test_compatible_check_and_canonical_hash_do_not_mutate_settings():
    metadata, plan, identities, code = compatible_run()
    before = deepcopy((metadata, plan, identities, code))
    validate_resume(metadata, plan, identities, code)
    raw = json.loads(
        metadata.model_dump_json(), object_pairs_hook=lambda pairs: dict(reversed(pairs))
    )
    assert (
        compatibility_fingerprint(RunMetadata.model_validate(raw))
        == metadata.compatibility_fingerprint
    )
    assert (metadata, plan, identities, code) == before


@pytest.mark.parametrize(
    "change",
    [
        "plan_order",
        "repetitions",
        "staples_order",
        "input",
        "manifest",
        "recipes",
        "prompt",
        "schema",
        "commit",
        "tree",
        "dirty",
        "model",
        "temperature",
        "pricing",
        "budget_maximum",
        "artifact_schema",
        "observation_schema",
        "stored_tampering",
        "completed",
    ],
)
def test_every_immutable_component_mismatch_is_rejected(change):
    metadata, plan, identities, code = compatible_run()
    overrides = {}
    if change == "plan_order":
        plan = ExecutionPlan(
            tuple(reversed(plan.units)), plan.inputs, plan.effective_assumed_staples
        )
    elif change == "repetitions":
        plan = ExecutionPlan(plan.units[:-1], plan.inputs, plan.effective_assumed_staples)
    elif change == "staples_order":
        plan = ExecutionPlan(
            plan.units, plan.inputs, tuple(reversed(plan.effective_assumed_staples))
        )
    elif change == "input":
        identities.input_sha256["R01a"] = "0" * 64
    elif change in ("manifest", "recipes"):
        identities.fixture_sha256[change] = "0" * 64
    elif change == "prompt":
        identities.prompt_sha256 = "0" * 64
    elif change == "schema":
        identities.response_schema_sha256 = "0" * 64
    elif change in ("commit", "tree"):
        setattr(code, change, "c" * 40)
    elif change == "dirty":
        code.dirty = True
    elif change in ("model", "temperature"):
        overrides["model"] = {
            **metadata.model,
            "id" if change == "model" else "temperature": "different",
        }
    elif change == "pricing":
        overrides["pricing"] = {**metadata.pricing, "input_per_million_usd": 99}
    elif change == "budget_maximum":
        metadata.http_attempt_budget.maximum += 1
        metadata.http_attempt_budget.remaining += 1
    elif change in ("artifact_schema", "observation_schema"):
        setattr(metadata, change, "unsupported/v2")
    elif change == "stored_tampering":
        metadata.model["id"] = "changed after fingerprint"
    else:
        metadata.state = "completed"
    before = deepcopy((metadata, plan, identities, code))
    with pytest.raises(ValueError):
        validate_resume(metadata, plan, identities, code, **overrides)
    assert (metadata, plan, identities, code) == before


def test_progress_does_not_change_the_immutable_fingerprint():
    metadata, _, _, _ = compatible_run()
    original = metadata.compatibility_fingerprint
    metadata.updated_at = "later"
    metadata.resume_history.append({"resumed_at": "later"})
    metadata.http_attempt_budget.consumed = 1
    metadata.http_attempt_budget.remaining -= 1
    metadata.plan[0].state = "incomplete"
    metadata.plan[0].observation_refs = ["observations/attempt-001.json"]
    assert compatibility_fingerprint(metadata) == original


def test_changed_snapshot_and_fixture_bytes_change_input_identities(tmp_path):
    _, plan, _, _ = compatible_run()
    manifest = tmp_path / "cases.json"
    recipes = tmp_path / "recipes.json"
    manifest.write_bytes(FROZEN_MANIFEST.read_bytes())
    recipes.write_bytes(FROZEN_MANIFEST.with_name("fixtures.json").read_bytes())
    initial = capture_input_identities(plan, manifest, recipes)
    manifest.write_bytes(manifest.read_bytes() + b"\n")
    assert (
        capture_input_identities(plan, manifest, recipes).fixture_sha256 != initial.fixture_sha256
    )
    plan.inputs["R01a"].supplied_ingredients.append("changed fridge")
    assert capture_input_identities(plan, manifest, recipes).input_sha256 != initial.input_sha256


def _git(root, *args):
    """Run only local Git operations inside a disposable test repository."""
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True
    ).stdout.strip()


def test_code_identity_hashes_dirty_and_untracked_content_without_git_writes(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "core.autocrlf", "false")
    source = tmp_path / "source.py"
    source.write_bytes(b"original\n")
    (tmp_path / ".gitignore").write_bytes(b"output/\n")
    # Git sorts a directory as name + '/', which differs from plain name order.
    (tmp_path / "same").mkdir()
    (tmp_path / "same" / "nested.py").write_bytes(b"nested\n")
    (tmp_path / "same.py").write_bytes(b"sibling\n")
    _git(tmp_path, "add", ".")
    _git(
        tmp_path,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.test",
        "commit",
        "-qm",
        "fixture",
    )

    def git_bytes():
        return {
            path.relative_to(tmp_path): path.read_bytes()
            for path in (tmp_path / ".git").rglob("*")
            if path.is_file()
        }

    before = git_bytes()
    clean = capture_code_identity(tmp_path)
    assert not clean.dirty
    assert clean.tree == _git(tmp_path, "rev-parse", "HEAD^{tree}").decode()
    assert git_bytes() == before
    source.write_bytes(b"first dirty version\n")
    first = capture_code_identity(tmp_path)
    source.write_bytes(b"second dirty version\n")
    second = capture_code_identity(tmp_path)
    assert first.dirty and second.dirty
    assert first.commit == second.commit == clean.commit
    assert len({clean.tree, first.tree, second.tree}) == 3
    extra = tmp_path / "untracked.py"
    extra.write_bytes(b"untracked\n")
    untracked = capture_code_identity(tmp_path)
    assert untracked.tree != second.tree
    (tmp_path / "output").mkdir()
    (tmp_path / "output" / "metadata.json").write_bytes(b"ignored run output")
    assert capture_code_identity(tmp_path) == untracked
    source.unlink()
    assert capture_code_identity(tmp_path).tree != untracked.tree
    assert git_bytes() == before


def test_unreadable_code_identity_fails_with_fixed_message(tmp_path):
    with pytest.raises(ValueError, match="^could not capture complete code identity$"):
        capture_code_identity(tmp_path)


def test_missing_or_unsupported_resume_metadata_is_read_only(tmp_path):
    with pytest.raises(OSError):
        load_resume_metadata(tmp_path)
    assert not list(tmp_path.iterdir())
    path = tmp_path / "metadata.json"
    path.write_text('{"artifact_schema":"unsupported/v2"}', encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(ValueError):
        load_resume_metadata(tmp_path)
    assert path.read_bytes() == before
