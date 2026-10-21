"""Cloud boundaries: real PostgreSQL transactions and isolated OpenRouter transports."""

import csv
import io
import json
import os
import zipfile
from pathlib import Path

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import create_engine

from app.database import recipe_engine
from app.main import create_app
from app.recipes.catalog import read_catalog
from app.recipes.service import RecipeRepository
from app.vision.exceptions import VisionError, VisionUnavailableError
from app.vision.openrouter import OpenRouterVisionProvider
from app.vision.providers import FixtureVisionProvider
from db.import_recipes import TABLES
from db.postgres import import_zip


def test_openrouter_vision_contract():
    def respond(request):
        payload = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer private-test-key"
        assert payload["provider"]["require_parameters"] is True
        assert payload["max_tokens"] == 2048
        assert (
            payload["messages"][0]["content"][1]["image_url"]["url"] == "data:image/png;base64,eA=="
        )
        schema = payload["response_format"]["json_schema"]["schema"]
        assert schema["$defs"]["DetectedItem"]["additionalProperties"] is False
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(
                                {
                                    "items": [
                                        {"name_raw": "egg", "category": "계란", "confidence": 0.9},
                                    ]
                                }
                            )
                        },
                    }
                ]
            },
        )

    provider = OpenRouterVisionProvider(
        "private-test-key", "test/model", transport=httpx.MockTransport(respond)
    )
    assert provider.detect(b"x", "image/png")[0].category == "계란"


@pytest.mark.parametrize(
    "status,error",
    [
        (401, VisionError),
        (429, VisionUnavailableError),
        (503, VisionUnavailableError),
        (302, VisionError),
    ],
)
def test_openrouter_errors_hide_secrets(status, error):
    transport = httpx.MockTransport(lambda _: httpx.Response(status, text="private-test-key"))
    with pytest.raises(error) as caught:
        OpenRouterVisionProvider("private-test-key", "test", transport=transport).detect(
            b"x", "image/png"
        )
    assert "private-test-key" not in str(caught.value)


def test_openrouter_rejects_truncation():
    transport = httpx.MockTransport(
        lambda _: httpx.Response(
            200,
            json={
                "choices": [{"finish_reason": "length", "message": {"content": "{}"}}],
            },
        )
    )
    with pytest.raises(VisionError):
        OpenRouterVisionProvider("key", "test", transport=transport).detect(b"x", "image/png")


def dataset(path, *, name="계란요리", ingredient="계란", bad_fk=False):
    values = {
        "recipe": [(1, name, None, None, None, "10분", None, "1", None)],
        "ingredient": [(1, ingredient), (204, "물")],
        "recipe_step": [(1, 1, 1, "끓인다", None)],
        "recipe_ingredient": [(1, 999 if bad_fk else 1, 1, None, "3060001", None, None)],
    }
    with zipfile.ZipFile(path, "w") as archive:
        for spec in TABLES:
            stream = io.StringIO()
            writer = csv.writer(stream)
            writer.writerow(spec.columns)
            writer.writerows(values.get(spec.table, []))
            archive.writestr(spec.filename, stream.getvalue())
    return path


def test_zip_path_traversal_rejected(tmp_path):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("../Recipe.csv", "x")
    with pytest.raises(ValueError, match="exactly"):
        import_zip("postgresql+psycopg://unused", archive)
    assert not (tmp_path / "Recipe.csv").exists()


@pytest.fixture
def pg_engine():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL required for disposable PostgreSQL integration database")
    engine = create_engine(url)
    # Test database must be disposable, never the deployed DATABASE_URL.
    with engine.begin() as conn:
        for spec in reversed(TABLES):
            conn.execute(text(f"DROP TABLE IF EXISTS {spec.table} CASCADE"))
    yield url, engine
    engine.dispose()


def test_postgres_initialize_reset_rollback_and_readiness(pg_engine, tmp_path):
    url, engine = pg_engine
    archive = dataset(tmp_path / "dataset.zip")
    empty_repo = RecipeRepository(recipe_engine(url, Path("unused")))
    empty_client = TestClient(
        create_app(FixtureVisionProvider(Path("fixtures/vision")), empty_repo)
    )
    assert empty_client.get("/health").status_code == 200
    assert empty_client.get("/ready").status_code == 503
    counts = import_zip(url, archive)
    assert counts["ingredient"] == 2
    repo = RecipeRepository(recipe_engine(url, Path("unused")))
    original_version = read_catalog(repo).version
    client = TestClient(create_app(FixtureVisionProvider(Path("fixtures/vision")), repo))
    assert client.get("/ready").status_code == 200
    assert client.get("/recipes/source/1").json()["name"] == "계란요리"
    assert client.post("/recipes/recommend", json={"ingredients": ["계란"]}).status_code == 200
    with pytest.raises(ValueError, match="initialized"):
        import_zip(url, archive)
    with pytest.raises(ValueError):
        import_zip(url, dataset(archive, bad_fk=True), replace=True)
    assert read_catalog(repo).version == original_version
    # Force a PostgreSQL-only failure after DELETE: a local check constraint.
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE recipe ADD CONSTRAINT reject_new CHECK (name <> 'reject')"))
    with pytest.raises(psycopg.errors.CheckViolation):
        import_zip(url, dataset(archive, name="reject"), replace=True)
    assert client.get("/recipes/source/1").json()["name"] == "계란요리"
    import_zip(url, dataset(archive, name="새요리", ingredient="감자"), replace=True)
    assert read_catalog(repo).version != original_version
    response = client.post(
        "/recipes/recommendations",
        json={"ingredient_ids": [1]},
        headers={"X-Ingredient-Catalog": original_version},
    )
    assert response.status_code == 409
    assert client.get("/recipes/source/1").json()["name"] == "새요리"
