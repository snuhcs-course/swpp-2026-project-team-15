# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
import json

import pytest
from experiments.dish_recipes import run_video_recipes as run
from experiments.dish_recipes import validate_recipe
from experiments.dish_recipes import video_recipes as vr

VIDEO = {"id": "abcdefghijk", "title": "김치볶음밥 만들기", "channel": "채널"}


def answer(**over):
    base = {
        "is_requested_dish": True,
        "cooked_dish": "김치볶음밥",
        "servings": 0,
        "ingredients": [
            {"name": "김치", "amount": "1컵", "role": "main", "evidence": "both"},
            {"name": "밥", "amount": "", "role": "main", "evidence": "seen"},
            {"name": " ", "amount": "", "role": "seasoning", "evidence": "heard"},
        ],
        "steps": ["김치를 볶는다.", " ", "밥을 넣고 섞는다."],
        "tips": ["", "약불로"],
        "uncertain": [],
    }
    base.update(over)
    return base


def test_payload_sends_the_youtube_link_to_google_ai_studio_only():
    payload = vr.build_payload("김치볶음밥", "abcdefghijk", "google/gemini-2.5-flash-lite")
    part = payload["messages"][1]["content"][1]
    assert part == {
        "type": "video_url",
        "video_url": {"url": "https://www.youtube.com/watch?v=abcdefghijk"},
    }
    assert payload["provider"] == {"only": ["google-ai-studio"], "allow_fallbacks": False}
    assert payload["response_format"]["json_schema"]["strict"] is True


def test_payload_rejects_anything_that_is_not_a_video_id():
    with pytest.raises(ValueError):
        vr.build_payload("김치볶음밥", 'x" onerror=', "m")


def test_to_recipe_cleans_the_answer_into_the_stored_format():
    recipe = vr.to_recipe("kimchi-fried-rice", VIDEO, answer(), "2026-11-19")
    assert recipe["source"] == "ai_structured_from_video"
    assert [i["name"] for i in recipe["ingredients"]] == ["김치", "밥"]
    assert recipe["ingredients"][1]["amount"] is None
    assert recipe["servings"] is None
    assert recipe["steps"] == [
        {"n": 1, "text": "김치를 볶는다."},
        {"n": 2, "text": "밥을 넣고 섞는다."},
    ]
    assert recipe["tips"] == ["약불로"]
    assert validate_recipe.check_recipe(recipe, None) == []


def test_to_recipe_returns_nothing_when_the_video_cooks_another_dish():
    assert (
        vr.to_recipe("pork-bowl", VIDEO, answer(is_requested_dish=False, cooked_dish="제육볶음"))
        is None
    )


def test_parse_response_reports_errors_without_raising():
    assert vr.parse_response({"error": {"message": "bad"}}).ok is False
    body = {"choices": [{"finish_reason": "stop", "message": {"content": "not json"}}]}
    assert vr.parse_response(body).error == "answer is not JSON"
    good = {
        "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(answer())}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 2, "cost": 0.01},
        "provider": "Google AI Studio",
    }
    call = vr.parse_response(good, 1.5)
    assert call.ok and call.cost_usd == 0.01 and call.provider == "Google AI Studio"


def test_caption_based_recipes_still_need_their_captions():
    recipe = vr.to_recipe("kimchi-fried-rice", VIDEO, answer(), "2026-11-19")
    recipe["source"] = "ai_structured_from_captions"
    assert validate_recipe.check_recipe(recipe, None) == [
        "captions not found: cannot check the ingredients"
    ]


def test_agreement_merges_synonyms_and_spaces():
    video = {"ingredients": [{"name": "달걀"}, {"name": "김 치"}, {"name": "파"}]}
    captions = {"ingredients": [{"name": "계란"}, {"name": "김치"}, {"name": "양파"}]}
    precision, recall, extra, missed = run.agreement(video, captions)
    assert (round(precision, 2), round(recall, 2)) == (0.67, 0.67)
    assert extra == {run.canonical("파")} and missed == {run.canonical("양파")}


def test_main_agreement_counts_shared_ingredients_only():
    video = {"ingredients": [{"name": "밥", "role": "main"}, {"name": "깨", "role": "seasoning"}]}
    captions = {"ingredients": [{"name": "밥", "role": "secondary"}]}
    assert run.main_agreement(video, captions) == (1, 0)


def test_workdir_must_be_outside_the_repository(tmp_path):
    with pytest.raises(SystemExit):
        run.outside_repo(run.REPO_ROOT / "data")
    assert run.outside_repo(tmp_path) == tmp_path.resolve()
