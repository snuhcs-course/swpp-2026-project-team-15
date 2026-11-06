# AI-generated initial implementation with Codex (GPT-6), 2026-11-06; reviewed by Ahyoon Choi.

from pathlib import Path

from app import main
from tests.conftest import StubVision


def test_recipe_image_directory_is_under_server_static_recipes():
    """Pin the default filesystem location to server/static/images/recipes."""
    expected = Path(main.__file__).resolve().parents[1] / "static" / "images" / "recipes"

    assert main.RECIPE_IMAGE_DIR == expected


def test_recipe_image_route_serves_from_the_configured_static_directory(
    tmp_path, monkeypatch, make_client
):
    """Verify /recipe-images serves the bytes stored in the directory mounted by FastAPI."""
    image_dir = tmp_path / "static" / "images" / "recipes"
    image_dir.mkdir(parents=True)
    expected_bytes = b"test-webp-content"
    (image_dir / "fixture.webp").write_bytes(expected_bytes)
    monkeypatch.setattr(main, "RECIPE_IMAGE_DIR", image_dir)

    response = make_client(StubVision()).get("/recipe-images/fixture.webp")

    assert response.status_code == 200
    assert response.content == expected_bytes
    assert response.headers["content-type"].startswith("image/webp")
