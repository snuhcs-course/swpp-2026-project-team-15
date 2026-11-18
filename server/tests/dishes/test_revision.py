# AI-generated with Claude Code (Sonnet 5.5), 2026-11-18; reviewed by Jaehyuk Choi.
"""Recipe revision: availability by the server, one model call, a check without a model."""

import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.dishes.catalog import Catalog
from app.dishes.llm import DishLLMError
from app.dishes.recipes import RecipeStore
from app.dishes.revision import Reviser
from app.dishes.schemas import SourceRecipe
from app.dishes.service import DishService
from app.main import create_app
from tests.conftest import StubVision
from tests.dishes.test_dishes import STAPLES, FakeLLM

RECIPE = {
    "dish_id": "kimchi-fried-rice",
    "video": {"id": "abcdefghijk", "title": "김치볶음밥", "channel": "채널"},
    "source": "ai_structured_from_captions",
    "generated_at": "2026-11-18",
    "servings": 2,
    "ingredients": [
        {"name": "밥", "amount": "2공기", "role": "main"},
        {"name": "김치", "amount": "1컵", "role": "main"},
        {"name": "대파", "amount": "1대", "role": "secondary"},
        {"name": "계란", "amount": "2개", "role": "secondary"},
        {"name": "식용유", "amount": "2큰술", "role": "seasoning"},
    ],
    "steps": [
        {"n": 1, "text": "대파를 송송 썬다."},
        {"n": 2, "text": "기름에 대파를 볶다가 김치를 넣고 볶는다."},
        {"n": 3, "text": "밥을 넣어 볶고 계란 프라이를 올린다."},
    ],
    "tips": ["김치는 신 것이 좋다."],
}

GOOD = {
    "can_revise": True,
    "refusal_reason": "",
    "servings": 2,
    "ingredients": [
        {"name": "밥", "amount": "2공기"},
        {"name": "김치", "amount": "1컵"},
        {"name": "식용유", "amount": "2큰술"},
    ],
    "steps": ["기름에 김치를 볶는다.", "밥을 넣어 볶는다."],
    "tips": [],
    "changes": [
        {"reason": "대파가 없어서 뺐어요.", "ingredient_refs": [3], "step_refs": [1, 2]},
        {"reason": "계란이 없어서 뺐어요.", "ingredient_refs": [4], "step_refs": [3]},
    ],
}


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    return Catalog.load(staples=STAPLES)


def store() -> RecipeStore:
    return RecipeStore({"kimchi-fried-rice": SourceRecipe.model_validate(RECIPE)})


def service(catalog, *answers) -> tuple[DishService, FakeLLM]:
    llm = FakeLLM(*answers)
    recipes = store()
    reviser = Reviser(catalog, catalog, llm, recipes)
    return DishService(catalog, llm, None, recipes, reviser, catalog), llm


def revised(catalog, data, ingredients=("밥", "김치")):
    svc, _ = service(catalog, data)
    return svc.reviser.revise("kimchi-fried-rice", list(ingredients))


# --- store -----------------------------------------------------------------------------------


def test_store_loads_and_rejects_bad_files(tmp_path):
    path = tmp_path / "r.json"
    path.write_text(json.dumps({"schema": 1, "recipes": {"kimchi-fried-rice": RECIPE}}))
    assert "kimchi-fried-rice" in RecipeStore.load(path)
    assert len(RecipeStore.load(None)) == 0
    path.write_text(json.dumps({"schema": 2, "recipes": {}}))
    with pytest.raises(ValueError):
        RecipeStore.load(path)
    path.write_text(json.dumps({"schema": 1, "recipes": {"egg-roll": RECIPE}}))
    with pytest.raises(ValueError):
        RecipeStore.load(path)


# --- availability and the no-model path ------------------------------------------------------


def test_availability_marks_owned_assumed_unavailable(catalog):
    view = service(catalog)[0].reviser.view("kimchi-fried-rice", ["밥", "배추김치"])
    assert view.availability == ["owned", "owned", "unavailable", "unavailable", "assumed"]


def test_nothing_missing_needs_no_model_call(catalog):
    svc, _ = service(catalog)
    result = svc.reviser.revise("kimchi-fried-rice", ["밥", "김치", "대파", "달걀"])
    assert result.status == "revised" and result.changes == []
    assert [i.name for i in result.revised.ingredients][0] == "밥"


def test_unknown_dish_or_recipe_is_none(catalog):
    reviser = service(catalog)[0].reviser
    assert reviser.revise("nope", ["밥"]) is None
    assert reviser.revise("egg-roll", ["계란"]) is None


# --- the model answer and the check ----------------------------------------------------------


def test_good_answer_is_returned_with_numbered_steps(catalog):
    svc, llm = service(catalog, GOOD)
    result = svc.reviser.revise("kimchi-fried-rice", ["밥", "김치"])
    assert result.status == "revised"
    assert [s.n for s in result.revised.steps] == [1, 2]
    assert result.changes[0].ingredient_refs == [3]
    assert len(llm.calls) == 1
    sent = llm.calls[0][1]
    assert [r["status"] for r in sent["ingredients"]][2:4] == ["unavailable", "unavailable"]
    assert sent["owned"] == ["밥", "김치"]


