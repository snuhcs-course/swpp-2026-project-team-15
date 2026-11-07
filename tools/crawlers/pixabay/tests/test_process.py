# AI-generated initial implementation with Codex (GPT-6), 2026-11-06; reviewed by Ahyoon Choi.

"""Tests for local original-image conversion, skip/force behavior, and attribution output."""

import csv
import json

import pytest
from PIL import Image
from process import FIELDS, load_selections, process


def _write_selection(path, *, recipe_id="1", pixabay_id="9", user="A", user_id="4"):
    """Create one valid exported review row in the CSV schema consumed by process()."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerow(
            {
                "recipe_id": recipe_id,
                "pixabay_id": pixabay_id,
                "user": user,
                "user_id": user_id,
                "page_url": "https://pixabay.test/item",
                "image_url": "https://images.test/temporary.jpg",
                "tags": "soup",
            }
        )


def _write_image(path, *, size=(40, 20), orientation=None):
    """Create a tiny local test image and optionally attach EXIF orientation metadata."""
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", size, color=(20, 80, 140))
    if orientation is None:
        image.save(path)
    else:
        exif = Image.Exif()
        exif[274] = orientation
        image.save(path, exif=exif)


def test_process_converts_local_image_and_writes_attribution_without_blurhash(tmp_path):
    """Convert the local original and record its Pixabay attribution.

    Verify all three WebP variants exist and no BlurHash placeholder file is produced.
    """
    selection_file = tmp_path / "selections" / "batch.csv"
    downloads_dir = tmp_path / "downloads"
    images_dir = tmp_path / "server" / "static" / "images" / "recipes"
    output_dir = tmp_path / "output"
    _write_selection(selection_file)
    _write_image(downloads_dir / "1.png", size=(400, 200))

    result = process([selection_file], downloads_dir, images_dir, output_dir)

    assert result["processed"] == 1
    assert result["skipped"] == 0
    assert result["missing"] == []
    for variant in ("thumb", "list", "detail"):
        with Image.open(images_dir / f"1_{variant}.webp") as converted:
            assert converted.format == "WEBP"
    attribution = json.loads((output_dir / "attribution.json").read_text(encoding="utf-8"))
    assert attribution["1"] == {
        "pixabay_id": 9,
        "user": "A",
        "user_id": 4,
        "page_url": "https://pixabay.test/item",
        "source": "Pixabay",
    }
    assert not (output_dir / "placeholders.json").exists()


def test_process_skips_up_to_date_variants_unless_force_is_set(tmp_path):
    """Skip all newer output variants on a normal run, then regenerate each when force=True."""
    selection_file = tmp_path / "selection.csv"
    downloads_dir = tmp_path / "downloads"
    images_dir = tmp_path / "images"
    output_dir = tmp_path / "output"
    _write_selection(selection_file)
    _write_image(downloads_dir / "1.jpg")

    first = process([selection_file], downloads_dir, images_dir, output_dir)
    second = process([selection_file], downloads_dir, images_dir, output_dir)
    forced = process([selection_file], downloads_dir, images_dir, output_dir, force=True)

    assert first["skipped"] == 0
    assert second["skipped"] == 3
    assert forced["skipped"] == 0
    assert forced["processed"] == 1


def test_process_applies_exif_orientation_before_resizing(tmp_path):
    """Rotate an EXIF-tagged portrait correctly before saving dimensions to WebP variants."""
    selection_file = tmp_path / "selection.csv"
    downloads_dir = tmp_path / "downloads"
    images_dir = tmp_path / "images"
    output_dir = tmp_path / "output"
    _write_selection(selection_file)
    _write_image(downloads_dir / "1.jpg", size=(40, 20), orientation=6)

    process([selection_file], downloads_dir, images_dir, output_dir)

    with Image.open(images_dir / "1_detail.webp") as detail:
        assert detail.size == (20, 40)


@pytest.mark.parametrize("extension", ["jpg", "jpeg", "png", "webp"])
def test_process_accepts_each_supported_original_image_extension(tmp_path, extension):
    """Find locally saved originals with each extension supported by the Pixabay processing flow."""
    selection_file = tmp_path / "selection.csv"
    downloads_dir = tmp_path / "downloads"
    _write_selection(selection_file)
    _write_image(downloads_dir / f"1.{extension}")

    result = process([selection_file], downloads_dir, tmp_path / "images", tmp_path / "output")

    assert result["processed"] == 1
    assert result["missing"] == []


def test_process_reports_missing_original_and_keeps_attribution_file_valid(tmp_path):
    """Report a selected recipe that has no local original.

    The command should still write valid empty attribution JSON and finish with a missing ID result.
    """
    selection_file = tmp_path / "selection.csv"
    output_dir = tmp_path / "output"
    _write_selection(selection_file, recipe_id="12")

    result = process([selection_file], tmp_path / "no-downloads", tmp_path / "images", output_dir)

    assert result["missing"] == [12]
    assert result["processed"] == 0
    assert json.loads((output_dir / "attribution.json").read_text(encoding="utf-8")) == {}


def test_process_merges_new_attribution_without_dropping_existing_entries(tmp_path):
    """Retain existing attribution records when processing another selected recipe.

    The output JSON should contain both the old entry and metadata for the newly processed ID.
    """
    selection_file = tmp_path / "selection.csv"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "attribution.json").write_text(
        json.dumps({"99": {"source": "Pixabay", "user": "Earlier"}}), encoding="utf-8"
    )
    _write_selection(selection_file)
    _write_image(tmp_path / "downloads" / "1.webp")

    process([selection_file], tmp_path / "downloads", tmp_path / "images", output_dir)
    attribution = json.loads((output_dir / "attribution.json").read_text(encoding="utf-8"))

    assert attribution["99"]["user"] == "Earlier"
    assert attribution["1"]["user"] == "A"


def test_load_selections_rejects_non_integer_recipe_ids(tmp_path):
    """Report malformed exported CSV rows instead of assigning a selection to the wrong recipe.

    A non-integer recipe ID must fail before image processing begins.
    """
    selection_file = tmp_path / "bad.csv"
    _write_selection(selection_file, recipe_id="not-an-id")

    with pytest.raises(ValueError, match="Invalid selection row"):
        load_selections([selection_file])
