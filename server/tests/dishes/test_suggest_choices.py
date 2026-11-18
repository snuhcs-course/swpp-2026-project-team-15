# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""The suggestion answer is limited to the request's closed lists; an owned ingredient is never
returned as missing."""

from fastapi.testclient import TestClient

from app.dishes.catalog import Catalog
from app.dishes.choices import (
    ingredient_vocabulary,
    owned_vocabulary,
    suggest_choices,
    user_items,
)
from app.dishes.prompts import SUGGEST_CLOSED_SYSTEM, suggest_request, suggest_schema
from app.dishes.service import DishService
from app.main import create_app
from tests.conftest import StubVision

CATALOG = Catalog.load()
VOCAB = ingredient_vocabulary(CATALOG.all())
NAMES = [d.name for d in CATALOG.all()]


class RecordingModel:
    """Returns a scripted answer and keeps what it was sent."""

    def __init__(self, answer: dict):
        self.answer = answer
        self.sent: list[tuple] = []

    def complete(self, system: str, user: str, name: str, schema: dict) -> dict:
        self.sent.append((system, user, name, schema))
        return self.answer


def _post(model: RecordingModel, ingredients: list[str]):
    client = TestClient(create_app(StubVision(), dishes=DishService(CATALOG, model)))
    return client.post("/dishes/suggest", json={"ingredients": ingredients})


def _dish_props(schema: dict) -> dict:
    return schema["properties"]["dishes"]["items"]["properties"]


def test_vocabulary_has_one_spelling_per_synonym_group():
    assert VOCAB == sorted(set(VOCAB))
    assert "계란" in VOCAB and "달걀" not in VOCAB and "참치캔" in VOCAB


def test_owned_vocabulary_uses_spelling_and_synonym_groups_only():
    items = user_items([" 달걀", "달걀", "참치 통조림", "다진마늘", ""])
    assert items == ["달걀", "참치 통조림", "다진마늘"]
    assert owned_vocabulary(items, VOCAB) == {"계란", "참치캔"}
    missing = suggest_choices(items, NAMES, VOCAB).missing
    assert "계란" not in missing and "참치캔" not in missing and "마늘" in missing
    assert len(missing) == len(VOCAB) - 2


def test_schema_closes_names_have_and_missing():
    props = _dish_props(suggest_schema(suggest_choices(["김치", "밥"], NAMES, VOCAB)))
    assert props["name"]["enum"] == NAMES
    assert props["have"]["items"]["enum"] == ["김치", "밥"]
    assert {"김치", "밥"}.isdisjoint(props["missing"]["items"]["enum"])


def test_an_empty_choice_list_allows_only_an_empty_array():
    choices = suggest_choices(["밥"], NAMES, ["밥"])
    assert _dish_props(suggest_schema(choices))["missing"] == {"type": "array", "maxItems": 0}


def test_request_uses_the_closed_prompt_and_the_user_items():
    request = suggest_request(suggest_choices([" 계란", "계란", "밥"], NAMES, VOCAB))
    assert request.system == SUGGEST_CLOSED_SYSTEM and request.name == "dish_choice"
    assert '"owned": ["계란", "밥"]' in request.user


def test_service_sends_the_per_request_schema():
    model = RecordingModel({"dishes": []})
    assert _post(model, ["계란", "밥"]).status_code == 200
    _, _, _, schema = model.sent[0]
    missing = _dish_props(schema)["missing"]["items"]["enum"]
    assert "계란" not in missing and "밥" not in missing and "대파" in missing


def test_owned_ingredient_is_never_returned_as_missing():
    # Regression: a provider that ignores the schema must not make an owned item "missing".
    answer = {
        "dishes": [
            {"name": "계란볶음밥", "have": ["달걀", "밥", "치즈"], "missing": ["계란", "대파"]},
        ]
    }
    dish = _post(RecordingModel(answer), ["달걀", "밥"]).json()["dishes"][0]
    assert dish["missing"] == ["대파"]  # 계란 is owned as 달걀
    assert dish["have"] == ["달걀", "밥"]  # 치즈 is not one of the user's items


def test_assumed_staples_are_not_missing_choices():
    choices = suggest_choices(["두부"], NAMES, VOCAB, CATALOG.staples)
    assert "간장" in VOCAB and "간장" not in choices.missing
    assert not set(choices.missing) & CATALOG.staples
    assert "대파" in choices.missing


def test_the_running_service_leaves_staples_out_of_the_missing_choices():
    model = RecordingModel({"dishes": []})
    client = TestClient(
        create_app(StubVision(), dishes=DishService(CATALOG, model, assumed=CATALOG.staples))
    )
    assert client.post("/dishes/suggest", json={"ingredients": ["두부"]}).status_code == 200
    schema = model.sent[0][3]
    missing = schema["properties"]["dishes"]["items"]["properties"]["missing"]["items"]["enum"]
    assert "간장" not in missing and "참기름" not in missing
