# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Dish suggestions: closed list, deterministic have/missing, checked model answers (no network)."""

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


# --- suggest ---------------------------------------------------------------------------------


def test_rules_only_without_a_model(catalog):
    body = (
        client_for(DishService(catalog))
        .post("/dishes/suggest", json={"ingredients": ["김치", "밥"], "limit": 3})
        .json()
    )
    assert body["source"] == "rules" and len(body["dishes"]) == 3
    first = body["dishes"][0]
    assert first["reason"].startswith("필요한 재료") and first["videos"] == []
    assert first["search_url"].startswith("https://www.youtube.com/results?search_query=")


def test_model_choice_is_validated_and_have_missing_recomputed(catalog):
    llm = FakeLLM(
        {
            "dishes": [
                {"id": "does-not-exist", "reason": "x", "keywords": []},
                {
                    "id": "kimchi-fried-rice",
                    "reason": "김치와 밥이 있어요",
                    "keywords": [
                        "김치볶음밥 쉬운 레시피",
                        "아무 상관 없는 영상",
                        "김치볶음밥 레시피",
                    ],
                    "have": ["가짜"],  # ignored: the server recomputes have/missing
                    "missing": [],
                },
                {"id": "kimchi-fried-rice", "reason": "dup", "keywords": []},
            ]
        }
    )
    body = (
        client_for(DishService(catalog, llm))
        .post("/dishes/suggest", json={"ingredients": ["김치", "밥"], "limit": 1})
        .json()
    )
    assert body["source"] == "llm"
    dish = body["dishes"][0]
    assert dish["id"] == "kimchi-fried-rice"
    assert dish["have"] == ["밥", "김치"] and dish["missing"] == ["대파", "계란"]
    assert dish["keywords"] == ["김치볶음밥 쉬운 레시피", "김치볶음밥 레시피"]
    sent = llm.calls[0][1]
    assert all(c["id"] in catalog.dishes for c in sent["candidates"])


def test_model_failure_falls_back_to_rules(catalog):
    llm = FakeLLM(DishLLMError("down"))
    body = (
        client_for(DishService(catalog, llm))
        .post("/dishes/suggest", json={"ingredients": ["계란"]})
        .json()
    )
    assert body["source"] == "rules" and body["dishes"]


def test_all_unknown_model_ids_fall_back_to_rules(catalog):
    llm = FakeLLM({"dishes": [{"id": "x", "reason": "", "keywords": []}]})
    body = (
        client_for(DishService(catalog, llm))
        .post("/dishes/suggest", json={"ingredients": ["계란"]})
        .json()
    )
    assert body["source"] == "rules"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"ingredients": []},
        {"ingredients": ["계란"], "limit": 0},
        {"ingredients": ["계란"], "limit": 9},
    ],
)
def test_bad_suggest_input_is_422(catalog, payload):
    assert client_for(DishService(catalog)).post("/dishes/suggest", json=payload).status_code == 422


def test_list_endpoint(catalog):
    body = client_for(DishService(catalog)).get("/dishes").json()
    assert body["count"] == len(catalog) and body["dishes"][0].keys() >= {"id", "name", "category"}


# --- adapt -----------------------------------------------------------------------------------


def test_adapt_keeps_only_checked_items(catalog):
    llm = FakeLLM(
        {
            "substitutions": [
                {"missing": "대파", "suggestion": "양파로 대신해요", "uses": ["양파"]},
                {
                    "missing": "계란",
                    "suggestion": "두부를 으깨서 넣어요",
                    "uses": ["두부"],
                },  # not owned
                {"missing": "계란", "suggestion": "계란 2개 사용", "uses": ["양파"]},  # quantity
                {"missing": "김", "suggestion": "김 대신", "uses": ["양파"]},  # not missing
                {"missing": "대파", "suggestion": "중복", "uses": ["양파"]},
            ],
            "skip_ok": ["계란", "김"],
            "note": "양파가 있으면 충분해요",
        }
    )
    body = (
        client_for(DishService(catalog, llm))
        .post(
            "/dishes/adapt",
            json={"dish_id": "kimchi-fried-rice", "ingredients": ["밥", "김치", "양파"]},
        )
        .json()
    )
    assert body["source"] == "llm"
    assert body["substitutions"] == [
        {"missing": "대파", "suggestion": "양파로 대신해요", "uses": ["양파"]}
    ]
    assert body["skip_ok"] == ["계란"]
    assert body["note"] == "양파가 있으면 충분해요"


def test_adapt_rules_when_no_model_and_when_nothing_is_missing(catalog):
    client = client_for(DishService(catalog))
    body = client.post(
        "/dishes/adapt",
        json={"dish_id": "kimchi-fried-rice", "ingredients": ["밥", "김치", "양파"]},
    ).json()
    assert body["source"] == "rules"
    assert body["substitutions"][0] == {
        "missing": "대파",
        "suggestion": "양파(으)로 대신해요",
        "uses": ["양파"],
    }
    assert body["skip_ok"] == ["계란"]
    full = client.post("/dishes/adapt", json={"dish_id": "egg-fry", "ingredients": ["계란"]}).json()
    assert full["substitutions"] == [] and full["note"]


