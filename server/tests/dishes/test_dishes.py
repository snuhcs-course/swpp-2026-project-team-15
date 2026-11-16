# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Dish suggestions: the model answers from names and owned ingredients; the server checks names."""

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.dishes.catalog import Catalog
from app.dishes.llm import DishLLM, DishLLMError
from app.dishes.service import DishService
from app.dishes.youtube import (
    VideoCache,
    YouTubeClient,
    prefetch,
    search_url,
    to_video,
    top_videos,
)
from app.main import create_app
from tests.conftest import StubVision

FIXTURE = Path(__file__).parent / "fixtures" / "sample_video_cache.json"
STAPLES = frozenset({"물", "소금", "간장", "설탕", "후추", "식용유", "참기름", "다진마늘"})


class FakeLLM:
    """Scripted stand-in: returns the queued dict (or raises) and records the prompts."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []

    def complete(self, system, user, name, schema):
        self.calls.append((name, json.loads(user)))
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    return Catalog.load(staples=STAPLES)


def client_for(service: DishService) -> TestClient:
    return TestClient(create_app(StubVision(), dishes=service))


# --- data and matching -----------------------------------------------------------------------


def test_baseline_list_is_valid(catalog):
    assert len(catalog) >= 100
    for dish in catalog.dishes.values():
        assert 1 <= len(dish.key_ingredients) <= 6
        assert dish.optional <= set(dish.key_ingredients)


def test_have_and_missing_are_computed_from_key_ingredients(catalog):
    owned = catalog.owned(["김치", "쌀", "돼지고기"])  # 쌀 stands in for 밥
    match = catalog.match(catalog.get("pork-kimchi-fried-rice"), owned)
    assert match.have == ("밥", "김치", "돼지고기")
    assert match.missing == ("양파",)


def test_synonyms_and_staples(catalog):
    owned = catalog.owned(["달걀", "파"])
    match = catalog.match(catalog.get("egg-roll"), owned)
    assert "계란" in match.have and "대파" in match.have
    assert catalog.match(catalog.get("egg-fry"), owned).missing == ()  # 식용유 is a staple
    garlic = catalog.match(catalog.get("pork-belly-kimchi"), catalog.owned(["돼지고기", "김치"]))
    assert garlic.missing == ()  # 마늘 is covered by the staple 다진마늘


def test_rules_rank_fewest_missing_first_and_need_one_owned_item(catalog):
    ranked = catalog.rank(["계란", "대파"])
    assert ranked and all(m.have for m in ranked)
    assert [len(m.missing) for m in ranked] == sorted(len(m.missing) for m in ranked)
    assert catalog.rank(["우주식량"]) == []


# --- suggest (naive: the model answers, the server checks the names) -------------------------


def _answer(*dishes):
    return {"dishes": [{"name": n, "have": h, "missing": m} for n, h, m in dishes]}


def test_model_answer_is_returned_as_written_after_the_name_check(catalog):
    llm = FakeLLM(
        _answer(
            ("존재하지 않는 요리", ["김치"], []),
            ("김치볶음밥", [" 밥 ", "김치", "김치"], ["대파", "계란"]),
            ("김치볶음밥", ["밥"], []),  # repeated name: dropped
            ("김치죽", ["김치", "밥"], []),
        )
    )
    body = (
        client_for(DishService(catalog, llm))
        .post("/dishes/suggest", json={"ingredients": ["김치", "밥"], "limit": 1})
        .json()
    )
    assert body["source"] == "llm"
    assert [d["name"] for d in body["dishes"]] == ["김치볶음밥", "김치죽"]  # order kept, no cap
    first = body["dishes"][0]
    assert first["id"] == "kimchi-fried-rice"
    assert first["have"] == ["밥", "김치"] and first["missing"] == ["대파", "계란"]
    assert first["search_url"].startswith("https://www.youtube.com/results?search_query=")
    assert "reason" not in first and "keywords" not in first


def test_model_sees_only_names_and_owned_ingredients(catalog):
    llm = FakeLLM({"dishes": []})
    client_for(DishService(catalog, llm)).post(
        "/dishes/suggest", json={"ingredients": ["김치", "밥"]}
    )
    sent = llm.calls[0][1]
    assert set(sent) == {"owned", "dishes"} and sent["owned"] == ["김치", "밥"]
    assert sent["dishes"] == [d.name for d in catalog.dishes.values()]


def test_empty_model_answer_is_an_answer_not_an_error(catalog):
    body = (
        client_for(DishService(catalog, FakeLLM({"dishes": []})))
        .post("/dishes/suggest", json={"ingredients": ["소금"]})
        .json()
    )
    assert body == {"source": "llm", "dishes": []}


def test_malformed_model_items_are_skipped(catalog):
    llm = FakeLLM({"dishes": ["x", {"name": 3}, {"name": "김치죽", "have": "밥", "missing": None}]})
    body = (
        client_for(DishService(catalog, llm))
        .post("/dishes/suggest", json={"ingredients": ["김치"]})
        .json()
    )
    assert [d["name"] for d in body["dishes"]] == ["김치죽"]
    assert body["dishes"][0]["have"] == [] and body["dishes"][0]["missing"] == []


def test_model_failure_and_missing_model_are_502_without_fallback(catalog):
    failing = client_for(DishService(catalog, FakeLLM(DishLLMError("The model service is down"))))
    response = failing.post("/dishes/suggest", json={"ingredients": ["계란"]})
    assert response.status_code == 502 and "down" in response.json()["detail"]
    none = client_for(DishService(catalog)).post("/dishes/suggest", json={"ingredients": ["계란"]})
    assert none.status_code == 502


@pytest.mark.parametrize("payload", [{}, {"ingredients": []}, {"ingredients": ["a"] * 61}])
def test_bad_suggest_input_is_422(catalog, payload):
    assert client_for(DishService(catalog)).post("/dishes/suggest", json=payload).status_code == 422


def test_list_endpoint(catalog):
    body = client_for(DishService(catalog)).get("/dishes").json()
    assert body["count"] == len(catalog) and body["dishes"][0].keys() >= {"id", "name", "category"}


# --- adapt (naive: the model names a substitute from the user's own ingredients) --------------


def _adapt(catalog, llm, owned, missing, dish_id="egg-roll"):
    client = client_for(DishService(catalog, llm))
    return client.post(
        "/dishes/adapt", json={"dish_id": dish_id, "ingredients": owned, "missing": missing}
    )


def test_adapt_keeps_substitutes_that_come_from_the_owned_list(catalog):
    llm = FakeLLM(
        {
            "substitutions": [
                {"missing": "대파", "substitute": "양파"},
                {"missing": "계란", "substitute": "두부"},  # not owned: dropped
                {"missing": "당근", "substitute": "양파"},  # not asked: dropped
                {"missing": "대파", "substitute": "양파"},  # repeated: dropped
            ]
        }
    )
    body = _adapt(catalog, llm, ["양파", "밥"], ["대파", "계란"]).json()
    assert body["source"] == "llm" and body["note"] == "" and body["skip_ok"] == []
    assert body["substitutions"] == [
        {"missing": "대파", "suggestion": "양파(으)로 대신해요", "uses": ["양파"]}
    ]
    assert llm.calls[0][1] == {
        "dish": "계란말이",
        "missing": ["대파", "계란"],
        "owned": ["양파", "밥"],
    }


def test_adapt_empty_answer_gives_the_honest_note(catalog):
    llm = FakeLLM({"substitutions": [{"missing": "대파", "substitute": ""}]})
    body = _adapt(catalog, llm, ["양파"], ["대파"]).json()
    assert body["substitutions"] == [] and body["note"].startswith("냉장고 재료로는")


def test_adapt_nothing_missing_needs_no_model_and_errors_are_clear(catalog):
    llm = FakeLLM()
    body = _adapt(catalog, llm, ["양파"], []).json()
    assert body["note"] == "부족한 재료가 없어요." and llm.calls == []
    assert _adapt(catalog, FakeLLM(), ["양파"], ["대파"], "nope").status_code == 422
    assert _adapt(catalog, None, ["양파"], ["대파"]).status_code == 502
    assert _adapt(catalog, FakeLLM(DishLLMError("down")), ["양파"], ["대파"]).status_code == 502
    bad = client_for(DishService(catalog)).post(
        "/dishes/adapt", json={"dish_id": "egg-roll", "ingredients": []}
    )
    assert bad.status_code == 422


# --- names and additions without the recipe database -----------------------------------------


def test_ingredient_names_come_from_the_dish_data(catalog):
    client = client_for(DishService(catalog))
    names = client.get("/recipes/ingredients").json()["names"]
    assert names == sorted(set(names))
    for expected in ("김치", "쌀", "달걀", "대파", "소금", "양파", "참치캔"):
        assert expected in names
    assert all(0 < len(n) <= 12 and " " not in n and not any(c.isdigit() for c in n) for n in names)
    assert "물" not in names


def test_ingredient_suggestions_complete_the_most_dishes(catalog):
    client = client_for(DishService(catalog))
    body = client.post("/recipes/ingredient-suggestions", json={"ingredients": ["밥", "김치"]})
    suggestions = body.json()["suggestions"]
    assert suggestions and len(suggestions) <= 5
    assert all(s["ready_recipe_count"] >= 1 and s["ready_recipe_names"] for s in suggestions)
    assert [s["ready_recipe_count"] for s in suggestions] == sorted(
        (s["ready_recipe_count"] for s in suggestions), reverse=True
    )
    assert not {"밥", "김치"} & {s["name"] for s in suggestions}  # only things not yet owned
    empty = client.post("/recipes/ingredient-suggestions", json={"ingredients": []})
    assert empty.status_code == 200 and empty.json() == {"suggestions": []}


# --- model transport -------------------------------------------------------------------------


def _llm(handler) -> DishLLM:
    return DishLLM("test-key", transport=httpx.MockTransport(handler))


def test_llm_parses_a_strict_json_answer_and_never_leaks_the_key():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        message = {"content": json.dumps({"dishes": []})}
        return httpx.Response(
            200, json={"choices": [{"finish_reason": "stop", "message": message}]}
        )

    assert _llm(handler).complete("s", "u", "n", {"type": "object"}) == {"dishes": []}
    assert seen["body"]["temperature"] == 0
    assert seen["body"]["response_format"]["json_schema"]["strict"] is True


@pytest.mark.parametrize("status", [429, 500, 400])
def test_llm_errors_are_safe(status):
    def handler(request):
        return httpx.Response(status, text="secret test-key echoed")

    with pytest.raises(DishLLMError) as err:
        _llm(handler).complete("s", "u", "n", {})
    assert "test-key" not in str(err.value)


def test_llm_bad_payloads():
    for response in (
        httpx.Response(
            200, json={"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]}
        ),
        httpx.Response(
            200, json={"choices": [{"finish_reason": "stop", "message": {"content": "not json"}}]}
        ),
        httpx.Response(200, json={}),
    ):
        with pytest.raises(DishLLMError):
            _llm(lambda request, r=response: r).complete("s", "u", "n", {})


# --- YouTube cache and prefetch --------------------------------------------------------------


def test_cache_is_optional_and_expires():
    assert VideoCache(None).get("kimchi-fried-rice") == []
    assert VideoCache("/nonexistent/path.json").get("kimchi-fried-rice") == []
    cache = VideoCache(FIXTURE)
    assert [v["video_id"] for v in cache.get("kimchi-fried-rice")] == [
        "FAKE_TEST_ID_01",
        "FAKE_TEST_ID_02",
    ]
    assert cache.get("egg-roll") == []  # older than 30 days


def test_videos_and_search_link_in_suggestions(catalog):
    llm = FakeLLM(_answer(("김치볶음밥", ["밥", "김치"], ["대파"])))
    service = DishService(catalog, llm, VideoCache(FIXTURE))
    body = client_for(service).post("/dishes/suggest", json={"ingredients": ["김치", "밥"]}).json()
    dish = next(d for d in body["dishes"] if d["id"] == "kimchi-fried-rice")
    assert [v["video_id"] for v in dish["videos"]] == ["FAKE_TEST_ID_01", "FAKE_TEST_ID_02"]
    assert dish["videos"][0]["embeddable"] is True
    assert "%EA%B9%80%EC%B9%98%EB%B3%B6%EC%9D%8C%EB%B0%A5" in dish["search_url"]
    assert search_url("김치볶음밥").endswith("+%EB%A0%88%EC%8B%9C%ED%94%BC")


def _youtube_handler(calls):
    def handler(request):
        calls.append(request.url.path)
        assert "key=" in str(request.url)
        if request.url.path.endswith("/search"):
            return httpx.Response(200, json={"items": [{"id": {"videoId": v}} for v in "abcd"]})
        items = [
            {
                "id": "a",
                "snippet": {
                    "title": "초간단 김치 볶음밥",
                    "channelTitle": "C",
                    "thumbnails": {"medium": {"url": "u"}},
                },
                "statistics": {"viewCount": "10"},
                "status": {"embeddable": True, "privacyStatus": "public"},
            },
            {
                "id": "b",
                "snippet": {"title": "B 김치볶음밥 레시피", "channelTitle": "C"},
                "statistics": {"viewCount": "500"},
                "status": {"embeddable": True, "privacyStatus": "public"},
            },
            {
                "id": "c",
                "snippet": {"title": "C"},
                "statistics": {"viewCount": "900"},
                "status": {"embeddable": False, "privacyStatus": "public"},
            },
            {
                "id": "d",
                "snippet": {"title": "D"},
                "statistics": {},
                "status": {"embeddable": True},
            },
        ]
        return httpx.Response(200, json={"items": items})

    return handler


def test_top_videos_prefers_titles_that_name_the_dish_then_views():
    calls = []
    client = YouTubeClient("k", transport=httpx.MockTransport(_youtube_handler(calls)))
    videos = top_videos(client, "김치볶음밥")
    # c is not embeddable; b and a name the dish (more views first), d only fills up
    assert [v["video_id"] for v in videos] == ["b", "a", "d"]
    assert videos[1]["thumbnail_url"] == "u" and videos[0]["thumbnail_url"].startswith(
        "https://i.ytimg.com/"
    )
    assert to_video({"id": "z", "status": {"embeddable": False}}) is None
    assert client.requests == 2


def test_prefetch_dry_run_then_fake_live(tmp_path):
    cache = VideoCache(tmp_path / "videos.json")
    dishes = [
        ("kimchi-fried-rice", "김치볶음밥"),
        ("egg-roll", "계란말이"),
        ("egg-fry", "계란후라이"),
    ]
    plan = prefetch(dishes, cache, None, max_requests=4)
    assert plan["will_fetch"] == 2 and plan["quota_units"] == 202 and plan["fetched"] == 0
    assert not (tmp_path / "videos.json").exists()  # a dry run writes nothing
    calls = []
    client = YouTubeClient("k", transport=httpx.MockTransport(_youtube_handler(calls)))
    done = prefetch(dishes, cache, client, max_requests=4, sleep=lambda s: None)
    assert done["fetched"] == 2 and len(calls) == 4
    assert VideoCache(tmp_path / "videos.json").get("kimchi-fried-rice")
    again = prefetch(dishes, VideoCache(tmp_path / "videos.json"), None, max_requests=40)
    assert again["to_fetch"] == 1  # the two fetched dishes are fresh


def test_prefetch_stops_on_quota_error(tmp_path):
    def handler(request):
        return httpx.Response(403, json={"error": "quota"})

    client = YouTubeClient("k", transport=httpx.MockTransport(handler))
    log = []
    summary = prefetch(
        [("a", "A"), ("b", "B")],
        VideoCache(tmp_path / "v.json"),
        client,
        max_requests=10,
        sleep=lambda s: None,
        log=log.append,
    )
    assert summary["failed"] == 1 and len(log) == 1  # stopped after the first 403
    assert "k" not in "".join(log).replace("HTTP", "")


# --- start from the environment -------------------------------------------------------------


def test_app_starts_from_the_environment_without_any_database(monkeypatch):
    from app.main import create_app_from_env

    for name in ("OPENROUTER_API_KEY", "DISH_LLM_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("VISION_PROVIDER", "mock")
    client = TestClient(create_app_from_env())
    assert client.get("/ready").json() == {"status": "ready"}
    assert client.get("/dishes").json()["count"] >= 100
    assert client.post("/recipes/recommend", json={"ingredients": ["계란"]}).status_code == 404
    response = client.post("/dishes/suggest", json={"ingredients": ["계란", "대파"]})
    assert response.status_code == 502  # no key, no model, no fallback
