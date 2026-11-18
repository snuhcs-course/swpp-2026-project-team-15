# AI-generated with Claude Code (Sonnet 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""The composition root picks the concrete classes from the settings; services never do."""

import json

import pytest

from app.dishes.dependencies import build_chat_model, build_dish_service, build_video_finder
from app.dishes.llm import DishLLM
from app.dishes.video_search import WebSearchVideoSource
from app.dishes.youtube import YouTubeVerifier


def test_no_keys_means_no_model_and_no_video_finder():
    service = build_dish_service({})
    assert service.llm is None and service.finder is None
    assert service.reviser is not None and service.index is not None and len(service.catalog) > 100


def test_a_model_key_builds_the_model_client_and_the_model_is_shared_with_the_reviser():
    service = build_dish_service({"DISH_LLM_API_KEY": "k"})
    assert isinstance(service.llm, DishLLM) and service.reviser.llm is service.llm


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
        build_dish_service({"YOUTUBE_API_KEY": "y", "DISH_VIDEOS": str(bad)})
    with pytest.raises(OSError):
        build_dish_service({"DISH_RECIPES": str(tmp_path / "missing.json")})
