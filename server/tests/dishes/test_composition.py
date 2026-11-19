# AI-generated with Claude Code (Sonnet 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""The composition root picks the concrete classes from the settings; services never do."""

import json

import pytest

from app.dishes.dependencies import build_chat_model, build_dish_parts, build_video_finder
from app.dishes.llm import DishLLM
from app.dishes.video_search import WebSearchVideoSource
from app.dishes.youtube import YouTubeVerifier


def test_no_keys_means_no_model_and_no_video_finder():
    parts = build_dish_parts({})
    assert parts.service.llm is None and parts.service.finder is None
    assert parts.reviser is not None and parts.index is not None
    assert len(parts.service.catalog) > 100
    # Server review (2026-11-19): the service no longer carries the router's reviser and index.
    assert not hasattr(parts.service, "reviser") and not hasattr(parts.service, "index")


def test_a_model_key_builds_the_model_client_and_the_model_is_shared_with_the_reviser():
    parts = build_dish_parts({"DISH_LLM_API_KEY": "k"})
    assert isinstance(parts.service.llm, DishLLM) and parts.reviser.llm is parts.service.llm


def test_general_model_key_is_the_fallback():
    assert isinstance(build_chat_model({}, "fallback"), DishLLM)
    assert build_chat_model({}, "  ") is None


def test_video_finder_needs_a_youtube_key_and_a_model_key_only_for_discovery():
    assert build_video_finder({}, "model-key") is None
    stored_only = build_video_finder({"YOUTUBE_API_KEY": "y"})
    assert isinstance(stored_only._verifier, YouTubeVerifier) and stored_only._source is None
    full = build_video_finder({"YOUTUBE_API_KEY": "y"}, "model-key")
    assert isinstance(full._source, WebSearchVideoSource)


def test_data_files_are_read_at_startup_and_a_bad_one_stops_it(tmp_path):
    bad = tmp_path / "videos.json"
    bad.write_text(json.dumps({"schema": 9}), encoding="utf-8")
    with pytest.raises(ValueError):
        build_dish_parts({"YOUTUBE_API_KEY": "y", "DISH_VIDEOS": str(bad)})
    with pytest.raises(OSError):
        build_dish_parts({"DISH_RECIPES": str(tmp_path / "missing.json")})


def test_the_built_service_assumes_the_catalog_staples():
    service = build_dish_parts({}).service
    assert service.assumed == service.catalog.staples and "간장" in service.assumed


def test_the_reviser_matches_recipe_rows_with_the_name_table():
    # Phone check 2026-11-19: 꽃소금 in a video recipe was shown missing next to 소금.
    from app.dishes.recipe_names import RecipeNames

    reviser = build_dish_parts({}).reviser
    assert isinstance(reviser.index, RecipeNames)
    assert reviser.index.status("꽃소금", reviser.index.owned([])) == "assumed"


def test_the_dish_model_and_the_video_search_use_the_same_key():
    # Server review (2026-11-19): the fallback rule was written twice.
    parts = build_dish_parts({"DISH_LLM_API_KEY": "dish", "YOUTUBE_API_KEY": "y"}, "general")
    assert parts.service.llm._api_key == parts.service.finder._source._api_key == "dish"
    parts = build_dish_parts({"YOUTUBE_API_KEY": "y"}, "general")
    assert parts.service.llm._api_key == parts.service.finder._source._api_key == "general"
