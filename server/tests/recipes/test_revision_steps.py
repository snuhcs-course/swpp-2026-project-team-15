# AI-generated with Claude Code (Sonnet 5.5), 2026-11-03; human review pending.
"""Steps around one revision call: a refusal decided in code, and a completed change list."""

import json

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.recipes.policy import RecommendationPolicy
from app.recipes.recommendations import RecommendationService
from app.recipes.schemas import RecommendationsRequest
from recipe_revision.changes import complete_changes
from recipe_revision.core import LLMResponse, _validate, output_schema
from recipe_revision.models import InventoryIngredient, SourceIngredient, SourceRecipe, SourceStep
from recipe_revision.pipeline import Steps, revise_with_steps
from recipe_revision.prescreen import missing_identity_names, prescreen_refusal
from tests.conftest import StubVision

MAIN, SECONDARY, SEASONING = "3060001", "3060002", "3060003"
LABEL = {MAIN: "주재료", SECONDARY: "부재료", SEASONING: "양념"}


def row(row_id, ingredient_id, name, code, original=None):
    return SourceIngredient(row_id, ingredient_id, name, "1개", code, LABEL[code], original or name)


def make_recipe(name="양파전", rows=None, steps=None, recipe_id=7):
    rows = rows or (
        row(1, 345, "양파", MAIN),
        row(2, 147, "두부", SECONDARY),
        row(3, 129, "대파", SECONDARY),
        row(4, 284, "소금", SEASONING),
    )
    steps = steps or (
        SourceStep(11, 1, "양파를 썬다.", None),
        SourceStep(12, 2, "두부와 대파를 섞어 지진다.", None),
    )
    return SourceRecipe(recipe_id, name, None, None, None, None, None, "2인분", None, rows, steps)


def inventory(*pairs):
    return tuple(InventoryIngredient(i, n) for i, n in (*pairs, (204, "물")))


def success(ingredient_rows, steps, changes=()):
    return {
        "can_revise": True,
        "reason": "ok",
        "changes": list(changes),
        "revised_recipe": {
            "name": "양파전",
            "servings": "2인분",
            "ingredients": [
                {"ingredient_id": i, "name": n, "quantity_text": None} for i, n in ingredient_rows
            ],
            "steps": [
                {"step_number": k, "instruction": text, "tip": None}
                for k, text in enumerate(steps, 1)
            ],
        },
    }


class ScriptedLLM:
    """Returns the given results in order and records the requests."""

    def __init__(self, *results):
        self.results, self.requests = list(results), []

    def generate(self, request):
        self.requests.append(request)
        result = self.results.pop(0)
        usage = {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110}
        return LLMResponse(json.dumps({"result": result}), {"usage": usage})


# --- prescreen ---------------------------------------------------------------------------------


def test_prescreen_refuses_when_a_dish_name_ingredient_is_unavailable():
    recipe = make_recipe()
    refusal = prescreen_refusal(recipe, inventory((147, "두부"), (129, "대파")))
    assert (
        refusal["can_revise"] is False and refusal["changes"] == [] and "양파" in refusal["reason"]
    )
    _validate({"result": refusal}, output_schema())  # same shape the model must produce
    assert prescreen_refusal(recipe, inventory((345, "양파"))) is None


def test_prescreen_ignores_other_missing_ingredients_and_counts_synonyms_as_one():
    assert prescreen_refusal(make_recipe(), inventory((345, "양파"))) is None
    eggs = make_recipe("계란말이", (row(1, 10, "계란", MAIN), row(2, 129, "대파", SECONDARY)))
    assert missing_identity_names(eggs, inventory((11, "달걀"), (129, "대파"))) == []
    assert missing_identity_names(eggs, inventory((129, "대파"))) == ["계란"]


# --- completed change list ---------------------------------------------------------------------


def test_complete_changes_explains_every_removal_and_keeps_the_schema():
    recipe = make_recipe()
    result = success([(345, "양파"), (147, "두부")], ["양파를 썬다.", "두부를 지진다."])
    completed, added = complete_changes(result, recipe)
    assert added == 2  # 대파 and 소금 were removed without a change entry
    assert {tuple(c["source_ingredient_row_ids"]) for c in completed["changes"]} == {(3,), (4,)}
    assert all(c["kind"] == "omission" for c in completed["changes"])
    _validate({"result": completed}, output_schema())
    declared = success(
        [(345, "양파"), (147, "두부"), (284, "소금")],
        ["양파를 썬다."],
        [
            {
                "kind": "omission",
                "reason": "대파 없음",
                "source_ingredient_row_ids": [3],
                "source_step_ids": [],
            }
        ],
    )
    assert complete_changes(declared, recipe) == (declared, 0)
    refusal = {"can_revise": False, "reason": "x", "changes": [], "revised_recipe": None}
    assert complete_changes(refusal, recipe) == (refusal, 0)


# --- pipeline ----------------------------------------------------------------------------------

BAD = success([(345, "양파"), (9999, "설탕")], ["양파를 썬다."])
GOOD = success([(345, "양파")], ["양파를 썬다."])


