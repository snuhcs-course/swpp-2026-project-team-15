# AI-generated with Claude Code (Sonnet 5.5), 2026-11-03; reviewed by Jaehyuk Choi.
"""Assumed-seasoning policy: one object for selection, request and check; data-driven list."""

import json
from dataclasses import replace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app, create_app_from_env
from app.recipes import constants
from app.recipes.policy import RecommendationPolicy
from app.recipes.recommendations import RecommendationService
from app.recipes.seasonings import (
    DEFAULT_FILE,
    FILE_ENV,
    MODE_ENV,
    load_seasoning_policy,
    validate_against_catalog,
)
from recipe_revision.compact import available_ids, build_compact_request, check_result
from recipe_revision.models import InventoryIngredient, SourceIngredient, SourceRecipe, SourceStep
from recipe_revision.seasoning import (
    ASSUME_ALL,
    ASSUME_NONE,
    SeasoningConfigError,
    SeasoningPolicy,
)
from tests.conftest import StubVision

MAIN, SECONDARY, SEASONING = "3060001", "3060002", "3060003"
LABEL = {MAIN: "주재료", SECONDARY: "부재료", SEASONING: "양념"}
SALT, GARLIC, GOCHUJANG = 284, 103, 20


def row(row_id, ingredient_id, name, code):
    return SourceIngredient(row_id, ingredient_id, name, "1", code, LABEL[code], name)


def recipe():
    return SourceRecipe(
        7,
        "양파전",
        None,
        None,
        None,
        None,
        None,
        "2인분",
        None,
        (
            row(1, 345, "양파", MAIN),
            row(2, SALT, "소금", SEASONING),
            row(3, GARLIC, "다진마늘", SEASONING),
            row(4, GOCHUJANG, "고추장", SEASONING),
            row(5, 204, "물", MAIN),
        ),
        (SourceStep(11, 1, "양파를 썬다.", None),),
    )


def items(*pairs):
    return tuple(InventoryIngredient(i, n) for i, n in (*pairs, (204, "물")))


LIST = SeasoningPolicy("list", frozenset({SALT, GARLIC}), {SALT: "소금", GARLIC: "다진마늘"})


def statuses(seasonings, inventory):
    payload = json.loads(build_compact_request(recipe(), inventory, seasonings=seasonings).user)
    return {r["ingredient_id"]: r["status"] for r in payload["original"]["ingredients"]}


def counted(seasonings, available=frozenset({345, 204})):
    return RecommendationPolicy(seasonings=seasonings).metrics(recipe(), available)


def test_three_modes_decide_the_same_way_everywhere():
    inv = items((345, "양파"))
    assert statuses(LIST, inv) == {
        345: "owned",
        SALT: "assumed",
        GARLIC: "assumed",
        GOCHUJANG: "unavailable",
        204: "owned",
    }
    assert statuses(ASSUME_ALL, inv)[GOCHUJANG] == "assumed"
    assert statuses(ASSUME_NONE, inv)[SALT] == "unavailable"
    assert available_ids(recipe(), inv, seasonings=LIST) == {345, 204, SALT, GARLIC}
    assert available_ids(recipe(), inv, seasonings=ASSUME_ALL) == {
        345,
        204,
        SALT,
        GARLIC,
        GOCHUJANG,
    }
    assert available_ids(recipe(), inv, seasonings=ASSUME_NONE) == {345, 204}
    # The same object drives the filter's counts.

    def missing(policy):
        counts = counted(policy)
        return counts.total_ingredients - counts.total_matches

    assert (missing(LIST), missing(ASSUME_ALL), missing(ASSUME_NONE)) == (1, 0, 3)


def test_listed_id_is_assumed_whatever_its_label_and_unlisted_seasoning_is_not():
    assert LIST.assumed(SALT, False) and LIST.assumed(SALT, True)
    assert not LIST.assumed(GOCHUJANG, True)
    assert ASSUME_ALL.assumed(GOCHUJANG, True) and not ASSUME_ALL.assumed(345, False)
    assert not ASSUME_NONE.assumed(SALT, True)


def test_editing_the_list_changes_selection_request_and_check_together():
    inv = items((345, "양파"))
    longer = replace(LIST, assumed_ids=LIST.assumed_ids | {GOCHUJANG})
    shorter = replace(LIST, assumed_ids=LIST.assumed_ids - {GARLIC})
    result = {
        "can_revise": True,
        "revised_recipe": {
            "ingredients": [{"ingredient_id": GOCHUJANG}],
            "steps": [{"instruction": "고추장을 푼다.", "tip": None}],
        },
    }
    assert check_result(result, recipe(), inv, seasonings=LIST) == [
        "unavailable_ingredient",
        "unavailable_in_steps",
    ]
    assert check_result(result, recipe(), inv, seasonings=longer) == []
    assert statuses(longer, inv)[GOCHUJANG] == "assumed"
    assert statuses(shorter, inv)[GARLIC] == "unavailable"

    def count(policy):
        return counted(policy).total_ingredients

    assert (count(LIST), count(longer), count(shorter)) == (2, 1, 3)


