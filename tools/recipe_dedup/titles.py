# AI-assisted with Codex, 2026-11-15; Soohyun An
"""Export selected source titles without modifying the collection or inferring names."""

import csv
import json
from pathlib import Path

TITLE_COLUMNS = ("source_id", "original_title", "normalized_title")


def source_path(root: Path, relative: str) -> Path:
    """Resolve a run-relative reference while rejecting paths outside its root."""
    reference = Path(relative)
    path = (root / reference).resolve()
    if reference.is_absolute() or not path.is_relative_to(root) or path == root:
        raise ValueError("Reference path must stay inside the source run")
    return path


def read_selection(source_run: Path) -> tuple[dict, list[dict]]:
    """Read allocation-ordered records, rejecting invalid identity and escaping paths."""
    root = source_run.expanduser().resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8-sig"))
    if not isinstance(manifest, dict) or not isinstance(manifest.get("allocations"), list):
        raise ValueError("Expected a manifest with selected allocations")
    rows, seen = [], set()
    for allocation in manifest["allocations"]:
        source_id = allocation.get("source_id") if isinstance(allocation, dict) else None
        if not isinstance(source_id, str) or not source_id.strip():
            raise ValueError("Expected a nonempty string source ID in each allocation")
        if source_id in seen:
            raise ValueError(f"Duplicate selected source ID: {source_id}")
        seen.add(source_id)
        try:
            path = source_path(root, manifest["details"][source_id]["record"]["path"])
            record = json.loads(path.read_text(encoding="utf-8-sig"))
            if record["source"]["id"] != source_id:
                raise ValueError("Record identity differs from the selected ID")
            title = record["title"]
            if not isinstance(title, str):
                raise ValueError("Original title must be text")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise ValueError(f"Invalid selected recipe {source_id}: {exc}") from exc
        rows.append(record)
    return manifest, rows


def read_title_rows(source_run: Path) -> list[dict[str, str]]:
    """Return unchanged source titles and empty user titles in selection order."""
    _, records = read_selection(source_run)
    return [
        dict(source_id=r["source"]["id"], original_title=r["title"], normalized_title="")
        for r in records
    ]


def export_titles(source_run: Path, output: Path) -> int:
    """Create a new UTF-8 BOM worksheet after validating all selected records.

    Return the row count. Source files and existing worksheets are never overwritten;
    the normalized title stays empty because only the user authors that value.
    """
    root = source_run.expanduser().resolve()
    destination = output.expanduser().resolve()
    if destination.is_relative_to(root):
        raise ValueError("Output must be outside the source run")
    if destination.exists():
        raise FileExistsError(f"Output already exists: {destination}")
    # Read the whole small selection first so invalid input leaves no output directory.
    rows = read_title_rows(root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation also protects manual work if a file appears after validation.
    with destination.open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TITLE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)
