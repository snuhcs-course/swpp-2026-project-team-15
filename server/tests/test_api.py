# AI-generated with Claude Code (Opus 5.5), 2026-10-11; review pending by Jaehyuk Choi.
import pytest

from app.config import Settings
from app.schemas import DetectedItem
from app.vocabulary import STAPLE_SEASONINGS
from tests.conftest import StubVision

JPEG = ("fridge.jpg", b"\xff\xd8fake", "image/jpeg")


def test_health(make_client):
    assert make_client(StubVision()).get("/health").json() == {"status": "ok"}


def test_analyze_returns_unconfirmed_candidates(make_client):
    vision = StubVision(
        [DetectedItem(name_raw="국산 다진마늘 500g", category="다진마늘", confidence=1.0)]
    )

    response = make_client(vision).post("/analyze", files={"image": JPEG})

    assert response.status_code == 200
    assert response.json() == {
        "candidates": [{"name": "다진마늘", "raw_texts": ["국산 다진마늘 500g"], "confidence": 1.0}]
    }


def test_analyze_with_nothing_found_returns_empty_list(make_client):
    response = make_client(StubVision([])).post("/analyze", files={"image": JPEG})

    assert response.json() == {"candidates": []}


def test_analyze_rejects_non_image(make_client):
    response = make_client(StubVision()).post(
        "/analyze", files={"image": ("notes.txt", b"hi", "text/plain")}
    )

    assert response.status_code == 415


def test_analyze_rejects_empty_upload(make_client):
    response = make_client(StubVision()).post(
        "/analyze", files={"image": ("empty.jpg", b"", "image/jpeg")}
    )

    assert response.status_code == 422


def test_analyze_reports_provider_failure_as_bad_gateway(make_client):
    response = make_client(StubVision(error=True)).post("/analyze", files={"image": JPEG})

    assert response.status_code == 502


def test_recommend_returns_ranked_recipes_and_assumed_staples(make_client):
    response = make_client(StubVision()).post(
        "/recipes/recommend", json={"ingredients": ["김치", "두부", "밥", "계란", "대파"]}
    )

    body = response.json()
    assert response.status_code == 200
    assert body["staples_assumed"] == list(STAPLE_SEASONINGS)
    assert [(r["name"], r["missing"]) for r in body["recipes"]] == [
        ("계란볶음밥", []),
        ("김치찌개", ["돼지고기"]),
    ]


def test_recommend_validates_bounds(make_client):
    response = make_client(StubVision()).post(
        "/recipes/recommend", json={"ingredients": [], "max_missing": 6}
    )

    assert response.status_code == 422


def test_settings_default_to_mock_provider():
    assert Settings.from_env({}).vision_provider == "mock"


@pytest.mark.parametrize(
    "env",
    [{"VISION_PROVIDER": "openai"}, {"VISION_PROVIDER": "gemini", "GEMINI_API_KEY": "k"}],
)
def test_settings_reject_invalid_configuration(env):
    with pytest.raises(ValueError):
        Settings.from_env(env)
