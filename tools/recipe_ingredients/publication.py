# AI-generated CSV preservation and publication with Codex, 2026-11-15; reviewed by Soohyun An
"""Publish validated local preparation files with explicit, non-overwriting backups."""

import csv
import hashlib
import io
import json
import os
import tempfile
from pathlib import Path

from recipe_ingredients.mapping import _catalog
from recipe_ingredients.normalization import _validate, build_documents

CSV_NAMES = (
    "Ingredient.csv",
    "IngredientPresentation.csv",
    "IngredientAllergen.csv",
    "RecipeIngredient.csv",
)


class PublicationError(RuntimeError):
    """Report a failed phase and surviving files; no automatic rollback is attempted."""


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _json_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _unchanged(expected: dict[Path, bytes]) -> None:
    """Detect concurrent edits before snapshots or publication are trusted."""
    for path, content in expected.items():
        if path.read_bytes() != content:
            raise ValueError(f"Input changed during execution: {path}")


def _write_new(path: Path, content: bytes) -> None:
    """Create one file exclusively, preserving existing destinations even on failure."""
    with path.open("xb") as handle:
        handle.write(content)
    if path.read_bytes() != content:
        raise OSError(f"Written bytes do not match: {path}")


def _prepare(
    documents: dict, snapshots: dict, selected_path: Path, decisions_path: Path, catalog_path: Path
) -> bytes:
    """Validate generated documents and serialize the exact fixed-header catalog."""
    mapping = documents["ingredient-mapping.json"]
    report = documents["validation-report.json"]
    expected_hashes = {
        key: _sha256(snapshots[path])
        for key, path in [
            ("selected", selected_path),
            ("decisions", decisions_path),
            ("catalog", catalog_path),
        ]
    }
    if mapping["input_hashes"] != expected_hashes or report["input_hashes"] != expected_hashes:
        raise ValueError("Generated inputs do not match initial snapshots")
    if report["validation_passed"] is not True:
        raise ValueError("Generated validation did not pass")
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(["ingredient_id", "name"])
    writer.writerows((row["ingredient_id"], row["name"]) for row in mapping["catalog"])
    content = buffer.getvalue().encode("utf-8-sig")
    catalog = _catalog(content)
    old_catalog = _catalog(snapshots[catalog_path])
    if catalog[: len(old_catalog)] != old_catalog:
        raise ValueError("Existing catalog identities or order changed")
    selected = json.loads(snapshots[selected_path].decode("utf-8-sig"))
    reviewed = json.loads(snapshots[decisions_path].decode("utf-8-sig"))
    _validate(
        selected,
        documents["normalized-recipes.json"],
        {row["name_raw"]: row for row in mapping["mappings"]},
        {row["name_raw"]: row for row in reviewed["decisions"]},
        {row["ingredient_id"]: row["name"] for row in catalog},
    )
    return content


def publish(selected_path: Path, decisions_path: Path, catalog_dir: Path, output: Path) -> dict:
    """Validate, preserve four CSVs, replace only Ingredient.csv and write a final report.

    All paths are explicit. Existing outputs/backups are refused. Input byte
    snapshots are rechecked before backup and replacement; concurrent writers
    must still be stopped by the operator. On I/O failure, preserve recovery files
    and raise PublicationError with phase, paths and actual catalog status.
    """
    selected_path, decisions_path, catalog_dir, output = (
        path.resolve() for path in (selected_path, decisions_path, catalog_dir, output)
    )
    originals = [catalog_dir / name for name in CSV_NAMES]
    backups = [p.with_name(f"{p.stem}_old.csv") for p in originals]
    catalog_path = originals[0]
    snapshots, recovery_paths = {}, [*backups, output]
    phase = "preflight"
    try:
        if output.exists() or output.is_symlink():
            raise ValueError(f"Output already exists: {output}")
        if any(p.exists() or p.is_symlink() for p in backups):
            raise ValueError("A required _old backup already exists")
        # A new output must not become an ancestor of any supplied input.
        if any(p.is_relative_to(output) for p in [selected_path, decisions_path, *originals]):
            raise ValueError("Output overlaps supplied inputs")
        snapshots = {p: p.read_bytes() for p in [selected_path, decisions_path, *originals]}
        phase = "validation"
        documents = build_documents(selected_path, decisions_path, catalog_path)
        catalog_bytes = _prepare(documents, snapshots, selected_path, decisions_path, catalog_path)
        serialized = {
            name: _json_bytes(documents[name])
            for name in ["ingredient-mapping.json", "normalized-recipes.json"]
        }
        _unchanged(snapshots)
        phase = "output preparation"
        output.mkdir(parents=True, exist_ok=False)
        for name, content in serialized.items():
            _write_new(output / name, content)
        phase = "backup"
        _unchanged(snapshots)
        for original, backup in zip(originals, backups, strict=True):
            _write_new(backup, snapshots[original])
        # The replacement is on the catalog filesystem, so os.replace is atomic
        # for this file only. The four backups are deliberately not a transaction.
        phase = "catalog replacement"
        with tempfile.NamedTemporaryFile(
            dir=catalog_dir, prefix=".Ingredient-", suffix=".tmp", delete=False
        ) as handle:
            temporary_catalog = Path(handle.name)
            recovery_paths.append(temporary_catalog)
            handle.write(catalog_bytes)
        if temporary_catalog.read_bytes() != catalog_bytes:
            raise OSError("Temporary catalog bytes do not match")
        _unchanged(snapshots)
        os.replace(temporary_catalog, catalog_path)
        phase = "publication verification"
        after = dict(snapshots)
        after[catalog_path] = catalog_bytes
        _unchanged(after)
        for original, backup in zip(originals, backups, strict=True):
            if backup.read_bytes() != snapshots[original]:
                raise OSError(f"Backup bytes changed: {backup}")
        for name, content in serialized.items():
            if (output / name).read_bytes() != content:
                raise OSError(f"Output bytes changed: {name}")
        report = documents["validation-report.json"]
        report.update(
            catalog_published=True,
            output_hashes={name: _sha256(content) for name, content in serialized.items()},
            published_catalog=dict(
                path=str(catalog_path),
                sha256=_sha256(catalog_bytes),
                header=["ingredient_id", "name"],
            ),
            csv_snapshots={
                original.name: dict(
                    original_path=str(original),
                    backup_path=str(backup),
                    before_sha256=_sha256(snapshots[original]),
                    backup_sha256=_sha256(backup.read_bytes()),
                    after_sha256=_sha256(original.read_bytes()),
                )
                for original, backup in zip(originals, backups, strict=True)
            },
        )
        phase = "report finalization"
        temporary_report = output / ".validation-report.json.tmp"
        recovery_paths.append(temporary_report)
        _write_new(temporary_report, _json_bytes(report))
        os.replace(temporary_report, output / "validation-report.json")
        return report
    except (OSError, ValueError, KeyError, TypeError) as error:
        remaining = [str(p) for p in recovery_paths if p.exists()]
        catalog_state = "unknown"
        if catalog_path in snapshots:
            try:
                catalog_state = (
                    "unchanged"
                    if catalog_path.read_bytes() == snapshots[catalog_path]
                    else "changed"
                )
            except OSError:
                catalog_state = "unreadable"
        raise PublicationError(
            f"Publication failed during {phase}: {error}. Catalog: {catalog_state}. "
            f"Remaining paths: {remaining}. "
            "Do not use partial outputs; inspect backups before retrying."
        ) from error
