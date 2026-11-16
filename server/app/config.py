# AI-generated with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.

# Modified with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
# Changes: Drop the recipe database and revision settings.

"""Settings read from environment variables (see server/.env.example)."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

SERVER_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    vision_provider: Literal["mock", "gemini", "openrouter"]
    vision_fixture_dir: Path
    gemini_api_key: str
    gemini_model: str
    openrouter_api_key: str = ""
    openrouter_vision_model: str = ""

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "Settings":
        provider = env.get("VISION_PROVIDER", "mock")
        if provider not in ("mock", "gemini", "openrouter"):
            raise ValueError(
                f"VISION_PROVIDER must be 'mock', 'gemini' or 'openrouter', got {provider!r}"
            )
        settings = cls(
            vision_provider=provider,
            vision_fixture_dir=SERVER_DIR / "fixtures" / "vision",
            gemini_api_key=env.get("GEMINI_API_KEY", ""),
            gemini_model=env.get("GEMINI_MODEL", ""),
            openrouter_api_key=env.get("OPENROUTER_API_KEY", ""),
            openrouter_vision_model=env.get("OPENROUTER_VISION_MODEL", ""),
        )
        if provider == "gemini" and not (settings.gemini_api_key and settings.gemini_model):
            raise ValueError("VISION_PROVIDER=gemini requires GEMINI_API_KEY and GEMINI_MODEL")
        if provider == "openrouter" and not (
            settings.openrouter_api_key and settings.openrouter_vision_model
        ):
            raise ValueError(
                "OpenRouter vision requires OPENROUTER_API_KEY and OPENROUTER_VISION_MODEL"
            )
        return settings
