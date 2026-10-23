# AI-generated with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.

# Modified with Codex (GPT-6.1 Sol), 2026-10-17; reviewed by Soohyun An.
# Changes: Load Revision provider settings and credentials from environment variables.

"""Settings read from environment variables (see server/.env.example)."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

SERVER_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVER_DIR.parent


@dataclass(frozen=True)
class Settings:
    vision_provider: Literal["mock", "gemini", "openrouter"]
    recipe_db_path: Path
    vision_fixture_dir: Path
    gemini_api_key: str
    gemini_model: str
    revision_provider: str = "mock"
    revision_llm_endpoint: str = ""
    revision_llm_model: str = ""
    revision_llm_api_key: str = ""

    database_url: str = ""
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
            recipe_db_path=REPO_ROOT
            / env.get("RECIPE_DB_PATH", "data/recipes-iter2/recipes.sqlite3"),
            vision_fixture_dir=SERVER_DIR / "fixtures" / "vision",
            gemini_api_key=env.get("GEMINI_API_KEY", ""),
            gemini_model=env.get("GEMINI_MODEL", ""),
            revision_provider=env.get("REVISION_PROVIDER", "mock"),
            revision_llm_endpoint=env.get("REVISION_LLM_ENDPOINT", ""),
            revision_llm_model=env.get("REVISION_LLM_MODEL", ""),
            revision_llm_api_key=env.get("REVISION_LLM_API_KEY", "")
            or env.get("OPENROUTER_API_KEY", ""),
            database_url=env.get("DATABASE_URL", ""),
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
