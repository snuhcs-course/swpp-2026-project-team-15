# AI-assisted with Codex, 2026-11-15; reviewed by Soohyun An
"""Build exact-title review candidates and validate human duplicate decisions."""

import csv
import json
from pathlib import Path

from .titles import TITLE_COLUMNS, read_selection, source_path

DECISION_COLUMNS = ("source_id", "decision", "duplicate_of", "reason")


def read_csv_rows(path: Path, columns: tuple[str, ...], source_ids: list[str]) -> list[dict]:
    """Join an exact-column worksheet to selected string IDs without editing values."""
    expected = set(source_ids)
    indexed = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(columns):
            raise ValueError(f"Expected CSV columns: {','.join(columns)}")
        for row in reader:
            source_id = row["source_id"]
            if source_id not in expected:
                raise ValueError(f"Unknown source ID: {source_id}")
            if source_id in indexed:
                raise ValueError(f"Duplicate source ID: {source_id}")
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"Malformed CSV row: {source_id}")
            indexed[source_id] = row
    missing = [source_id for source_id in source_ids if source_id not in indexed]
    if missing:
        raise ValueError(f"Missing source IDs: {', '.join(missing)}")
    return [indexed[source_id] for source_id in source_ids]


def read_mapping(path: Path, records: list[dict]) -> list[dict]:
    """Validate source titles ignoring whitespace; preserve user title keys verbatim."""
    rows = read_csv_rows(path, TITLE_COLUMNS, [r["source"]["id"] for r in records])
    for record, row in zip(records, rows, strict=True):
        if "".join(row["original_title"].split()) != "".join(record["title"].split()):
            raise ValueError(f"Original title mismatch: {row['source_id']}")
    return rows


def read_decisions(path: Path, source_ids: list[str]) -> list[dict]:
    """Validate draft decisions, allowing pending but requiring direct keep targets.

    Keep means retained by duplicate review only, not approved for service use.
    Pending reasons can record manual review needs; no decision is inferred or repaired.
    """
    rows = read_csv_rows(path, DECISION_COLUMNS, source_ids)
    indexed = {row["source_id"]: row for row in rows}
    for row in rows:
        source_id, decision, target = row["source_id"], row["decision"], row["duplicate_of"]
        if decision not in {"keep", "exclude", "pending"}:
            raise ValueError(f"Invalid decision: {source_id}")
        if decision != "exclude":
            if target:
                raise ValueError(f"Only exclude may reference a representative: {source_id}")
        elif (
            not row["reason"].strip()
            or target == source_id
            or target not in indexed
            or indexed[target]["decision"] != "keep"
        ):
            raise ValueError(
                f"Exclude requires a reason and a different direct keep ID: {source_id}"
            )
    return rows


def export_groups(source_run: Path, titles: Path, output: Path) -> dict:
    """Create candidate JSON and an all-pending worksheet in a new output directory.

    Validate inputs before creating the directory. Reference images without opening
    or copying them; comparison uses source records so CSV whitespace edits do not
    replace the source original title. Return the generated candidate report.
    """
    root = source_run.expanduser().resolve()
    destination = output.expanduser().resolve()
    if destination.is_relative_to(root):
        raise ValueError("Output must be outside the source run")
    if titles.expanduser().resolve().is_relative_to(destination):
        raise ValueError("Output must be separate from the title worksheet")
    if destination.exists():
        raise FileExistsError(f"Output already exists: {destination}")
    manifest, records = read_selection(root)
    rows = read_mapping(titles, records)
    candidates, unfinished = {}, []
    for record, row in zip(records, rows, strict=True):
        source_id, name = row["source_id"], row["normalized_title"]
        if not name.strip():
            unfinished.append(source_id)
            continue
        try:
            image = source_path(root, manifest["images"][source_id]["path"])
            item = dict(
                source_id=source_id,
                original_title=record["title"],
                normalized_title=name,
                source_url=record["source"]["url"],
                ingredients=record["ingredients"],
                steps=record["steps"],
                thumbnail_path=image.relative_to(root).as_posix(),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid comparison data {source_id}: {exc}") from exc
        candidates.setdefault(name, []).append(item)
    report = dict(
        source_run_id=manifest["run_id"],
        title_normalization_complete=not unfinished,
        unfinished_ids=unfinished,
        groups=[
            dict(normalized_title=name, recipes=items)
            for name, items in candidates.items()
            if len(items) > 1
        ],
    )
    destination.mkdir(parents=True)
    with (destination / "groups.json").open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    with (destination / "decisions.csv").open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=DECISION_COLUMNS)
        writer.writeheader()
        writer.writerows(
            dict(source_id=row["source_id"], decision="pending", duplicate_of="", reason="")
            for row in rows
        )
    return report
