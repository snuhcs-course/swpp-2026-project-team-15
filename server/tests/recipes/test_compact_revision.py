"""Compact revision request, seasoning policy and deterministic post-check (no network)."""

import json
from dataclasses import asdict

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.recipes.policy import RecommendationPolicy
from app.recipes.recommendations import RecommendationService
from recipe_revision.compact import (
    SYSTEM_PROMPT_STAPLES,
    SYSTEM_PROMPT_STRICT,
    available_ids,
    build_compact_request,
    check_result,
)
from recipe_revision.core import LLMResponse, build_request, revise
from recipe_revision.models import InventoryIngredient, SourceIngredient, SourceRecipe, SourceStep
from recipe_revision.seasoning import ASSUME_ALL, ASSUME_NONE
from tests.conftest import StubVision

MAIN, SECONDARY, SEASONING = "3060001", "3060002", "3060003"
LABEL = {MAIN: "주재료", SECONDARY: "부재료", SEASONING: "양념"}


def ingredient(row_id, ingredient_id, name, code, quantity="1개", original=None):
    return SourceIngredient(
        row_id, ingredient_id, name, quantity, code, LABEL[code], original or name
    )


def recipe():
    return SourceRecipe(
        recipe_id=7,
        name="양파전",
        description="long description the model does not need",
        cuisine_type="한식",
        category="부침",
        cooking_time="30분",
        calories="165Kcal",
        servings="2인분",
        difficulty="쉬움",
        ingredients=(
            ingredient(1, 345, "양파", MAIN),
            ingredient(2, 147, "두부", SECONDARY),
            ingredient(3, 105, "소고기", SECONDARY, "50g", original="다진쇠고기"),
            ingredient(4, 284, "소금", SEASONING, "약간"),
            ingredient(5, 103, "다진마늘", SEASONING, None),
        ),
        steps=(
            SourceStep(11, 1, "양파를 썬다.", None),
            SourceStep(12, 2, "다진 쇠고기와 두부를 섞는다.", "물기를 꼭 짠다."),
            SourceStep(13, 3, "소금으로 간해 지진다.", None),
        ),
    )


def inventory(*pairs):
    return tuple(InventoryIngredient(i, n) for i, n in (*pairs, (204, "물")))


def test_compact_request_keeps_only_needed_fields():
    request = build_compact_request(recipe(), inventory((345, "양파"), (147, "두부")))
    original = json.loads(request.user)["original"]
    assert set(original) == {"name", "servings", "ingredients", "steps"}
    assert original["ingredients"][0] == {
        "recipe_ingredient_id": 1,
        "ingredient_id": 345,
        "name": "양파",
        "quantity_text": "1개",
        "role": "main",
        "status": "owned",
    }
    by_id = {row["ingredient_id"]: row for row in original["ingredients"]}
    assert by_id[105]["as_written"] == "다진쇠고기"  # kept only when it differs from name
    assert "as_written" not in by_id[345]
    assert "quantity_text" not in by_id[103]  # null fields are dropped
    assert "tip" not in original["steps"][0] and original["steps"][1]["tip"] == "물기를 꼭 짠다."
    assert [step["step_id"] for step in original["steps"]] == [11, 12, 13]
    for dropped in ("description", "calories", "difficulty", "ingredient_type"):
        assert dropped not in request.user
    assert json.loads(request.user)["inventory"] == [
        {"ingredient_id": 345, "name": "양파"},
        {"ingredient_id": 147, "name": "두부"},
        {"ingredient_id": 204, "name": "물"},
    ]


def test_compact_request_is_smaller_and_keeps_schema():
    items = inventory((345, "양파"))
    legacy = build_request(recipe(), items)
    compact = build_compact_request(recipe(), items)
    assert len(compact.user) < 0.7 * len(legacy.user)
    assert compact.to_dict()["output_schema"] == legacy.to_dict()["output_schema"]
    assert json.loads(legacy.user)["original"] == json.loads(json.dumps(asdict(recipe())))


def revised(ingredient_ids, steps):
    return {
        "can_revise": True,
        "reason": "",
        "changes": [],
        "revised_recipe": {
            "name": "양파전",
            "servings": "2인분",
            "ingredients": [
                {"ingredient_id": i, "name": str(i), "quantity_text": None} for i in ingredient_ids
            ],
            "steps": [
                {"step_number": n, "instruction": text, "tip": None}
                for n, text in enumerate(steps, 1)
            ],
        },
    }


def test_status_follows_seasoning_policy():
    items = inventory((345, "양파"))
    staples = json.loads(build_compact_request(recipe(), items, seasonings=ASSUME_ALL).user)
    strict = json.loads(build_compact_request(recipe(), items, seasonings=ASSUME_NONE).user)
    status = lambda payload: {  # noqa: E731
        row["ingredient_id"]: row["status"] for row in payload["original"]["ingredients"]
    }
    assert status(staples) == {
        345: "owned",
        147: "unavailable",
        105: "unavailable",
        284: "assumed",
        103: "assumed",
    }
    assert status(strict)[284] == "unavailable" and status(strict)[345] == "owned"
    assert build_compact_request(recipe(), items).system == SYSTEM_PROMPT_STAPLES
    assert (
        build_compact_request(recipe(), items, seasonings=ASSUME_NONE).system
        == SYSTEM_PROMPT_STRICT
    )
    assert "assumed" in SYSTEM_PROMPT_STAPLES and "assumed" not in SYSTEM_PROMPT_STRICT


