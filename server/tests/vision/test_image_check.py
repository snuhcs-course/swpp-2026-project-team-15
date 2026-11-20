# AI-generated with Claude Code (Opus 5.5), 2026-11-19; not yet reviewed.
"""The structural image check before any model call (phone test 2026-11-19)."""

import pytest

from app.vision.exceptions import VisionError
from tests.conftest import StubVision


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
    assert looks_like_image(b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1heic" + b"\x00" * 64)
    assert not looks_like_image(b"GIF89a")
    assert not looks_like_image(b"\xff\xd8fake")  # two bytes are not a JPEG signature


@pytest.mark.parametrize(
    "brand", [b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"mif1", b"msf1"]
)
def test_every_heif_brand_passes_even_with_a_short_header(brand):
    from app.vision.router import looks_like_image

    assert looks_like_image(b"\x00\x00\x00\x18ftyp" + brand)


@pytest.mark.parametrize("brand", [b"isom", b"mp42", b"avif"])
def test_video_and_avif_brands_are_not_images(brand):
    from app.vision.router import looks_like_image

    assert not looks_like_image(b"\x00\x00\x00\x18ftyp" + brand + b"\x00" * 64)
