# AI-generated with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.
import pytest

from app.config import Settings


def test_settings_default_to_mock_provider():
    assert Settings.from_env({}).vision_provider == "mock"


@pytest.mark.parametrize(
    "env",
    [{"VISION_PROVIDER": "openai"}, {"VISION_PROVIDER": "gemini", "GEMINI_API_KEY": "k"}],
)
def test_settings_reject_invalid_configuration(env):
    with pytest.raises(ValueError):
        Settings.from_env(env)
