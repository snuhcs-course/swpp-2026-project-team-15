"""US02/03/04/05: reviewed names resolve before ID-based recommendations.

Expected IDs/ordering follow the independent contributor integration fixture;
water validation follows the received catalog mismatch (old204=된장/new204=물).
"""

import sqlite3
from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.main import create_app
from app.recipes.recommendations import RecommendationService
from tests.conftest import StubVision


def test_catalog_recommendation_and_favorite_source_flow(integration_repository):
    client = TestClient(create_app(StubVision(), integration_repository))
    analyzed = client.post("/analyze", files={"image": ("food.jpg", b"photo", "image/jpeg")})
    assert analyzed.status_code == 200
    catalog = client.get("/recipes/catalog").json()
    assert len(catalog["version"]) == 64
    ids = {row["name"]: row["ingredient_id"] for row in catalog["ingredients"]}
    result = client.post(
        "/recipes/recommendations",
        json={"ingredient_ids": [ids["Alpha"], ids["Beta"]]},
        headers={"X-Ingredient-Catalog": catalog["version"]},
    )
    assert result.status_code == 200
    entry = next(row for row in result.json()["recipes"] if row["recipe_id"] == 20)
    assert entry["revision"]["status"] == "refused"  # Existing mock is explicitly a refusal.
    restored = client.get("/recipes/source/20")
    assert restored.status_code == 200
    assert restored.json() == entry["original"]
    assert client.get("/recipes/source/999999").status_code == 404


def test_changed_catalog_rejected_before_ai(integration_repository):
    factory = Mock(side_effect=AssertionError("AI must not run with stale IDs"))
    service = RecommendationService(integration_repository, llm_factory=factory)
    client = TestClient(create_app(StubVision(), integration_repository, recommendations=service))
    response = client.post(
        "/recipes/recommendations",
        json={"ingredient_ids": [1]},
        headers={"X-Ingredient-Catalog": "outdated"},
    )
    assert response.status_code == 409
    factory.assert_not_called()


def test_wrong_water_catalog_rejects_new_flow(integration_repository, integration_db):
    with sqlite3.connect(integration_db) as db:
        db.execute("UPDATE ingredient SET name='된장' WHERE ingredient_id=204")
    client = TestClient(create_app(StubVision(), integration_repository))
    assert client.get("/recipes/catalog").status_code == 503
    assert client.post("/recipes/recommendations", json={"ingredient_ids": [1]}).status_code == 503
    assert client.get("/recipes/source/20").status_code == 503


def test_catalog_database_failure_is_recoverable(integration_repository, integration_db):
    with sqlite3.connect(integration_db) as db:
        db.execute("DROP TABLE ingredient")
    response = TestClient(create_app(StubVision(), integration_repository)).get("/recipes/catalog")
    assert response.status_code == 503
