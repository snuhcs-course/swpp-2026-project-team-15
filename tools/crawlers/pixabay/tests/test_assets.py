# AI-generated initial implementation with Codex (GPT-6), 2026-11-06; reviewed by Ahyoon Choi.

"""Tests for mapping processed image files and merging their URLs into Recipe.csv."""

import csv

import pytest
from assets import generate_url_mapping, write_recipe_csv
from process import FIELDS


def _write_selection(path, recipe_ids):
    """Create review-export rows for the recipe IDs used by mapping and CSV merge tests."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for recipe_id in recipe_ids:
            writer.writerow(
                {
                    "recipe_id": recipe_id,
                    "pixabay_id": "1",
                    "user": "A",
                    "user_id": "2",
                    "page_url": "https://pixabay.test/1",
                    "image_url": "https://images.test/temporary.jpg",
                    "tags": "food",
                }
            )


def test_generate_url_mapping_uses_variant_prefix_and_reports_missing_files(tmp_path):
    """Map only selected WebP files that exist.

    The generated CSV must use a normalized public prefix and report selected IDs with no file.
    """
    selection_file = tmp_path / "selection.csv"
    images_dir = tmp_path / "images"
    mapping_file = tmp_path / "out" / "mapping.csv"
    _write_selection(selection_file, [1, 2])
    images_dir.mkdir()
    (images_dir / "1_detail.webp").write_bytes(b"image")

    result = generate_url_mapping(
        [selection_file],
        images_dir,
        mapping_file,
        public_prefix="/recipe-images/",
        variant="detail",
    )

    with mapping_file.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert result["mapped"] == 1
    assert result["missing"] == [2]
    assert rows == [{"recipe_id": "1", "image_url": "/recipe-images/1_detail.webp"}]


def test_generate_url_mapping_rejects_unknown_variants(tmp_path):
    """Fail before writing a mapping when the requested variant is outside the supported set."""
    with pytest.raises(ValueError, match="variant must be"):
        generate_url_mapping(
            [], tmp_path, tmp_path / "mapping.csv", public_prefix="/images", variant="raw"
        )


def test_write_recipe_csv_adds_urls_and_preserves_unmapped_rows(tmp_path):
    """Copy source recipe fields, append main_image_url when absent, and update only mapped IDs."""
    source = tmp_path / "Recipe.csv"
    mapping = tmp_path / "mapping.csv"
    output = tmp_path / "out" / "Recipe.csv"
    source.write_text("recipe_id,name\n1,Soup\n2,Stew\n", encoding="utf-8")
    mapping.write_text("recipe_id,image_url\n1,/recipe-images/1_list.webp\n", encoding="utf-8")

    result = write_recipe_csv(mapping, source, output)

    with output.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        assert reader.fieldnames == ["recipe_id", "name", "main_image_url"]
    assert result == {"recipes": 2, "updated": 1}
    assert rows[0]["main_image_url"] == "/recipe-images/1_list.webp"
    assert rows[1]["main_image_url"] == ""
    assert rows[0]["name"] == "Soup"


def test_write_recipe_csv_rejects_duplicate_mapping_ids(tmp_path):
    """Refuse ambiguous mapping input rather than picking one URL based on CSV row order."""
    source = tmp_path / "Recipe.csv"
    mapping = tmp_path / "mapping.csv"
    source.write_text("recipe_id,name\n1,Soup\n", encoding="utf-8")
    mapping.write_text("recipe_id,image_url\n1,/one.webp\n1,/two.webp\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate recipe_id"):
        write_recipe_csv(mapping, source, tmp_path / "out.csv")


def test_write_recipe_csv_refuses_to_overwrite_source(tmp_path):
    """Protect the authoritative source CSV by rejecting identical resolved input/output paths."""
    source = tmp_path / "Recipe.csv"
    mapping = tmp_path / "mapping.csv"
    source.write_text("recipe_id,name\n1,Soup\n", encoding="utf-8")
    mapping.write_text("recipe_id,image_url\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must differ"):
        write_recipe_csv(mapping, source, source)
