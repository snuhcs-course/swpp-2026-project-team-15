# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Dish suggestions: the model answers from names and owned ingredients; the server checks names."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.dishes.answers import search_url
from app.dishes.catalog import Catalog
from app.dishes.errors import DishLLMError, VideoError
from app.dishes.llm import DishLLM
from app.dishes.service import DishService
from app.dishes.video_search import REQUEST, WebSearchVideoSource, extract_ids
from app.dishes.video_store import VideoStore
from app.dishes.videos import VideoCache, VideoFinder
from app.dishes.youtube import YouTubeVerifier, to_video
from app.main import create_app
from tests.conftest import StubVision

STAPLES = frozenset({"물", "소금", "간장", "설탕", "후추", "식용유", "참기름", "다진마늘"})


class FakeLLM:
    """Scripted stand-in: returns the queued dict (or raises) and records the prompts."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []
        self.users: list[str] = []

    def complete(self, system, user, name, schema, max_tokens=None):
        self.users.append(user)
        self.calls.append((name, json.JSONDecoder().raw_decode(user)[0]))
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


def test_model_answer_is_checked_and_ordered_by_its_missing_count(catalog):
    llm = FakeLLM(
        _answer(
            ("존재하지 않는 요리", ["김치"], []),
            ("김치볶음밥", [" 밥 ", "김치", "김치"], ["대파", "계란"]),
            ("김치볶음밥", ["밥"], []),  # repeated name: dropped
            ("김치비빔밥", ["김치", "밥"], []),
        )
    )
    body = (
        client_for(DishService(catalog, llm))
        .post("/dishes/suggest", json={"ingredients": ["김치", "밥"], "limit": 1})
        .json()
    )
    assert body["source"] == "llm"
    # fewest missing first, nothing dropped, no cap
    assert [d["name"] for d in body["dishes"]] == ["김치비빔밥", "김치볶음밥"]
    first = body["dishes"][1]
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
    llm = FakeLLM(
        {"dishes": ["x", {"name": 3}, {"name": "김치비빔밥", "have": "밥", "missing": None}]}
    )
    body = (
        client_for(DishService(catalog, llm))
        .post("/dishes/suggest", json={"ingredients": ["김치"]})
        .json()
    )
    assert [d["name"] for d in body["dishes"]] == ["김치비빔밥"]
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
        {"missing": "대파", "suggestion": "양파로 대신해요", "uses": ["양파"]}
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
    client = client_for(DishService(catalog, index=catalog))
    names = client.get("/recipes/ingredients").json()["names"]
    assert names == sorted(set(names))
    for expected in ("김치", "쌀", "달걀", "대파", "소금", "양파", "참치캔"):
        assert expected in names
    assert all(0 < len(n) <= 12 and " " not in n and not any(c.isdigit() for c in n) for n in names)
    assert "물" not in names


def test_ingredient_suggestions_complete_the_most_dishes(catalog):
    client = client_for(DishService(catalog, index=catalog))
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


@pytest.fixture(autouse=True)
def _no_retry_wait(monkeypatch):
    monkeypatch.setattr("app.dishes.http.RETRY_WAITS", (0, 0))


def test_llm_keeps_the_complete_items_of_an_answer_cut_at_the_token_limit(caplog):
    cut = '{"dishes":[{"name":"김치볶음밥","have":["김치"],"missing":[]},{"name":"계란볶'

    def handler(request):
        return httpx.Response(
            200, json={"choices": [{"finish_reason": "length", "message": {"content": cut}}]}
        )

    with caplog.at_level("WARNING", logger="app.dishes.llm"):
        data = _llm(handler).complete("s", "u", "n", {"type": "object"})
    assert [d["name"] for d in data["dishes"]] == ["김치볶음밥"]
    assert any("cut at the token limit" in r.getMessage() for r in caplog.records)


def test_llm_retries_twice_when_the_service_limits_the_rate():
    answers = [
        httpx.Response(429),
        httpx.Response(429),
        httpx.Response(
            200,
            json={"choices": [{"finish_reason": "stop", "message": {"content": '{"dishes":[]}'}}]},
        ),
    ]
    assert _llm(lambda request: answers.pop(0)).complete("s", "u", "n", {}) == {"dishes": []}


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


def test_llm_logs_one_line_per_call_without_content_or_key(caplog):
    def handler(request):
        message = {"content": json.dumps({"dishes": []})}
        body = {
            "choices": [{"finish_reason": "stop", "message": message}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7},
        }
        return httpx.Response(200, json=body)

    with caplog.at_level("INFO", logger="app.dishes.llm"):
        _llm(handler).complete("system text", "user 김치볶음밥", "dish_choice", {"type": "object"})
    lines = [r.getMessage() for r in caplog.records if r.name == "app.dishes.llm"]
    assert len(lines) == 1
    assert "finish=stop" in lines[0] and "in=11" in lines[0] and "out=7" in lines[0]
    assert "김치" not in lines[0] and "test-key" not in lines[0] and "system text" not in lines[0]


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


# --- videos on request -----------------------------------------------------------------------

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)
IDS = ["a" * 11, "b" * 11, "c" * 11, "d" * 11]


def _item(vid, *, embeddable=True, privacy="public", thumb=True, size=("1000", "563")):
    snippet = {"title": f"title {vid[0]}", "channelTitle": "C"}
    if thumb:
        snippet["thumbnails"] = {"medium": {"url": f"https://i.ytimg.com/vi/{vid}/mq.jpg"}}
    item = {
        "id": vid,
        "snippet": snippet,
        "status": {"embeddable": embeddable, "privacyStatus": privacy},
    }
    if size is not None:
        item["player"] = {"embedWidth": size[0], "embedHeight": size[1]}
    return item


def _finder(
    calls,
    *,
    answer=None,
    items=None,
    openrouter_status=200,
    youtube_status=200,
    stored=None,
    cache=None,
    model=True,
    handler_wrap=None,
):
    """A VideoFinder whose two services are faked; ``calls`` records (host, payload/params)."""
    text = answer or " ".join(f"https://www.youtube.com/watch?v={v}" for v in IDS)
    listing = items if items is not None else [_item(v) for v in IDS]

    def handler(request):
        if request.url.host == "openrouter.ai":
            calls.append(("model", json.loads(request.content)))
            if openrouter_status != 200:
                return httpx.Response(openrouter_status)
            body = {"choices": [{"message": {"content": text, "annotations": []}}]}
            return httpx.Response(200, json=body)
        assert "yt-key" not in str(request.url)  # the key travels in a header, not in the URL
        assert request.headers["x-goog-api-key"] == "yt-key"
        calls.append(("youtube", dict(request.url.params)))
        if youtube_status != 200:
            return httpx.Response(youtube_status)
        return httpx.Response(200, json={"items": listing})

    transport = httpx.MockTransport(handler_wrap(handler) if handler_wrap else handler)
    return VideoFinder(
        YouTubeVerifier("yt-key", transport=transport),
        stored or VideoStore(),
        cache or VideoCache(),
        WebSearchVideoSource("or-key", transport=transport) if model else None,
        now=lambda: NOW,
    )


def test_request_text_is_the_wording_chosen_in_round_3():
    criteria = json.loads(
        (
            Path(__file__).parents[3] / "research/experiments/dish_pipeline/criteria_round3.json"
        ).read_text(encoding="utf-8")
    )
    assert REQUEST.format(dish="X") == criteria["exact_request_texts"]["D0"].replace("<dish>", "X")


def test_extract_ids_reads_text_then_citations_without_repeats():
    url = "https://www.youtube.com/watch?v="
    ids = extract_ids(
        f"{url}{'a' * 11} and https://youtu.be/{'b' * 11}", [f"{url}{'a' * 11}", f"{url}{'c' * 11}"]
    )
    assert ids == ["a" * 11, "b" * 11, "c" * 11]
    assert extract_ids("no links", []) == []


def test_finder_keeps_embeddable_public_videos_in_the_models_order():
    calls = []
    items = [
        _item(IDS[3]),  # the API returns another order than the model's
        _item(IDS[0]),
        _item(IDS[1], embeddable=False),
        _item(IDS[2], privacy="private"),
    ]
    finder = _finder(calls, items=items)
    videos = finder.lookup("kimchi-fried-rice", "김치볶음밥")[0]
    assert [v.video_id for v in videos] == [IDS[0], IDS[3]]
    assert videos[0].thumbnail_url.startswith("https://i.ytimg.com/")
    model_call = next(p for k, p in calls if k == "model")
    assert model_call["model"] == "google/gemini-2.5-flash-lite:online"
    assert "김치볶음밥" in model_call["messages"][0]["content"]
    youtube_calls = [p for k, p in calls if k == "youtube"]
    assert len(youtube_calls) == 1 and youtube_calls[0]["id"] == ",".join(IDS)  # one batch


def test_portrait_videos_are_dropped_and_sizes_compare_as_numbers():
    calls = []
    items = [
        _item(IDS[0], size=("563", "1000")),  # portrait (a Short)
        _item(IDS[1], size=("1000", "563")),  # landscape; as strings "563" > "1000"
        _item(IDS[2], size=("1000", "1000")),  # square stays
        _item(IDS[3], size=None),  # no size: kept, since it cannot be judged
    ]
    videos = _finder(calls, items=items).lookup("egg-roll", "계란말이")[0]
    assert [v.video_id for v in videos] == [IDS[1], IDS[2], IDS[3]]
    youtube_call = next(p for k, p in calls if k == "youtube")
    assert youtube_call["part"] == "snippet,status,player"
    assert youtube_call["maxWidth"] == "1000"


def test_finder_caches_a_dish_for_a_day():
    calls = []
    now = [1000.0]
    finder = _finder(calls, cache=VideoCache(clock=lambda: now[0]))
    finder.lookup("egg-roll", "계란말이")[0]
    finder.lookup("egg-roll", "계란말이")[0]
    assert len(calls) == 2  # one model call and one YouTube call
    now[0] += 24 * 3600 + 1
    finder.lookup("egg-roll", "계란말이")[0]
    assert len(calls) == 4


def test_finder_empty_answer_is_an_answer_and_a_thumbnail_is_built_when_missing():
    calls = []
    assert _finder(calls, answer="I found nothing").lookup("a", "A")[0] == []
    assert [k for k, _ in calls] == ["model"]  # nothing to look up
    video = to_video(_item("z" * 11, thumb=False))
    assert video.thumbnail_url == f"https://i.ytimg.com/vi/{'z' * 11}/mqdefault.jpg"
    assert to_video({"id": "z", "status": {"embeddable": False}}) is None


def test_finder_retries_a_rate_limited_model_call(monkeypatch):
    monkeypatch.setattr("app.dishes.http.RETRY_WAITS", (0, 0))
    state = {"n": 0}

    def limit_twice(handler):
        def wrapped(request):
            if request.url.host == "openrouter.ai":
                state["n"] += 1
                if state["n"] < 3:
                    return httpx.Response(429)
            return handler(request)

        return wrapped

    finder = _finder([], handler_wrap=limit_twice)
    assert len(finder.lookup("a", "A")[0]) == 4 and state["n"] == 3


@pytest.mark.parametrize(
    "kwargs", [{"openrouter_status": 500}, {"youtube_status": 403}], ids=["model", "youtube"]
)
def test_finder_failures_are_errors_without_keys(kwargs):
    with pytest.raises(VideoError) as raised:
        _finder([], **kwargs).lookup("a", "A")[0]
    assert "key" not in str(raised.value).lower()


def test_videos_endpoint(catalog):
    finder = _finder([])
    service = DishService(catalog, FakeLLM(), finder)
    client = client_for(service)
    body = client.post("/dishes/videos", json={"dish_id": "kimchi-fried-rice"}).json()
    assert [v["video_id"] for v in body["videos"]] == IDS
    assert "%EA%B9%80%EC%B9%98%EB%B3%B6%EC%9D%8C%EB%B0%A5" in body["search_url"]
    assert search_url("김치볶음밥").endswith("+%EB%A0%88%EC%8B%9C%ED%94%BC")
    assert client.post("/dishes/videos", json={"dish_id": "nope"}).status_code == 422
    assert client.post("/dishes/videos", json={}).status_code == 422
    no_finder = client_for(DishService(catalog, FakeLLM()))
    assert no_finder.post("/dishes/videos", json={"dish_id": "egg-roll"}).status_code == 502
    broken = client_for(DishService(catalog, FakeLLM(), _finder([], openrouter_status=500)))
    assert broken.post("/dishes/videos", json={"dish_id": "egg-roll"}).status_code == 502


def test_suggestions_carry_a_search_link_but_no_videos(catalog):
    llm = FakeLLM(_answer(("김치볶음밥", ["밥", "김치"], ["대파"])))
    body = (
        client_for(DishService(catalog, llm))
        .post("/dishes/suggest", json={"ingredients": ["김치", "밥"]})
        .json()
    )
    dish = body["dishes"][0]
    assert "videos" not in dish and dish["search_url"].startswith("https://www.youtube.com/")


def test_suggestions_carry_a_card_photo_without_asking_youtube(catalog):
    # Found on the phone (2026-11-19): a card showed its photo only after the dish was opened.
    from app.dishes.recipes import RecipeStore
    from app.dishes.schemas import SourceRecipe
    from tests.dishes.test_revision import RECIPE

    llm = FakeLLM(
        _answer(
            ("김치볶음밥", ["밥", "김치"], ["대파"]),
            ("계란말이", ["계란"], []),
            ("계란국", ["계란"], []),
        )
    )
    calls = []
    stored = VideoStore({"egg-roll": (NOW, [IDS[1], IDS[2]])})
    recipes = RecipeStore({"kimchi-fried-rice": SourceRecipe.model_validate(RECIPE)})
    service = DishService(catalog, llm, _finder(calls, stored=stored), recipes)
    body = (
        client_for(service)
        .post("/dishes/suggest", json={"ingredients": ["김치", "밥", "계란"]})
        .json()
    )
    photos = {d["id"]: d["thumbnail_url"] for d in body["dishes"]}
    assert (
        photos["kimchi-fried-rice"]
        == f"https://i.ytimg.com/vi/{RECIPE['video']['id']}/mqdefault.jpg"
    )
    assert photos["egg-roll"] == f"https://i.ytimg.com/vi/{IDS[1]}/mqdefault.jpg"
    assert photos["egg-soup"] is None  # nothing stored and no recipe
    assert calls == []  # neither the model search nor YouTube was asked


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/dishes/suggest", {"ingredients": ["가" * 21]}),
        ("/dishes/adapt", {"dish_id": "egg-roll", "ingredients": ["계란"], "missing": ["가" * 21]}),
        ("/dishes/recipe", {"dish_id": "egg-roll", "ingredients": ["가" * 21]}),
        ("/dishes/revise", {"dish_id": "egg-roll", "ingredients": ["가" * 21]}),
        ("/recipes/ingredient-suggestions", {"ingredients": ["가" * 21]}),
        ("/recipes/ingredient-suggestions", {"ingredients": ["계란"] * 61}),
    ],
)
def test_an_overlong_name_or_list_is_refused_before_any_model_call(catalog, path, body):
    # Server review (2026-11-19): a 10,000-character name added about 5,000 paid prompt tokens.
    from app.dishes.recipes import RecipeStore
    from app.dishes.revision import Reviser

    llm, recipes = FakeLLM(), RecipeStore()
    service = DishService(
        catalog, llm, None, recipes, Reviser(catalog, catalog, llm, recipes), catalog
    )
    assert client_for(service).post(path, json=body).status_code == 422
    assert llm.calls == []


def test_the_longest_real_name_is_accepted(catalog):
    llm = FakeLLM(_answer(("김치볶음밥", ["밥", "김치"], [])))
    body = {"ingredients": ["모둠버섯(표고, 느타리, 새송이버섯)", "밥", "김치"]}
    assert (
        client_for(DishService(catalog, llm)).post("/dishes/suggest", json=body).status_code == 200
    )


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


# --- stored videos ---------------------------------------------------------------------------


def _stored(fetched=NOW - timedelta(days=3), ids=None, dish="egg-roll"):
    entry = {"fetched_at": fetched.isoformat(), "videos": [{"id": v} for v in (ids or IDS[:3])]}
    return VideoStore.load_data({"schema": 1, "dishes": {dish: entry}})


def test_stored_videos_are_checked_again_and_served_without_the_model():
    calls = []
    finder = _finder(calls, stored=_stored(), items=[_item(v) for v in IDS[:3]])
    videos, source = finder.lookup("egg-roll", "계란말이")
    assert source == "stored" and [v.video_id for v in videos] == IDS[:3]
    assert [k for k, _ in calls] == ["youtube"]  # one lookup, no model call


def test_stored_videos_that_were_deleted_or_closed_are_dropped_in_order():
    calls = []
    items = [_item(IDS[2]), _item(IDS[0], embeddable=False)]  # IDS[1] is gone, IDS[0] is closed
    videos, source = _finder(calls, stored=_stored(), items=items).lookup("egg-roll", "계란말이")
    assert source == "stored" and [v.video_id for v in videos] == [IDS[2]]
    assert [k for k, _ in calls] == ["youtube"]


def test_stored_videos_older_than_thirty_days_are_not_served():
    calls = []
    finder = _finder(calls, stored=_stored(fetched=NOW - timedelta(days=30), ids=[IDS[3]]))
    videos, source = finder.lookup("egg-roll", "계란말이")
    assert source == "discovered" and [k for k, _ in calls] == ["model", "youtube"]
    assert [v.video_id for v in videos] == IDS  # what the model proposed, not the stored list


def test_everything_stored_is_gone_so_the_model_is_asked():
    calls = []

    def without_first(handler):
        def wrapped(request):
            if request.url.host != "openrouter.ai":
                ids = [v for v in request.url.params["id"].split(",") if v != IDS[0]]
                calls.append(("youtube", ids))
                return httpx.Response(200, json={"items": [_item(v) for v in ids]})
            return handler(request)

        return wrapped

    finder = _finder(calls, stored=_stored(ids=[IDS[0]]), handler_wrap=without_first)
    videos, source = finder.lookup("egg-roll", "계란말이")
    assert source == "discovered" and IDS[0] not in [v.video_id for v in videos]
    assert [k for k, _ in calls] == ["youtube", "model", "youtube"]


def test_youtube_failure_while_checking_stored_videos_is_an_error():
    with pytest.raises(VideoError):
        _finder([], stored=_stored(), youtube_status=403).lookup("egg-roll", "계란말이")


def test_stored_path_works_without_a_model_but_discovery_does_not():
    finder = _finder([], stored=_stored(), items=[_item(v) for v in IDS[:3]], model=False)
    assert finder.lookup("egg-roll", "계란말이")[1] == "stored"
    with pytest.raises(VideoError):
        finder.lookup("unknown-dish", "없는요리")


def test_videos_endpoint_reports_where_the_list_came_from(catalog):
    finder = _finder([], stored=_stored(), items=[_item(v) for v in IDS[:3]])
    body = (
        client_for(DishService(catalog, FakeLLM(), finder))
        .post("/dishes/videos", json={"dish_id": "egg-roll"})
        .json()
    )
    assert body["source"] == "stored" and len(body["videos"]) == 3


def test_ties_keep_the_model_order(catalog):
    llm = FakeLLM(
        _answer(
            ("김치볶음밥", ["김치", "밥"], ["대파"]),
            ("김치비빔밥", ["김치", "밥"], ["계란"]),
            ("김치주먹밥", ["김치", "밥"], []),
        )
    )
    body = (
        client_for(DishService(catalog, llm))
        .post("/dishes/suggest", json={"ingredients": ["김치", "밥"]})
        .json()
    )
    assert [d["name"] for d in body["dishes"]] == ["김치주먹밥", "김치볶음밥", "김치비빔밥"]