def test_pipeline_prescreen_makes_no_model_call():
    llm = ScriptedLLM()
    outcome = revise_with_steps(make_recipe(), inventory((147, "두부")), llm, Steps())
    assert llm.requests == [] and outcome.status == "refused"
    assert outcome.provider_metadata == {"model_calls": 0, "prescreen": True}


def test_pipeline_rejects_an_answer_that_fails_the_check():
    llm = ScriptedLLM(BAD)
    outcome = revise_with_steps(
        make_recipe(), inventory((345, "양파")), llm, Steps(prescreen=False)
    )
    assert outcome.status == "check_failed" and len(llm.requests) == 1
    assert outcome.failure.code == "response_format" and outcome.failure.stage == "revision"


def test_pipeline_completes_changes_on_a_delivered_revision():
    llm = ScriptedLLM(GOOD)
    inv = inventory((345, "양파"))
    outcome = revise_with_steps(make_recipe(), inv, llm, Steps(prescreen=False))
    assert outcome.status == "revised" and outcome.provider_metadata["changes_completed"] == 3
    assert len(outcome.model_result["changes"]) == 3


# --- service and policy ------------------------------------------------------------------------


class FakeRepository:
    """Serves fixed recipes; the service only calls load_catalog."""

    def __init__(self, recipes, inventory_rows):
        self.recipes, self.inventory_rows = recipes, inventory_rows

    def load_catalog(self, ingredient_ids, water_id):
        return list(self.recipes), tuple(self.inventory_rows)


def catalog_recipes():
    # 버섯볶음 has the fewest missing ingredients (only 버섯, named in the dish) so it ranks first.
    mushroom = make_recipe(
        "버섯볶음",
        (
            row(1, 10, "돼지고기", MAIN),
            row(2, 11, "양파", SECONDARY),
            row(3, 12, "당근", SECONDARY),
            row(4, 13, "버섯", SECONDARY),
        ),
        recipe_id=1,
    )
    onion = make_recipe(
        "양파볶음",
        (
            row(5, 10, "돼지고기", MAIN),
            row(6, 11, "양파", SECONDARY),
            row(7, 12, "당근", SECONDARY),
            row(8, 14, "청양고추", SECONDARY),
            row(9, 15, "파프리카", SECONDARY),
        ),
        recipe_id=2,
    )
    pork = make_recipe(
        "돼지볶음",
        (
            row(10, 10, "돼지고기", MAIN),
            row(11, 11, "양파", SECONDARY),
            row(12, 12, "당근", SECONDARY),
            row(13, 16, "마늘종", SECONDARY),
            row(14, 17, "브로콜리", SECONDARY),
        ),
        recipe_id=3,
    )
    return [mushroom, onion, pork]


class CountingLLM:
    def __init__(self):
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        refusal = {"can_revise": False, "reason": "x", "changes": [], "revised_recipe": None}
        return LLMResponse(json.dumps({"result": refusal}))


def recommend(prescreen, limit):
    repository = FakeRepository(
        catalog_recipes(), inventory((10, "돼지고기"), (11, "양파"), (12, "당근"))
    )
    llm = CountingLLM()
    policy = RecommendationPolicy(prescreen=prescreen)
    service = RecommendationService(repository, policy=policy, llm_factory=lambda: llm)
    body = service.recommend(
        RecommendationsRequest(ingredient_ids=[10, 11, 12], revision_limit=limit)
    )
    return body, llm


def test_service_prescreen_refuse_keeps_the_slot_and_fill_uses_the_next_candidate():
    off, llm_off = recommend("off", 1)
    assert len(llm_off.requests) == 1
    refuse, llm_refuse = recommend("refuse", 1)
    first = next(e for e in refuse.recipes if e.recipe_id == 1)
    assert first.revision.status == "refused" and "버섯" in first.revision.result.reason
    assert llm_refuse.requests == []
    fill, llm_fill = recommend("fill", 1)
    assert len(llm_fill.requests) == 1  # the limit counts model calls
    assert fill.revision_summary.selected_count == 2 and fill.revision_summary.limit == 1
    statuses = {e.recipe_id: e.revision.status for e in fill.recipes}
    assert statuses[1] == "refused" and statuses[2] == "refused" and statuses[3] == "not_attempted"


def test_policy_defaults_and_validation():
    default = RecommendationPolicy()
    assert (default.prescreen, default.complete_changes) == ("refuse", True)
    assert default.revision_workers == 1
    with pytest.raises(ValueError, match="prescreen"):
        RecommendationPolicy(prescreen="always")


def test_http_service_still_returns_the_public_shape_with_all_steps(integration_repository):
    service = RecommendationService(
        integration_repository,
        policy=RecommendationPolicy(),
        llm_factory=lambda: CountingLLM(),
    )
    client = TestClient(create_app(StubVision(), integration_repository, recommendations=service))
    body = client.post("/recipes/recommendations", json={"ingredient_ids": [1, 2]}).json()
    assert body["revision_summary"]["attempted_count"] == 3
    assert {e["revision"]["status"] for e in body["recipes"]} <= {"refused", "not_attempted"}
