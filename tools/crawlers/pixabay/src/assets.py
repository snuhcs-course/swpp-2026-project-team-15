"""Export local image URL mappings and DB-ready recipe CSV files."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from process import load_selections


def generate_url_mapping(
    files: list[Path],
    images_dir: Path,
    mapping_file: Path,
    *,
    public_prefix: str,
    variant: str,
) -> dict[str, Any]:
    """Map selected recipe IDs to the configured public URL of each processed image."""
    if variant not in {"thumb", "list", "detail"}:
        raise ValueError("variant must be thumb, list or detail")
    selections = load_selections(files)
    mapping: dict[int, str] = {}
    missing: list[int] = []
    prefix = public_prefix.rstrip("/")
    for recipe_id in selections:
        filename = f"{recipe_id}_{variant}.webp"
        if (images_dir / filename).is_file():
            mapping[recipe_id] = f"{prefix}/{filename}" if prefix else f"/{filename}"
        else:
            missing.append(recipe_id)
    mapping_file.parent.mkdir(parents=True, exist_ok=True)
    with mapping_file.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("recipe_id", "image_url"))
        writer.writeheader()
        writer.writerows(
            {"recipe_id": recipe_id, "image_url": url} for recipe_id, url in sorted(mapping.items())
        )
    return {"mapped": len(mapping), "missing": missing, "mapping_file": mapping_file}


def write_recipe_csv(mapping_file: Path, source_csv: Path, output_csv: Path) -> dict[str, int]:
    """Add mapping URLs to a copy of Recipe.csv using the server importer schema."""
    if source_csv.resolve() == output_csv.resolve():
        raise ValueError("Output Recipe.csv must differ from the source file")
    mapping: dict[str, str] = {}
    with mapping_file.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            recipe_id, image_url = (
                row.get("recipe_id", "").strip(),
                row.get("image_url", "").strip(),
            )
            if recipe_id and image_url:
                if recipe_id in mapping:
                    raise ValueError(f"Duplicate recipe_id in mapping: {recipe_id}")
                mapping[recipe_id] = image_url
    with source_csv.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "recipe_id" not in reader.fieldnames:
            raise ValueError("Source Recipe.csv must include a recipe_id column")
        fieldnames = list(reader.fieldnames)
        if "main_image_url" not in fieldnames:
            fieldnames.append("main_image_url")
        rows = list(reader)
    updated = 0
    for row in rows:
        recipe_id = row.get("recipe_id", "").strip()
        if recipe_id in mapping:
            row["main_image_url"] = mapping[recipe_id]
            updated += 1
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return {"recipes": len(rows), "updated": updated}
