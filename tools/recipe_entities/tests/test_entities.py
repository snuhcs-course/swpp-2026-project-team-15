# AI-generated with Codex, 2026-11-16; reviewed by Soohyun An
"""Append acceptance contracts, without duplicating importer CSV/FK tests."""

import hashlib
import importlib
import json

import pytest

from recipe_entities.tests.support import read, write


def export(case, output):
    return importlib.import_module("recipe_entities.entities").write_entities(*case[:4], output)


@pytest.mark.parametrize("legacy", [False, True])
def test_preserves_old_records_and_appends_source_ids_with_complete_provenance(
    append_case, tmp_path, legacy
):
    normalized, catalog, review, existing, document = append_case
    if legacy:
        old = read(existing / "Recipe.csv")
        write(existing / "Recipe.csv", list(old[0])[:-1], [list(old[0].values())[:-1]])
    inputs = [normalized, catalog, *review.iterdir(), *existing.iterdir()]
    before = {path: path.read_bytes() for path in inputs}
    output = tmp_path / "result"
    export(append_case, output)
    recipes = read(output / "csv/Recipe.csv")
    assert [r["recipe_id"] for r in recipes] == ["1", "6001", "7001"]
    original = read(existing / "Recipe.csv")[0]
    assert all(recipes[0][key] == value for key, value in original.items())
    assert recipes[0]["main_image_url"] == ("" if legacy else "/old.jpg")
    assert all(
        r["main_image_url"] == r["calories"] == r["category"] == r["cuisine_type"] == ""
        for r in recipes[1:]
    )
    relations = read(output / "csv/RecipeIngredient.csv")
    assert relations[:2] == read(existing / "RecipeIngredient.csv")
    assert [int(r["recipe_ingredient_id"]) for r in relations[2:]] == list(range(41, 49))
    assert [
        (
            r["ingredient_id"],
            r["quantity_text"],
            r["ingredient_type_code"],
            r["ingredient_type"],
            r["original_name"],
        )
        for r in relations[2:6]
    ] == [
        ("204", "1컵", "3060002", "부재료", "물"),
        ("204", "1T", "3060003", "양념", "물"),
        ("425", "", "3060001", "주재료", "청홍고추"),
        ("553", "", "3060002", "부재료", "청홍고추"),
    ]
    steps = read(output / "csv/RecipeStep.csv")
    assert steps[:2] == read(existing / "RecipeStep.csv")
    assert [r["step_id"] for r in steps[2:]] == ["101", "102", "103", "104"]
    assert [(r["step_number"], r["instruction"], r["tip"]) for r in steps[2:4]] == [
        ("1", "섞는다.\n익힌다.", "약불\n천천히"),
        ("2", "완성한다.", ""),
    ]
    for name in [
        "CookingTool.csv",
        "Allergen.csv",
        "RecipeCookingTool.csv",
        "IngredientAllergen.csv",
    ]:
        assert (output / "csv" / name).read_bytes() == before[existing / name]
    assert (output / "csv/Ingredient.csv").read_bytes() == before[catalog]
    provenance = json.loads((output / "entity-provenance.json").read_bytes())
    assert provenance["source_occurrences"] == document["source_occurrences"]
    for record, source_item in zip(
        provenance["recipes"], reversed(document["recipes"]), strict=True
    ):
        assert record["source_record"] == source_item
        assert len(record["ingredient_relations"]) == 4
        assert record["ingredient_relations"][2]["normalized_row"]["quantity_text"] is None
        assert record["steps"][0]["source_step"] == source_item["recipe"]["steps"][1]
    assert all(path.read_bytes() == content for path, content in before.items())


def test_relation_ids_are_independent_of_review_row_order(append_case, tmp_path):
    export(append_case, tmp_path / "first")
    path = append_case[2] / "ingredient-roles.csv"
    rows = read(path)
    write(path, list(rows[0]), [list(row.values()) for row in reversed(rows)])
    export(append_case, tmp_path / "second")
    for name in ["Recipe.csv", "RecipeIngredient.csv", "RecipeStep.csv"]:
        assert (tmp_path / "first/csv" / name).read_bytes() == (
            tmp_path / "second/csv" / name
        ).read_bytes()


@pytest.mark.parametrize("fault", ["collision", "pending", "catalog", "length", "type", "steps"])
def test_refuses_unsafe_append_before_creating_output(append_case, tmp_path, fault):
    normalized, catalog, review, existing, document = append_case
    if fault == "collision":
        rows = read(existing / "Recipe.csv")
        rows.append(dict(rows[0], recipe_id="7001"))
        write(existing / "Recipe.csv", list(rows[0]), [list(row.values()) for row in rows])
    elif fault == "pending":
        path = review / "ingredient-roles.csv"
        rows = read(path)
        rows[0]["ingredient_type_code"] = ""
        write(path, list(rows[0]), [list(row.values()) for row in rows])
    elif fault == "catalog":
        write(
            existing / "Ingredient.csv",
            ["ingredient_id", "name"],
            [[204, "잘못된 이름"], [425, "청고추"]],
        )
    else:
        recipe = document["recipes"][0]["recipe"]
        if fault == "length":
            recipe["cooking_time_text"] = "x" * 21
        elif fault == "type":
            recipe["servings_text"] = 2
        else:
            recipe["steps"][0]["order"] = recipe["steps"][1]["order"]
        normalized.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        context_path = review / "review-context.json"
        context = json.loads(context_path.read_bytes())
        context["input_hashes"]["normalized_recipes"] = hashlib.sha256(
            normalized.read_bytes()
        ).hexdigest()
        context_path.write_text(json.dumps(context), encoding="utf-8")
    output = tmp_path / "unsafe"
    with pytest.raises(ValueError):
        export(append_case, output)
    assert not output.exists()
