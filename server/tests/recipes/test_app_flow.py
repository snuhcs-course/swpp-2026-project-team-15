"""The original name-based Android API remains independent of recipe revision."""

from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.main import create_app
from app.recipes.recommendations import RecommendationService
from app.recipes.service import RecipeRepository
from app.vision.schemas import DetectedItem
from tests.conftest import StubVision


def test_reviewed_names_recommend_without_revision(recipe_db):
    from app.database import read_only_sqlite_engine

    repository = RecipeRepository(read_only_sqlite_engine(recipe_db))
    factory = Mock(side_effect=AssertionError("The original app does not request AI revision"))
    client = TestClient(
        create_app(
            StubVision([DetectedItem(name_raw="egg", category="계란", confidence=0.9)]),
            repository,
            recommendations=RecommendationService(repository, llm_factory=factory),
        )
    )
    photo = client.post("/analyze", files={"image": ("photo.jpg", b"photo", "image/jpeg")})
    assert photo.status_code == 200
    assert photo.json()["candidates"][0]["name"] == "계란"
    # The user's reviewed inventory supplies names to the original contract.
    response = client.post("/recipes/recommend", json={"ingredients": ["계란", "밥"]})
    assert response.status_code == 200
    assert response.json()["recipes"][0]["name"] == "계란볶음밥"
    factory.assert_not_called()
    assert client.get("/recipes/catalog").status_code == 404
    assert client.get("/recipes/source/1").status_code == 404
