# AI-generated with Claude Code (Opus 5.5), 2026-10-11 to 2026-10-14; reviewed by Jaehyuk Choi.
from app.vision.exceptions import VisionError, VisionUnavailableError
from app.vision.schemas import DetectedItem
from tests.conftest import StubVision

JPEG = ("fridge.jpg", b"\xff\xd8fake", "image/jpeg")


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
    vision = StubVision(error=VisionError("bad response"))

    response = make_client(vision).post("/analyze", files={"image": JPEG})

    assert response.status_code == 502


def test_analyze_reports_temporary_unavailability_as_503(make_client):
    vision = StubVision(error=VisionUnavailableError("rate limit"))

    response = make_client(vision).post("/analyze", files={"image": JPEG})

    assert response.status_code == 503


def test_analyze_rejects_a_broken_image_before_the_model(make_client):
    # Phone test 2026-11-19: a broken PNG reached the model and came back as 502.
    vision = StubVision(error=VisionError("the model was called"))  # a call would give 502
    png_cut = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40  # signature, no end chunk
    for name, body, kind in [
        ("cut.png", png_cut, "image/png"),
        ("noise.jpg", b"not an image at all", "image/jpeg"),
    ]:
        response = make_client(vision).post("/analyze", files={"image": (name, body, kind)})
        assert response.status_code == 415, name


def test_image_check_accepts_the_supported_formats():
    from app.vision.router import looks_like_image

    assert looks_like_image(b"\xff\xd8\xff\xe0rest")
    assert looks_like_image(b"\x89PNG\r\n\x1a\n...\x00\x00\x00\x00IEND\xaeB`\x82")
    assert looks_like_image(b"RIFF\x00\x00\x00\x00WEBPVP8 ")
    assert looks_like_image(b"\x00\x00\x00\x18ftypheic")
    assert not looks_like_image(b"GIF89a")
