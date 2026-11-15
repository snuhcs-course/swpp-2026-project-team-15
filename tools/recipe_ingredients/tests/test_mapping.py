# AI-generated mapping contract tests with Codex, 2026-11-15; reviewed by Soohyun An
"""Contract tests for offline reviewed ingredient ID allocation."""

import copy
import csv
import hashlib
import json

import pytest


def prepare(tmp_path):
    """Write a small selection whose source IDs cannot be used as service IDs."""
    catalog = tmp_path / "Ingredient.csv"
    with catalog.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerows([("ingredient_id", "name"), (7, "Salt"), (2, "Water")])
    selection = {
        "source_run_id": "run",
        "recipes": [
            {
                "source_id": "900",
                "recipe": {
                    "source": {
                        "id": "900",
                        "namespace": "fixture",
                        "url": "https://example.test/900",
                    },
                    "title": "Dish",
                    "ingredients": [
                        dict(
                            group="Ingredients",
                            order=i,
                            name_raw=name,
                            quantity_text=None,
                            note_raw=None,
                            source_material_id="9999",
                        )
                        for i, name in enumerate(["salt", "z", "a", "a alias"], 1)
                    ],
                    "steps": [{"order": 1, "instruction": "Cook"}],
                },
            }
        ],
    }
    decisions = {
        "decisions": [
            dict(
                name_raw="salt",
                decision="reuse_existing",
                ingredient_id="7",
                normalized_name="Salt",
            ),
            dict(
                name_raw="z", decision="new_requested", ingredient_id=None, normalized_name="Zebra"
            ),
            dict(
                name_raw="a", decision="new_requested", ingredient_id=None, normalized_name="Apple"
            ),
            dict(
                name_raw="a alias",
                decision="new_requested",
                ingredient_id=None,
                normalized_name="Apple",
            ),
            dict(
                name_raw="historical",
                decision="new_requested",
                ingredient_id=None,
                normalized_name="Unused",
            ),
        ]
    }
    return catalog, selection, decisions


def run_plan(tmp_path, catalog, selection, decisions):
    """Exercise the public planner using serialized inputs and verify read-only behavior."""
    from recipe_ingredients.mapping import build_mapping

    selected = tmp_path / "selected.json"
    reviewed = tmp_path / "decisions.json"
    selected.write_text(json.dumps(selection), encoding="utf-8")
    reviewed.write_text(json.dumps(decisions), encoding="utf-8")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    try:
        return build_mapping(selected, reviewed, catalog)
    finally:
        assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_stable_existing_ids_sorted_new_names_and_historical_rows(tmp_path):
    catalog, selection, decisions = prepare(tmp_path)
    result = run_plan(tmp_path, catalog, selection, decisions)
    assert result["catalog"] == [
        {"ingredient_id": 7, "name": "Salt"},
        {"ingredient_id": 2, "name": "Water"},
        {"ingredient_id": 8, "name": "Apple"},
        {"ingredient_id": 9, "name": "Zebra"},
    ]
    mappings = {r["name_raw"]: r for r in result["mappings"]}
    assert (
        mappings["a"]["targets"]
        == mappings["a alias"]["targets"]
        == [{"ingredient_id": 8, "normalized_name": "Apple"}]
    )
    assert mappings["historical"]["active_occurrences"] == 0
    assert mappings["historical"]["targets"] == []
    assert mappings["salt"]["targets"][0]["ingredient_id"] == 7
    assert result["selected"] == selection
    decisions["decisions"].reverse()
    assert run_plan(tmp_path, catalog, selection, decisions)["mappings"] == result["mappings"]


