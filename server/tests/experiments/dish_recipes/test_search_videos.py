# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
from experiments.dish_recipes.search_videos import kept_in_order, result_ids, search_params


def test_search_params_ask_for_embeddable_korean_videos_by_relevance():
    p = search_params("떡라면 레시피")
    assert p["q"] == "떡라면 레시피"
    assert p["type"] == "video" and p["videoEmbeddable"] == "true"
    assert p["order"] == "relevance" and p["relevanceLanguage"] == "ko" and p["regionCode"] == "KR"
    assert p["maxResults"] == 25


def test_result_ids_keep_order_and_skip_non_videos():
    payload = {
        "items": [
            {"id": {"kind": "youtube#video", "videoId": "aaaaaaaaaaa"}},
            {"id": {"kind": "youtube#channel", "channelId": "x"}},
            {"id": {"kind": "youtube#video", "videoId": "bbbbbbbbbbb"}},
        ]
    }
    assert result_ids(payload) == ["aaaaaaaaaaa", "bbbbbbbbbbb"]


def test_kept_in_order_takes_the_first_relevant_in_search_order_only():
    order = ["v1", "v2", "v3", "v4"]
    review = {
        "d|v1": {"decision": "irrelevant"},
        "d|v2": {"decision": "relevant"},
        "d|v3": {"decision": "unsure"},
        "d|v4": {"decision": "relevant"},
    }
    assert kept_in_order(order, review, "d", 5) == ["v2", "v4"]
    assert kept_in_order(order, review, "d", 1) == ["v2"]
    assert kept_in_order(order, {}, "d", 5) == []
