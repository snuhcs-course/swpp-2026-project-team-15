"""Explicit, bounded live check of vision -> canonical IDs -> one recipe adjustment.

Private photos/results stay outside Git. Defaults elsewhere remain mock. No
provider fallback, retry, quota probing or paid-tier upgrade is performed.
"""

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv
from fastapi.testclient import TestClient
from google import genai
from google.genai import types

from app.config import Settings
from app.database import read_only_sqlite_engine
from app.main import create_app
from app.recipes.recommendations import RecommendationService
from app.recipes.service import RecipeRepository
from app.vision.gemini import REQUEST_TIMEOUT_MS, GeminiVisionProvider
from recipe_revision.adapters import ChatCompletionsLLM


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    settings = Settings.from_env()
    engine = read_only_sqlite_engine(settings.recipe_db_path)
    provider = genai.Client(
        api_key=settings.gemini_api_key,
        http_options=types.HttpOptions(
            timeout=REQUEST_TIMEOUT_MS, retry_options=types.HttpRetryOptions(attempts=1)
        ),
    )
    repository = RecipeRepository(engine)
    service = RecommendationService(repository, llm_factory=ChatCompletionsLLM.from_environment)
    report = {
        "vision_model": settings.gemini_model,
        "revision_model": settings.revision_llm_model,
        "vision_calls_max": 1,
        "revision_calls_max": 1,
        "mode": "live-free-quota",
    }
    try:
        with TestClient(
            create_app(
                GeminiVisionProvider(provider, settings.gemini_model),
                repository,
                recommendations=service,
            )
        ) as client:
            response = client.post(
                "/analyze", files={"image": ("photo.jpg", args.image.read_bytes(), "image/jpeg")}
            )
            report["analyze_http"] = response.status_code
            if response.status_code != 200:
                report["outcome"] = "vision_failed_or_quota_exhausted; no revision attempted"
            else:
                candidates = response.json()["candidates"]
                catalog = client.get("/recipes/catalog").json()
                known = {row["name"]: row["ingredient_id"] for row in catalog["ingredients"]}
                names = [row["name"] for row in candidates]
                # Match the documented client rule: exact name, then the existing egg alias.
                resolved = {
                    name: known.get(name, known.get("계란") if name == "달걀" else None)
                    for name in names
                }
                accepted = list(
                    dict.fromkeys(value for value in resolved.values() if value is not None)
                )
                report["candidate_names"] = names
                report["confirmed_ids"] = accepted
                report["unmapped"] = [name for name, value in resolved.items() if value is None]
                result = client.post(
                    "/recipes/recommendations",
                    json={"ingredient_ids": accepted, "revision_limit": 1},
                    headers={"X-Ingredient-Catalog": catalog["version"]},
                )
                report["recommendation_http"] = result.status_code
                if result.status_code == 200:
                    body = result.json()
                    report["catalog_version"] = catalog["version"]
                    report["revision_summary"] = body["revision_summary"]
                    report["revision_statuses"] = {
                        entry["recipe_id"]: entry["revision"]["status"] for entry in body["recipes"]
                    }
                    report["outcome"] = (
                        "live response recorded; semantic correctness not established"
                    )
                    args.output.with_suffix(".private-response.json").write_text(
                        json.dumps(body, ensure_ascii=False, indent=2) + "\n"
                    )
    finally:
        provider.close()
        engine.dispose()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: report.get(key)
                for key in ["analyze_http", "recommendation_http", "revision_summary", "outcome"]
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
