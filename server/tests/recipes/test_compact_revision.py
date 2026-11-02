"""Compact revision request (no network)."""

import json
from dataclasses import asdict

from fastapi.testclient import TestClient

from app.main import create_app
from app.recipes.policy import RecommendationPolicy
from app.recipes.recommendations import RecommendationService
from recipe_revision.compact import build_compact_request
from recipe_revision.core import SYSTEM_PROMPT, LLMResponse, build_request, revise
from recipe_revision.models import InventoryIngredient, SourceIngredient, SourceRecipe, SourceStep
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


def test_compact_request_is_smaller_and_keeps_prompt_and_schema():
    items = inventory((345, "양파"))
    legacy = build_request(recipe(), items)
    compact = build_compact_request(recipe(), items)
    assert len(compact.user) < 0.7 * len(legacy.user)
    assert compact.system == legacy.system == SYSTEM_PROMPT
    assert compact.to_dict() == {**legacy.to_dict(), "messages": compact.to_dict()["messages"]}
    assert json.loads(legacy.user)["original"] == json.loads(json.dumps(asdict(recipe())))


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


def service_for(repository, llm, **policy):
    service = RecommendationService(
        repository, policy=RecommendationPolicy(**policy), llm_factory=lambda: llm
    )
    return TestClient(create_app(StubVision(), repository, recommendations=service))


def test_service_flag_selects_request_form(integration_repository):
    compact, legacy = StubLLM(), StubLLM()
    body = {"ingredient_ids": [1, 2]}
    service_for(integration_repository, compact).post("/recipes/recommendations", json=body)
    service_for(integration_repository, legacy, compact_revision=False).post(
        "/recipes/recommendations", json=body
    )
    assert len(compact.requests) == len(legacy.requests) == 3
    assert all("recipe_id" not in json.loads(r.user)["original"] for r in compact.requests)
    assert all("recipe_id" in json.loads(r.user)["original"] for r in legacy.requests)
