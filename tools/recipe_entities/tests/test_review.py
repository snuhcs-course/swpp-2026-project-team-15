# AI-generated with Codex, 2026-11-16; reviewed by Soohyun An
"""Review contracts from the approved entity preparation specification."""

import csv
import importlib
import json

import pytest


def module():
    return importlib.import_module("recipe_entities.review")


def csv_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames, list(reader)


def save_rows(path, headers, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def completed_review(entity_inputs, tmp_path):
    normalized, catalog, _ = entity_inputs
    folder = tmp_path / "review"
    module().create_review(normalized, catalog, folder)
    path = folder / "ingredient-roles.csv"
    headers, rows = csv_rows(path)
    for row, code in zip(rows, ["3060002", "3060003", "3060001", "3060002"], strict=True):
        row["ingredient_type_code"] = code
        row["review_note"] = "사람의 판정"
    save_rows(path, headers, rows)
    return folder, path, headers, rows


def test_exports_separate_occurrences_and_split_components_without_inference(
    entity_inputs, tmp_path
):
    normalized, catalog, _ = entity_inputs
    before = [path.read_bytes() for path in (normalized, catalog)]
    folder = tmp_path / "review"
    module().create_review(normalized, catalog, folder)
    path = folder / "ingredient-roles.csv"
    _, rows = csv_rows(path)
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    assert [
        (
            r["source_occurrence_index"],
            r["component_index"],
            r["ingredient_id"],
            r["original_name"],
            r["quantity_text"],
        )
        for r in rows
    ] == [
        ("0", "1", "204", "물", "1컵"),
        ("1", "1", "204", "물", "1T"),
        ("2", "1", "425", "청홍고추", ""),
        ("2", "2", "553", "청홍고추", ""),
    ]
    assert all(r["ingredient_type_code"] == r["review_note"] == "" for r in rows)
    assert [path.read_bytes() for path in (normalized, catalog)] == before


def test_reads_reordered_decisions_with_independent_roles_for_the_same_id(entity_inputs, tmp_path):
    folder, path, headers, rows = completed_review(entity_inputs, tmp_path)
    save_rows(path, headers, list(reversed(rows)))
    before = path.read_bytes()
    approved = module().read_review(*entity_inputs[:2], folder)
    assert approved == rows
    assert path.read_bytes() == before


@pytest.mark.parametrize("fault", ["missing", "duplicate", "extra", "context", "blank", "code"])
def test_rejects_review_that_would_misclassify_or_drop_an_occurrence(
    entity_inputs, tmp_path, fault
):
    folder, path, headers, rows = completed_review(entity_inputs, tmp_path)
    if fault == "missing":
        rows.pop()
    elif fault == "duplicate":
        rows[-1] = rows[0].copy()
    elif fault == "extra":
        rows.append(dict(rows[0], source_occurrence_index="99"))
    elif fault == "context":
        rows[0]["quantity_text"] = "100컵"
    elif fault == "blank":
        rows[0]["ingredient_type_code"] = ""
    else:
        rows[0]["ingredient_type_code"] = "3069999"
    save_rows(path, headers, rows)
    before = path.read_bytes()
    with pytest.raises(ValueError, match="7001"):
        module().read_review(*entity_inputs[:2], folder)
    assert path.read_bytes() == before


@pytest.mark.parametrize("input_index", [0, 1])
def test_rejects_stale_input_even_when_parsed_values_are_unchanged(
    entity_inputs, tmp_path, input_index
):
    folder, _, _, _ = completed_review(entity_inputs, tmp_path)
    path = entity_inputs[input_index]
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="hash"):
        module().read_review(*entity_inputs[:2], folder)


@pytest.mark.parametrize("fault", ["source_id", "catalog_name", "reference", "duplicate_component"])
def test_refuses_invalid_identity_before_creating_review_output(entity_inputs, tmp_path, fault):
    normalized, catalog, document = entity_inputs
    recipe = document["recipes"][0]["recipe"]
    if fault == "source_id":
        recipe["source"]["id"] = "7002"
    elif fault == "catalog_name":
        recipe["ingredients"][0]["normalized_name"] = "다른 재료"
    elif fault == "reference":
        recipe["ingredients"][0]["source"]["occurrence_index"] = 3
    else:
        recipe["ingredients"].append(recipe["ingredients"][0].copy())
    normalized.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    folder = tmp_path / "invalid"
    with pytest.raises(ValueError, match="7001"):
        module().create_review(normalized, catalog, folder)
    assert not folder.exists()


def test_refuses_to_overwrite_completed_review(entity_inputs, tmp_path):
    folder, path, _, _ = completed_review(entity_inputs, tmp_path)
    before = path.read_bytes()
    with pytest.raises(ValueError, match="exist"):
        module().create_review(*entity_inputs[:2], folder)
    assert path.read_bytes() == before
