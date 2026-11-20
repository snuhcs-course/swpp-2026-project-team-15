"""AI-assisted HE review contract checks, 2026-11-09; manual review pending."""

import io
from pathlib import Path

import pytest
from PIL import Image

from app.vision.exceptions import VisionError
from app.vision.providers import FixtureVisionProvider
from app.vision.schemas import DetectedItem
from tests.conftest import StubVision

PHOTO = Path(__file__).resolve().parents[2] / "fixtures" / "demo" / "fridge.png"


def valid_photo():
    # A repository synthetic fixture, not a private user's photo or a live model call.
    path = next((PHOTO.parent).glob("*.png"))
    return (path.name, path.read_bytes(), "image/png")


def test_review_is_additive_and_preserves_evidence(make_client):
    client = make_client(
        StubVision([DetectedItem(name_raw="흰색 포장 두부", category="두부", confidence=0.4)])
    )
    response = client.post("/analyze/review", files={"image": valid_photo()})
    assert response.status_code == 200
    body = response.json()
    assert body["candidates"][0]["raw_texts"] == ["흰색 포장 두부"]
    assert body["candidates"][0]["confidence"] == 0.4
    assert body["review"]["provider_mode"] == "unknown"
    assert body["review"]["status"] == "review_required"
    assert body["review"]["minimum_confidence"] is None
    assert body["review"]["bbox_supported"] is False


def test_invalid_photo_is_rejected_before_provider(make_client):
    class CountingVision(StubVision):
        calls = 0

        def detect(self, image, mime_type):
            self.calls += 1
            return super().detect(image, mime_type)

    vision = CountingVision()
    response = make_client(vision).post(
        "/analyze/review", files={"image": ("fake.jpg", b"not a photo", "image/jpeg")}
    )
    assert response.status_code == 422
    assert vision.calls == 0


def test_no_candidates_is_not_a_network_failure(make_client):
    response = make_client(StubVision()).post("/analyze/review", files={"image": valid_photo()})
    assert response.status_code == 200
    assert response.json()["review"]["status"] == "empty"


def test_mock_mode_is_explicit_without_calling_model(make_client):
    fixtures = Path(__file__).resolve().parents[2] / "fixtures" / "vision"
    client = make_client(FixtureVisionProvider(fixtures))
    caps = client.get("/vision/capabilities")
    assert caps.status_code == 200
    assert caps.json()["provider_mode"] == "mock"
    assert caps.json()["bbox_supported"] is False
    response = client.post("/analyze/review", files={"image": valid_photo()})
    assert response.json()["review"]["provider_mode"] == "mock"


def test_review_error_does_not_return_provider_details(make_client):
    response = make_client(StubVision(error=VisionError("private provider details"))).post(
        "/analyze/review", files={"image": valid_photo()}
    )
    assert response.status_code == 502
    assert "private provider details" not in response.text


@pytest.mark.parametrize("actual_format", ["PNG", "GIF", "BMP", "TIFF"])
def test_review_rejects_decoded_format_mismatch_before_provider(make_client, actual_format):
    class CountingVision(StubVision):
        calls = 0

        def detect(self, image, mime_type):
            self.calls += 1
            return []

    image = Image.new("RGB", (16, 16), "green")
    data = io.BytesIO()
    image.save(data, format=actual_format)
    vision = CountingVision()
    response = make_client(vision).post(
        "/analyze/review", files={"image": ("disguised.jpg", data.getvalue(), "image/jpeg")}
    )
    assert response.status_code == 415
    assert vision.calls == 0
