# AI-generated with Claude Code (Opus 5.5), 2026-11-20; reviewed by Jaehyuk Choi.
"""The pydantic-settings class: a handed-in mapping is the only source, names are case-free."""

from app.config import Settings


def test_a_mapping_is_the_only_source(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "from-process")
    assert Settings.from_env({}).youtube_api_key == ""
    assert Settings.from_env().youtube_api_key == "from-process"


def test_dish_key_falls_back_to_the_general_key_and_unknown_names_are_ignored():
    s = Settings.from_env({"openrouter_api_key": "general", "UNRELATED": "x"})
    assert s.dish_model_key == "general"
    assert (
        Settings.from_env({"DISH_LLM_API_KEY": " dish ", "OPENROUTER_API_KEY": "g"}).dish_model_key
        == "dish"
    )