@pytest.mark.parametrize(
    "problem",
    [
        "missing",
        "duplicate",
        "hold",
        "unresolved",
        "unknown_disposition",
        "reuse_id",
        "reuse_name",
        "new_existing",
        "blank",
        "new_id",
        "long_name",
        "counts",
        "active_count",
        "active_recipe_count",
        "metadata_count",
        "hash",
        "identity",
        "duplicate_recipe",
        "duplicate_order",
        "bad_order",
        "blank_raw",
        "active_quality_exclusion",
        "unknown_split",
        "duplicate_split",
        "empty_split",
    ],
)
def test_invalid_inputs_fail_without_mutation(tmp_path, problem):
    catalog, selection, decisions = prepare(tmp_path)
    first = decisions["decisions"][0]
    ingredient = selection["recipes"][0]["recipe"]["ingredients"][0]
    if problem == "missing":
        decisions["decisions"].pop(0)
    elif problem == "duplicate":
        decisions["decisions"].append(copy.deepcopy(first))
    elif problem in {"hold", "unresolved", "unknown_disposition"}:
        first["decision"] = problem
    elif problem == "reuse_id":
        first["ingredient_id"] = "99"
    elif problem == "reuse_name":
        first["normalized_name"] = "Wrong"
    elif problem == "new_existing":
        decisions["decisions"][1]["normalized_name"] = "Salt"
    elif problem in {"blank", "long_name"}:
        decisions["decisions"][1]["normalized_name"] = " " if problem == "blank" else "x" * 101
    elif problem == "new_id":
        decisions["decisions"][1]["ingredient_id"] = "9999"
    elif problem == "counts":
        decisions["counts"] = {"new_requested": 1}
    elif problem in {"active_count", "active_recipe_count"}:
        first["active_occurrences" if problem == "active_count" else "active_recipe_count"] = 10
    elif problem == "metadata_count":
        decisions["active_selection"] = {"recipe_count": 9}
    elif problem == "hash":
        decisions["active_selection"] = {"sha256": "0" * 64}
    elif problem == "identity":
        selection["recipes"][0]["recipe"]["source"]["id"] = "wrong"
    elif problem == "duplicate_recipe":
        selection["recipes"].append(copy.deepcopy(selection["recipes"][0]))
    elif problem == "duplicate_order":
        selection["recipes"][0]["recipe"]["ingredients"].append(copy.deepcopy(ingredient))
    elif problem == "bad_order":
        ingredient["order"] = True
    elif problem == "blank_raw":
        ingredient["name_raw"] = ""
    elif problem == "active_quality_exclusion":
        first.update(decision="excluded_recipe_only", ingredient_id=None, normalized_name=None)
    else:
        target = dict(
            ingredient_id="99" if problem == "unknown_split" else "7",
            normalized_name="Salt",
            quantity_text=None,
        )
        first.update(
            decision="split_existing",
            ingredient_id=None,
            normalized_name=None,
            targets=[] if problem == "empty_split" else [target, copy.deepcopy(target)],
        )
    with pytest.raises(ValueError):
        run_plan(tmp_path, catalog, selection, decisions)


@pytest.mark.parametrize(
    "records",
    [
        [(7, "Salt"), (7, "Other")],
        [(7, "Salt"), (8, "Salt")],
        [(0, "Salt")],
        [("x", "Salt")],
        [(7, " ")],
        [(7, "x" * 101)],
    ],
)
def test_invalid_catalog(tmp_path, records):
    catalog, selection, decisions = prepare(tmp_path)
    with catalog.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows([("ingredient_id", "name"), *records])
    with pytest.raises(ValueError):
        run_plan(tmp_path, catalog, selection, decisions)


def test_valid_hash_metadata_and_split_exclusion_targets(tmp_path):
    catalog, selection, decisions = prepare(tmp_path)
    first = decisions["decisions"][0]
    first.update(
        decision="split_existing",
        ingredient_id=None,
        normalized_name=None,
        targets=[
            dict(ingredient_id="7", normalized_name="Salt", quantity_text=None),
            dict(ingredient_id="2", normalized_name="Water", quantity_text=None),
        ],
    )
    decisions["decisions"][1].update(decision="exclude_non_ingredient", normalized_name=None)
    decisions["decisions"][2].update(decision="exclude_prepared_component", normalized_name=None)
    decisions["active_selection"] = {
        "sha256": hashlib.sha256(json.dumps(selection).encode()).hexdigest(),
        "recipe_count": 1,
        "ingredient_rows": 4,
        "unique_raw_names": 4,
    }
    result = run_plan(tmp_path, catalog, selection, decisions)
    mappings = {r["name_raw"]: r for r in result["mappings"]}
    assert [t["ingredient_id"] for t in mappings["salt"]["targets"]] == [7, 2]
    assert mappings["z"]["targets"] == mappings["a"]["targets"] == []
    assert result["catalog"][-1] == {"ingredient_id": 8, "name": "Apple"}
