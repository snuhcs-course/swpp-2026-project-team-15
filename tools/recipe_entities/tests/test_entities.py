# AI-generated with Codex, 2026-11-16; reviewed by Soohyun An
"""Append acceptance contracts, without duplicating importer CSV/FK tests."""

import copy
import csv
import hashlib
import importlib
import json

import pytest

from recipe_entities.review import create_review


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write(path, headers, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


@pytest.fixture
def append_case(entity_inputs, tmp_path):
    """Two new recipes in reverse ID order and old IDs with gaps."""
    normalized, catalog, document = entity_inputs
    first = document["recipes"][0]
    first["recipe"]["steps"] = [
        dict(order=2, instruction="완성한다.", tips=[], image_urls=[]),
        dict(
            order=1,
            instruction="섞는다.\n익힌다.",
            tips=["약불", "천천히"],
            image_urls=["local-step"],
        ),
    ]
    other = copy.deepcopy(first)
    other["source_id"] = other["recipe"]["source"]["id"] = "6001"
    other["thumbnail_path"] = "images/6001.jpg"
    for row in other["recipe"]["ingredients"]:
        row["source"]["source_id"] = "6001"
        row["source"]["occurrence_index"] += 4
    extra_sources = copy.deepcopy(document["source_occurrences"])
    for row in extra_sources:
        row["source"]["source_id"] = "6001"
        row["source"]["occurrence_index"] += 4
    document["recipes"].append(other)
    document["source_occurrences"].extend(extra_sources)
    normalized.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    review = tmp_path / "approved"
    create_review(normalized, catalog, review)
    path = review / "ingredient-roles.csv"
    approved = read(path)
    for index, row in enumerate(approved):
        row["ingredient_type_code"] = ["3060002", "3060003", "3060001", "3060002"][index % 4]
        row["review_note"] = "확정"
    write(path, list(approved[0]), [list(row.values()) for row in approved])
    existing = tmp_path / "existing"
    existing.mkdir()
    tables = {
        "Recipe.csv": (
            "recipe_id,name,description,cuisine_type,category,cooking_time,calories,servings,difficulty,main_image_url",
            [
                [
                    1,
                    "기존 요리",
                    "원문\n설명",
                    "한식",
                    "밥",
                    "20분",
                    "100",
                    "1인분",
                    "쉬움",
                    "/old.jpg",
                ]
            ],
        ),
        "Ingredient.csv": ("ingredient_id,name", [[204, "물"], [425, "청고추"]]),
        "CookingTool.csv": ("tool_id,name", [[3, "숟가락"]]),
        "Allergen.csv": ("allergen_id,name", [[2, "기존 알레르기"]]),
        "RecipeStep.csv": (
            "step_id,recipe_id,step_number,instruction,tip",
            [[2, 1, 1, "기존 단계", "팁"], [100, 1, 2, "마무리", ""]],
        ),
        "RecipeIngredient.csv": (
            "recipe_ingredient_id,recipe_id,ingredient_id,quantity_text,ingredient_type_code,ingredient_type,original_name",
            [
                [1, 1, 204, "1컵", "3060002", "부재료", "물"],
                [40, 1, 425, "1개", "3060001", "주재료", "고추"],
            ],
        ),
        "RecipeCookingTool.csv": ("recipe_id,tool_id", [[1, 3]]),
        "IngredientAllergen.csv": ("ingredient_id,allergen_id", [[425, 2]]),
    }
    for name, (header, values) in tables.items():
        write(existing / name, header.split(","), values)
    return normalized, catalog, review, existing, document


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