def test_refusal_keeps_its_reason(catalog):
    data = {**GOOD, "can_revise": False, "refusal_reason": "김치가 없으면 김치볶음밥이 아니에요."}
    result = revised(catalog, data, ("밥", "계란"))
    assert result.status == "refused" and "김치" in result.refusal_reason
    assert result.revised is None


def test_refusal_without_reason_fails(catalog):
    result = revised(catalog, {**GOOD, "can_revise": False, "refusal_reason": " "})
    assert result.status == "failed" and result.error.code == "incomplete"


@pytest.mark.parametrize(
    ("patch", "code"),
    [
        (
            {"ingredients": GOOD["ingredients"] + [{"name": "참치캔", "amount": ""}]},
            "unavailable_ingredient",
        ),
        ({"steps": ["대파를 송송 썰어 볶는다.", "밥을 넣는다."]}, "mentions_unavailable"),
        ({"tips": ["계란을 올려도 좋다."]}, "mentions_unavailable"),
        ({"changes": [GOOD["changes"][0]]}, "unexplained_change"),
        ({"changes": [{"reason": "x", "ingredient_refs": [9], "step_refs": []}]}, "bad_reference"),
        ({"changes": [{"reason": "x", "ingredient_refs": [3], "step_refs": [7]}]}, "bad_reference"),
        (
            {"changes": [{"reason": " ", "ingredient_refs": [3], "step_refs": []}]},
            "unexplained_change",
        ),
        ({"steps": []}, "incomplete"),
        ({"ingredients": []}, "incomplete"),
    ],
)
def test_violations_are_failures_not_repairs(catalog, patch, code):
    result = revised(catalog, {**GOOD, **patch})
    assert result.status == "failed" and result.error.code == code
    assert result.revised is None


def test_synonym_names_count_as_owned_and_kept(catalog):
    data = {**GOOD, "ingredients": [{"name": "달걀", "amount": "1개"}] + GOOD["ingredients"]}
    data["changes"] = GOOD["changes"][:1] + [
        {"reason": "계란 대신 달걀을 써요.", "ingredient_refs": [4], "step_refs": []}
    ]
    assert revised(catalog, data, ("밥", "김치", "달걀")).status == "revised"


def test_model_failure_and_missing_model(catalog):
    svc, _ = service(catalog, DishLLMError("down"))
    with pytest.raises(DishLLMError):
        svc.reviser.revise("kimchi-fried-rice", ["밥"])
    with pytest.raises(DishLLMError):
        Reviser(catalog, catalog, None, store()).revise("kimchi-fried-rice", ["밥"])


def test_log_has_no_recipe_text_or_ingredients(catalog, caplog):
    with caplog.at_level(logging.INFO):
        revised(catalog, GOOD, ("밥", "김치", "특이한재료"))
        revised(catalog, {**GOOD, "steps": []})
    text = " ".join(r.getMessage() for r in caplog.records)
    assert "status=revised" in text and "status=failed" in text
    for secret in ("송송", "특이한재료", "2공기", "김치는 신"):
        assert secret not in text


# --- API ------------------------------------------------------------------------------------


def client(svc) -> TestClient:
    return TestClient(create_app(StubVision(), dishes=svc))


def test_api_recipe_view_and_revise(catalog):
    svc, _ = service(catalog, GOOD)
    c = client(svc)
    assert c.get("/dishes/kimchi-fried-rice/recipe").json()["servings"] == 2
    assert c.get("/dishes/egg-roll/recipe").status_code == 404
    view = c.post("/dishes/recipe", json={"dish_id": "kimchi-fried-rice", "ingredients": ["밥"]})
    assert view.json()["availability"][0] == "owned"
    body = {"dish_id": "kimchi-fried-rice", "ingredients": ["밥", "김치"]}
    out = c.post("/dishes/revise", json=body).json()
    assert out["status"] == "revised" and "AI가 만든 제안" in out["notice"]
    assert c.post("/dishes/revise", json={**body, "dish_id": "egg-roll"}).status_code == 404
    assert c.post("/dishes/revise", json={**body, "ingredients": []}).status_code == 422


def test_api_revise_returns_502_when_the_model_fails(catalog):
    svc, _ = service(catalog, DishLLMError("The model service is temporarily unavailable"))
    body = {"dish_id": "kimchi-fried-rice", "ingredients": ["밥"]}
    assert client(svc).post("/dishes/revise", json=body).status_code == 502


def test_suggest_marks_dishes_that_have_a_recipe(catalog):
    answer = {
        "dishes": [
            {"name": "김치볶음밥", "have": ["밥"], "missing": []},
            {"name": "계란말이", "have": [], "missing": []},
        ]
    }
    svc, _ = service(catalog, answer)
    flags = {d.name: d.has_recipe for d in svc.suggest(["밥"]).dishes}
    assert flags == {"김치볶음밥": True, "계란말이": False}
