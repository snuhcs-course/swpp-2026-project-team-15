# AI-generated with Codex, 2026-11-16; reviewed by Soohyun An
"""Small synthetic normalized inputs; actual review data is never used in tests."""

import copy
import csv
import json

import pytest

from recipe_entities.review import create_review
from recipe_entities.tests.support import read, write


@pytest.fixture
def entity_inputs(tmp_path):
    """Include repeated IDs, split quantities and an excluded source occurrence."""
    raw_rows = [
        dict(
            group="[재료]",
            order=1,
            name_raw="물",
            note_raw=None,
            quantity_text="1컵",
            source_material_id="water",
        ),
        dict(
            group="[소스]",
            order=2,
            name_raw="물",
            note_raw=None,
            quantity_text="1T",
            source_material_id="water",
        ),
        dict(
            group="[재료]",
            order=3,
            name_raw="청홍고추",
            note_raw="합산량",
            quantity_text="2개",
            source_material_id=None,
        ),
        dict(
            group="[재료]",
            order=4,
            name_raw="전자렌지",
            note_raw=None,
            quantity_text=None,
            source_material_id=None,
        ),
    ]
    sources = []
    ingredients = []
    targets = [[(204, "물")], [(204, "물")], [(425, "청고추"), (553, "홍고추")], []]
    for index, (raw, components) in enumerate(zip(raw_rows, targets, strict=True)):
        source = dict(
            source_id="7001", group=raw["group"], order=raw["order"], occurrence_index=index
        )
        decision = (
            "split_existing"
            if index == 2
            else ("exclude_non_ingredient" if index == 3 else "reuse_existing")
        )
        sources.append(dict(source=source, original=raw, decision=decision))
        for component, (identity, name) in enumerate(components, 1):
            ingredients.append(
                dict(
                    copy.deepcopy(raw),
                    ingredient_id=identity,
                    normalized_name=name,
                    source=copy.deepcopy(source),
                    component_index=component,
                )
            )
            if index == 2:
                ingredients[-1]["quantity_text"] = None
    recipe = dict(
        source_id="7001",
        original_title="원래 제목",
        thumbnail_path="images/7001.jpg",
        recipe=dict(
            source=dict(id="7001", url="https://example.invalid/7001"),
            title="고추 요리",
            description=None,
            servings_text="1인분",
            cooking_time_text="10분",
            difficulty_text=None,
            ingredients=ingredients,
            steps=[dict(order=1, instruction="섞는다.", tips=["천천히"], image_urls=[])],
            findings=[],
            listed_tools=None,
        ),
    )
    document = dict(source_run_id="synthetic", recipes=[recipe], source_occurrences=sources)
    normalized = tmp_path / "normalized.json"
    catalog = tmp_path / "Ingredient.csv"
    normalized.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    with catalog.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerows([["ingredient_id", "name"], [204, "물"], [425, "청고추"], [553, "홍고추"]])
    return normalized, catalog, document


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