def test_mode_all_matches_the_series_default_and_the_legacy_filter():
    inv = items((345, "양파"))
    assert build_compact_request(recipe(), inv) == build_compact_request(
        recipe(), inv, seasonings=ASSUME_ALL
    )
    legacy = RecommendationPolicy(excluded_types=frozenset({"양념"}), seasonings=ASSUME_NONE)
    new = RecommendationPolicy(seasonings=ASSUME_ALL)
    for available in (frozenset({345, 204}), frozenset({345, 204, SALT}), frozenset({204})):
        assert legacy.metrics(recipe(), available) == new.metrics(recipe(), available)


def test_none_mode_uses_the_strict_prompt_and_list_mode_the_staples_prompt():
    inv = items((345, "양파"))
    assert "assumed" not in build_compact_request(recipe(), inv, seasonings=ASSUME_NONE).system
    assert "assumed" in build_compact_request(recipe(), inv, seasonings=LIST).system


# --- configuration -------------------------------------------------------------------------


def write(tmp_path, config):
    path = tmp_path / "seasonings.json"
    path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "config,message",
    [
        ([], "JSON object"),
        ({"mode": "some"}, "mode must be one of"),
        ({"assumed": [{"id": 1, "name": "a"}, {"id": 1, "name": "b"}]}, "duplicate"),
        ({"assumed": [{"name": "a"}]}, "needs an 'id'"),
        ({"assumed": [{"id": "1"}]}, "must be an integer"),
        ({"assumed": [{"id": -3}]}, "positive"),
        ({"assumed": "x"}, "list of"),
        ({"surprise": 1}, "unknown seasoning config keys"),
    ],
)
def test_invalid_config_fails_with_a_clear_message(tmp_path, config, message):
    with pytest.raises(SeasoningConfigError, match=message):
        load_seasoning_policy({}, path=write(tmp_path, config))


def test_unreadable_or_malformed_file_is_reported(tmp_path):
    with pytest.raises(SeasoningConfigError, match="cannot read"):
        load_seasoning_policy({}, path=tmp_path / "missing.json")
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    with pytest.raises(SeasoningConfigError, match="not valid JSON"):
        load_seasoning_policy({}, path=bad)


def test_env_overrides_file_and_mode_without_code_changes(tmp_path):
    path = write(tmp_path, {"mode": "list", "assumed": [{"id": 5, "name": "x"}]})
    policy = load_seasoning_policy({FILE_ENV: str(path)})
    assert (policy.mode, policy.assumed_ids) == ("list", frozenset({5}))
    assert load_seasoning_policy({FILE_ENV: str(path), MODE_ENV: "none"}).mode == "none"
    with pytest.raises(SeasoningConfigError, match="mode must be"):
        load_seasoning_policy({FILE_ENV: str(path), MODE_ENV: "bogus"})


def test_catalog_check_catches_unknown_ids_and_renamed_ingredients():
    catalog = {SALT: "소금", GARLIC: "마늘"}
    with pytest.raises(SeasoningConfigError) as error:
        validate_against_catalog(LIST, catalog)
    assert "id 103 is named '마늘'" in str(error.value)
    with pytest.raises(SeasoningConfigError, match="id 284 .* is not in the ingredient table"):
        validate_against_catalog(LIST, {GARLIC: "다진마늘"})
    validate_against_catalog(LIST, {SALT: "소금", GARLIC: "다진마늘"})
    validate_against_catalog(ASSUME_ALL, {})  # ids are unused outside list mode


def test_built_in_default_is_the_team_list_and_matches_the_legacy_names():
    policy = load_seasoning_policy({})
    assert policy.mode == "list" and len(policy.assumed_ids) == 10
    config = json.loads(DEFAULT_FILE.read_text(encoding="utf-8"))
    # D1 calls the pepper "후춧가루"; the table calls it "후추" (same synonym group).
    names = {("후춧가루" if e["name"] == "후추" else e["name"]) for e in config["assumed"]}
    assert names == set(constants.STAPLE_SEASONINGS)


def test_default_policy_validates_against_the_real_ingredient_table(real_catalog):
    validate_against_catalog(load_seasoning_policy({}), real_catalog)


# --- application ---------------------------------------------------------------------------


def test_app_start_fails_fast_on_a_list_that_does_not_fit_the_table(integration_db):
    settings = Settings.from_env({"RECIPE_DB_PATH": str(integration_db), "VISION_PROVIDER": "mock"})
    with patch("app.main.Settings.from_env", return_value=settings):
        with pytest.raises(SeasoningConfigError, match="does not match the ingredient table"):
            create_app_from_env()


def test_service_uses_the_configured_list_for_candidates(integration_repository):
    # In the integration data ingredient 4 is a seasoning in every recipe.
    body = {"ingredient_ids": [1, 2]}

    def missing(seasonings):
        service = RecommendationService(
            integration_repository, policy=RecommendationPolicy(seasonings=seasonings)
        )
        client = TestClient(
            create_app(StubVision(), integration_repository, recommendations=service)
        )
        recipes = client.post("/recipes/recommendations", json=body).json()["recipes"]
        return {r["recipe_id"]: r["filtering"]["missing_count"] for r in recipes}

    listed = SeasoningPolicy("list", frozenset({4}), {4: "Salt"})
    unlisted = SeasoningPolicy("list", frozenset({2}), {2: "Beta"})
    assert missing(listed) == missing(ASSUME_ALL)
    assert all(missing(unlisted)[r] == missing(listed)[r] + 1 for r in missing(listed) if r != 20)
