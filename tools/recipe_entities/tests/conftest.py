# AI-generated with Codex, 2026-11-16; reviewed by Soohyun An
"""Small synthetic normalized inputs; actual review data is never used in tests."""

import copy
import csv
import json

import pytest


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