def test_available_ids_by_policy():
    items = inventory((345, "양파"))
    assert available_ids(recipe(), items, seasonings=ASSUME_ALL) == {345, 204, 284, 103}
    assert available_ids(recipe(), items, seasonings=ASSUME_NONE) == {345, 204}


@pytest.mark.parametrize(
    "ids,steps,assume,expected",
    [
        ([345, 284], ["양파를 소금에 절여 지진다."], ASSUME_ALL, []),
        (
            [345, 284],
            ["양파를 소금에 절여 지진다."],
            ASSUME_NONE,
            ["unavailable_ingredient", "unavailable_in_steps"],
        ),
        (
            [345, 147],
            ["양파와 두부를 지진다."],
            ASSUME_ALL,
            ["unavailable_ingredient", "unavailable_in_steps"],
        ),
        ([345], ["양파를 지진다. 두부를 곁들인다."], ASSUME_ALL, ["unavailable_in_steps"]),
        ([345], ["양파를 지진다. 소금으로 간한다."], ASSUME_NONE, ["unavailable_in_steps"]),
        ([345], ["양파를 지진다. 소금으로 간한다."], ASSUME_ALL, []),
        ([345, 147], ["양파를 지진다."], ASSUME_ALL, ["unavailable_ingredient"]),
    ],
)
def test_check_result_known_answers(ids, steps, assume, expected):
    result = revised(ids, steps)
    assert check_result(result, recipe(), inventory((345, "양파")), seasonings=assume) == expected


def test_check_masks_available_names_and_skips_refusals():
    # "다진마늘" is available here; an unavailable "마늘" must not fire on its text.
    base = recipe()
    rows = base.ingredients + (ingredient(6, 169, "마늘", SECONDARY),)
    withgarlic = SourceRecipe(**{**asdict(base), "ingredients": rows, "steps": base.steps})
    items = inventory((345, "양파"), (103, "다진마늘"))
    result = revised([345, 103], ["다진마늘을 넣고 양파를 지진다."])
    assert check_result(result, withgarlic, items, seasonings=ASSUME_NONE) == []
    refusal = {"can_revise": False, "reason": "x", "changes": [], "revised_recipe": None}
    assert check_result(refusal, withgarlic, items) == []


class StubLLM:
    def __init__(self):
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        result = {"can_revise": False, "reason": "x", "changes": [], "revised_recipe": None}
        return LLMResponse(json.dumps({"result": result}))


def test_revise_defaults_to_the_full_row_request():
    llm = StubLLM()
    revise(recipe(), inventory((345, "양파")), llm)
    assert "description" in llm.requests[0].user
    revise(recipe(), inventory((345, "양파")), llm, build=build_compact_request)
    assert "description" not in llm.requests[1].user


class FixedLLM:
    def __init__(self, result):
        self.result = result
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return LLMResponse(json.dumps({"result": self.result}))


def test_revise_with_check_returns_check_failed_without_retry():
    llm = FixedLLM(revised([345, 147], ["두부를 지진다."]))
    outcome = revise(
        recipe(), inventory((345, "양파")), llm, build=build_compact_request, check=check_result
    )
    assert outcome.status == "check_failed" and len(llm.requests) == 1
    assert outcome.model_result is None
    assert (outcome.failure.code, outcome.failure.stage) == ("response_format", "revision")
    assert "unavailable_ingredient" in outcome.error
    unchecked = revise(recipe(), inventory((345, "양파")), llm, build=build_compact_request)
    assert unchecked.status == "revised"


def service_for(repository, llm, **policy):
    service = RecommendationService(
        repository, policy=RecommendationPolicy(**policy), llm_factory=lambda: llm
    )
    return TestClient(create_app(StubVision(), repository, recommendations=service))


def test_service_sends_the_compact_request(integration_repository):
    llm = StubLLM()
    service_for(integration_repository, llm).post(
        "/recipes/recommendations", json={"ingredient_ids": [1, 2]}
    )
    assert len(llm.requests) == 3
    assert all("recipe_id" not in json.loads(r.user)["original"] for r in llm.requests)


class ByRecipeLLM:
    """Noncompliant output for the first call, compliant for later calls."""

    def __init__(self):
        self.requests = []

    def generate(self, request):
        self.requests.append(json.loads(request.user))
        ids = [3] if len(self.requests) == 1 else [1]  # ingredient 3 is outside the inventory
        return LLMResponse(json.dumps({"result": revised(ids, ["Cook"])}))


def test_service_rejects_noncompliant_revision_and_continues(integration_repository):
    llm = ByRecipeLLM()
    body = (
        service_for(integration_repository, llm)
        .post("/recipes/recommendations", json={"ingredient_ids": [1, 2]})
        .json()
    )
    attempted = [e for e in body["recipes"] if e["revision"]["status"] != "not_attempted"]
    assert body["revision_summary"]["attempted_count"] == len(llm.requests) == 3
    failed = [e["revision"] for e in attempted if e["revision"]["status"] == "failed"]
    assert len(failed) == 1
    assert failed[0]["error"]["code"] == "response_format"
    assert failed[0]["error"]["stage"] == "revision"
    assert failed[0]["error"]["scope"] == "individual"
    assert sum(1 for e in attempted if e["revision"]["status"] == "revised") == 2
