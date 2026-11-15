# AI-assisted with Codex, 2026-11-15; reviewed by Soohyun An
"""Export explicitly reviewed recipe copies while retaining source provenance."""

import csv
import json
from pathlib import Path

from .review import read_decisions, read_mapping
from .titles import read_selection, source_path


def read_quality_exclusions(path: Path, mappings: list[dict]) -> list[dict]:
    """Validate a user-supplied subset of IDs, exact normalized titles and reasons."""
    indexed = {row["source_id"]: row for row in mappings}
    exclusions = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["source_id", "normalized_title", "reason"]:
            raise ValueError("Expected quality CSV columns: source_id,normalized_title,reason")
        for row in reader:
            source_id = row["source_id"]
            if source_id not in indexed or source_id in exclusions:
                raise ValueError(f"Unknown or duplicate quality exclusion ID: {source_id}")
            if (
                None in row
                or any(v is None for v in row.values())
                or row["normalized_title"] != indexed[source_id]["normalized_title"]
                or not row["reason"].strip()
            ):
                raise ValueError(f"Invalid quality exclusion title or reason: {source_id}")
            exclusions[source_id] = row
    return [exclusions[row["source_id"]] for row in mappings if row["source_id"] in exclusions]


def export_selection(
    source_run: Path,
    titles: Path,
    decisions: Path,
    output: Path,
    quality_exclusions: Path | None = None,
) -> dict:
    """Write kept recipes and a decision report only after complete input validation.

    Preserve source order, original titles and all recipe fields except the copied
    title. Explicit quality exclusions override keep/pending without changing the
    duplicate worksheet; other pending decisions and all unfinished titles block
    export. Quality-excluded representatives require explicit human reselection.
    Return the report; never overwrite inputs, source files or existing results.
    """
    root = source_run.expanduser().resolve()
    destination = output.expanduser().resolve()
    if destination.is_relative_to(root):
        raise ValueError("Output must be outside the source run")
    if destination.exists():
        raise FileExistsError(f"Output already exists: {destination}")
    inputs = [titles, decisions] + ([quality_exclusions] if quality_exclusions else [])
    if any(path.expanduser().resolve().is_relative_to(destination) for path in inputs):
        raise ValueError("Output must be separate from input worksheets")
    manifest, records = read_selection(root)
    mappings = read_mapping(titles, records)
    source_ids = [record["source"]["id"] for record in records]
    reviewed = read_decisions(decisions, source_ids)
    quality = read_quality_exclusions(quality_exclusions, mappings) if quality_exclusions else []
    quality_ids = {row["source_id"] for row in quality}
    for row in reviewed:
        if row["duplicate_of"] in quality_ids:
            raise ValueError(
                f"Quality-excluded representative requires reselection: {row['duplicate_of']}"
            )
    unfinished = [row["source_id"] for row in mappings if not row["normalized_title"].strip()]
    pending = [
        row["source_id"]
        for row in reviewed
        if row["decision"] == "pending" and row["source_id"] not in quality_ids
    ]
    if unfinished or pending:
        raise ValueError(f"Unfinished title IDs: {unfinished}; pending decision IDs: {pending}")
    kept, excluded = [], []
    for record, mapping, decision in zip(records, mappings, reviewed, strict=True):
        source_id = mapping["source_id"]
        if decision["decision"] == "exclude" or source_id in quality_ids:
            excluded.append(source_id)
            continue
        try:
            image = source_path(root, manifest["images"][source_id]["path"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid thumbnail reference {source_id}: {exc}") from exc
        kept.append(
            dict(
                source_id=source_id,
                original_title=record["title"],
                thumbnail_path=image.relative_to(root).as_posix(),
                recipe=dict(record, title=mapping["normalized_title"]),
            )
        )
    dataset = dict(source_run_id=manifest["run_id"], recipes=kept)
    report = dict(
        source_run_id=manifest["run_id"],
        input_count=len(records),
        kept_count=len(kept),
        excluded_count=len(excluded),
        kept_ids=[item["source_id"] for item in kept],
        excluded_ids=excluded,
        decisions=reviewed,
        title_normalization_complete=True,
        duplicate_review_complete=not any(row["decision"] == "pending" for row in reviewed),
        selection_complete=True,
        duplicate_excluded_ids=[
            row["source_id"] for row in reviewed if row["decision"] == "exclude"
        ],
        quality_exclusions=quality,
        service_suitability_assessed=False,
        remaining_work=[
            "ingredient_normalization",
            "entity_csv_conversion",
            "image_deployment",
            "database_import",
        ],
    )
    destination.mkdir(parents=True)
    for filename, content in (
        ("selected-recipes.json", dataset),
        ("selection-report.json", report),
    ):
        with (destination / filename).open("x", encoding="utf-8") as handle:
            json.dump(content, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    return report
