# AI-generated with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.

# Modified with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
# Changes: Drop the recipe database and revision settings.
# Modified with Claude Code (Opus 5.5), 2026-11-20: one pydantic-settings class for every variable.

"""Settings read from environment variables (see server/.env.example and deploy/README.md).

The running app reads the process environment once (``Settings.from_env()``); a test or a script
hands in a mapping instead, which is then the only source. Names are the variable names, any case.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

VisionProvider = Literal["mock", "gemini", "openrouter"]

SERVER_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(frozen=True, extra="ignore", case_sensitive=False)

    vision_provider: VisionProvider = "mock"
    gemini_api_key: str = ""
    gemini_model: str = ""
    openrouter_api_key: str = ""
    openrouter_vision_model: str = ""
    # Dish suggestions, revisions and the video search; the key falls back to OPENROUTER_API_KEY.
    dish_llm_api_key: str = ""
    dish_llm_model: str = ""
    youtube_api_key: str = ""
    dish_videos: str = ""
    dish_recipes: str = ""
    # Usage data for the beta week; collection is off when unset.
    telemetry_file: str = ""

    @property
    def vision_fixture_dir(self) -> Path:
        return SERVER_DIR / "fixtures" / "vision"

    @property
    def dish_model_key(self) -> str:
        """The key for the dish model and the video search: DISH_LLM_API_KEY, else the general
        one. The one place this rule is written, so both calls always use the same key."""
        return self.dish_llm_api_key.strip() or self.openrouter_api_key.strip()

    @model_validator(mode="after")
    def _provider_has_its_settings(self) -> "Settings":
        if self.vision_provider == "gemini" and not (self.gemini_api_key and self.gemini_model):
            raise ValueError("VISION_PROVIDER=gemini requires GEMINI_API_KEY and GEMINI_MODEL")
        if self.vision_provider == "openrouter" and not (
            self.openrouter_api_key and self.openrouter_vision_model
        ):
            raise ValueError(
                "OpenRouter vision requires OPENROUTER_API_KEY and OPENROUTER_VISION_MODEL"
            )
        return self

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        """The process environment, or only ``env`` when one is given. Raises ValueError (a
        pydantic ValidationError) for an unknown provider or a provider without its keys."""
        if env is None:
            return cls()
        fields = cls.model_fields
        values: dict[str, Any] = {k.lower(): v for k, v in env.items() if k.lower() in fields}
        return _FromMapping(**values)


class _FromMapping(Settings):
    """Settings whose only source is the keyword arguments: no process environment."""

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (init_settings,)
