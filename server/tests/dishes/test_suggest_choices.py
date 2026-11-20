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
from app.dishes.dependencies import DishParts
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

    def complete(
        self, system: str, user: str, name: str, schema: dict, max_tokens: int | None = None
    ) -> dict:
        self.sent.append((system, user, name, schema, max_tokens))
        return self.answer


def _post(model: RecordingModel, ingredients: list[str]):
    client = TestClient(create_app(StubVision(), dishes=DishParts(DishService(CATALOG, model))))
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
    _, _, _, schema, _ = model.sent[0]
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
        create_app(
            StubVision(), dishes=DishParts(DishService(CATALOG, model, assumed=CATALOG.staples))
        )
    )
    assert client.post("/dishes/suggest", json={"ingredients": ["두부"]}).status_code == 200
    schema = model.sent[0][3]
    missing = schema["properties"]["dishes"]["items"]["properties"]["missing"]["items"]["enum"]
    assert "간장" not in missing and "참기름" not in missing


def test_a_runaway_answer_is_ordered_and_cut_to_the_list_limit():
    # Phone check 2026-11-19: 계란 + 밥 made the model list 118 dishes in 9.7 s (round 5).
    from app.dishes.answers import SUGGEST_LIMIT
    from app.dishes.prompts import SUGGEST_MAX_TOKENS

    # only dishes that use 계란 or 밥: the server drops the others (e2e_followups, item 1)
    names = [d.name for d in CATALOG.all() if CATALOG.uses(d, "계란") or CATALOG.uses(d, "밥")]
    answer = {
        "dishes": [
            {"name": n, "have": ["계란"], "missing": ["대파"] if i % 2 else []}
            for i, n in enumerate(names)
        ]
    }
    model = RecordingModel(answer)
    dishes = _post(model, ["계란", "밥"]).json()["dishes"]
    assert len(dishes) == SUGGEST_LIMIT < len(names)
    counts = [len(d["missing"]) for d in dishes]
    assert counts == sorted(counts)  # fewest missing kept first
    assert counts.count(0) == min(SUGGEST_LIMIT, (len(names) + 1) // 2)
    assert model.sent[0][4] == SUGGEST_MAX_TOKENS


def test_the_running_server_uses_one_owned_rule_for_cards_additions_and_recipes():
    # Server review (2026-11-19): with 햇반 the card could still list 밥 as missing while the
    # addition suggestions and the recipe view counted it as owned (23 of 50 Korean names).
    from app.config import Settings
    from app.dishes.dependencies import build_dish_parts

    parts = build_dish_parts(Settings.from_env({}))
    service = parts.service
    model = RecordingModel({"dishes": []})
    service.llm = model
    client = TestClient(create_app(StubVision(), dishes=parts))
    assert (
        client.post("/dishes/suggest", json={"ingredients": ["햇반", "삼겹살"]}).status_code == 200
    )
    missing = model.sent[0][3]["properties"]["dishes"]["items"]["properties"]["missing"]["items"]
    assert "밥" not in missing["enum"] and "돼지고기" not in missing["enum"]
    held = service.catalog.owned(["햇반", "쪽파"])
    assert service.catalog.status("밥", held) == "owned"
    assert service.catalog.status("대파", held) == "unavailable"  # a stand-in is not ownership


def test_dishes_that_use_none_of_the_fridge_are_dropped():
    # Phone test 2026-11-19: only 초콜릿 in the fridge gave 35 egg dishes with have=[초콜릿].
    names = [d.name for d in CATALOG.all()][:35]
    model = RecordingModel(
        {"dishes": [{"name": n, "have": ["초콜릿"], "missing": []} for n in names]}
    )
    assert _post(model, ["초콜릿"]).json()["dishes"] == []


def test_have_is_what_the_dish_uses_even_when_the_model_leaves_it_empty():
    # The served model listed 계란말이 for 양파·대파·감자 with have=[] although it uses 대파.
    model = RecordingModel({"dishes": [{"name": "계란말이", "have": [], "missing": ["계란"]}]})
    dish = _post(model, ["양파", "대파", "감자"]).json()["dishes"][0]
    assert dish["have"] == ["대파"]


def test_a_staple_alone_does_not_make_a_dish_use_the_fridge():
    dish = CATALOG.by_name("계란말이")
    assert not CATALOG.uses(dish, "초콜릿") and CATALOG.uses(dish, "달걀")