def test_adapt_errors(catalog):
    client = client_for(DishService(catalog, FakeLLM(DishLLMError("The model service is down"))))
    assert (
        client.post("/dishes/adapt", json={"dish_id": "nope", "ingredients": ["a"]}).status_code
        == 422
    )
    assert client.post("/dishes/adapt", json={"ingredients": ["a"]}).status_code == 422
    res = client.post(
        "/dishes/adapt", json={"dish_id": "kimchi-fried-rice", "ingredients": ["김치", "양파"]}
    )
    assert res.status_code == 502 and res.json()["detail"] == "The model service is down"


# --- substitutions only from the table -------------------------------------------------------


def _adapt(catalog, llm, dish_id, owned):
    client = client_for(DishService(catalog, llm))
    return client.post("/dishes/adapt", json={"dish_id": dish_id, "ingredients": owned}).json()


def test_adapt_rejects_a_substitution_the_table_does_not_allow(catalog):
    # 김 -> 김치 passed the old checks (owned, no quantity) but is not a table substitution.
    llm = FakeLLM(
        {
            "substitutions": [{"missing": "김", "suggestion": "김치로 대신해요", "uses": ["김치"]}],
            "skip_ok": ["김"],
            "note": "김치로 충분해요",
        }
    )
    body = _adapt(catalog, llm, "kimchi-rolled", ["김치", "밥", "간장", "소금"])
    assert body["substitutions"] == [] and body["skip_ok"] == []  # 김 is not optional here
    assert body["note"] == "냉장고 재료로는 마땅한 대체를 찾지 못했어요."
    assert llm.calls == []  # nothing the table allows, so the model is not even asked


def test_adapt_accepts_table_pairs_and_ignores_model_skip_claims(catalog):
    llm = FakeLLM(
        {
            "substitutions": [
                {"missing": "대파", "suggestion": "쪽파로 대신해요", "uses": ["양파"]},
                {"missing": "대파", "suggestion": "양파를 넣어요", "uses": ["양파", "소금"]},
            ],
            "skip_ok": ["계란", "김치"],  # the model cannot declare skips; only the table can
            "note": "양파가 있어요",
        }
    )
    body = _adapt(catalog, llm, "kimchi-fried-rice", ["밥", "김치", "양파"])
    assert body["substitutions"] == [
        {"missing": "대파", "suggestion": "쪽파로 대신해요", "uses": ["양파"]}
    ]
    assert body["skip_ok"] == ["계란"] and body["note"] == "양파가 있어요"
    assert llm.calls[0][1]["missing"] == [{"name": "대파", "allowed_uses": [["양파"]]}]


def test_adapt_replaces_a_model_pair_outside_the_table_with_the_table_option(catalog):
    llm = FakeLLM(
        {
            "substitutions": [{"missing": "대파", "suggestion": "김치로", "uses": ["김치"]}],
            "skip_ok": [],
            "note": "",
        }
    )
    body = _adapt(catalog, llm, "kimchi-fried-rice", ["밥", "김치", "양파"])
    assert body["substitutions"] == [
        {"missing": "대파", "suggestion": "양파(으)로 대신해요", "uses": ["양파"]}
    ]


def test_adapt_combo_and_optional_skip_without_any_model(catalog):
    body = _adapt(catalog, None, "tteokbokki", ["떡", "어묵", "고춧가루"])
    assert body["source"] == "rules"
    assert body["substitutions"] == [
        {
            "missing": "고추장",
            "suggestion": "고춧가루+간장+설탕(으)로 대신해요",
            "uses": ["고춧가루", "간장", "설탕"],
        }
    ]
    assert body["skip_ok"] == ["대파"]  # optional, and no table option with what is owned
    assert not catalog.accepts("고추장", ["양파"], catalog.owned(["양파"]))
    assert catalog.accepts("고추장", ["설탕", "고춧가루", "간장"], catalog.owned(["고춧가루"]))


def test_adapt_honest_empty_answer_without_a_model(catalog):
    body = _adapt(catalog, None, "kimchi-rolled", ["김치", "밥"])
    assert body["substitutions"] == [] and body["skip_ok"] == []
    assert body["note"] == "냉장고 재료로는 마땅한 대체를 찾지 못했어요."


def test_table_does_not_allow_tofu_egg_swaps(catalog):
    assert catalog.options("두부", catalog.owned(["계란"])) == []
    assert catalog.options("계란", catalog.owned(["두부"])) == []


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
    service = DishService(catalog, None, VideoCache(FIXTURE))
    body = (
        client_for(service)
        .post("/dishes/suggest", json={"ingredients": ["김치", "밥"], "limit": 8})
        .json()
    )
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
    body = client.post("/dishes/suggest", json={"ingredients": ["계란", "대파"]}).json()
    assert body["source"] == "rules" and body["dishes"]
