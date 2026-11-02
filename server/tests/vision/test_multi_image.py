import base64
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from app.vision import router as vision_router
from app.vision.exceptions import VisionError, VisionUnavailableError
from app.vision.gemini import PROMPT, GeminiVisionProvider
from app.vision.openrouter import OpenRouterVisionProvider
from app.vision.providers import FixtureVisionProvider, ImageInput
from app.vision.schemas import DetectedItem

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "vision"


def jpeg(name: str, body: bytes = b"\xff\xd8fake") -> tuple[str, bytes, str]:
    return (name, body, "image/jpeg")


def views(*parts: tuple[str, bytes, str]) -> list[tuple[str, tuple[str, bytes, str]]]:
    return [("images", part) for part in parts]


def item(raw: str, category: str, confidence: float = 0.9) -> DetectedItem:
    return DetectedItem(name_raw=raw, category=category, confidence=confidence)


class MultiVision:
    """Records how the router calls a provider that supports one request for several views."""

    def __init__(self, items=None, error=None):
        self.items = items or []
        self.error = error
        self.single_calls = []
        self.many_calls = []

    def detect(self, image, mime_type):
        self.single_calls.append((image, mime_type))
        if self.error:
            raise self.error
        return self.items

    def detect_many(self, images):
        self.many_calls.append(list(images))
        if self.error:
            raise self.error
        return self.items


class SingleOnlyVision:
    """A provider without detect_many: the router falls back to one request per image."""

    def __init__(self, per_image):
        self.per_image = per_image
        self.calls = 0

    def detect(self, image, mime_type):
        self.calls += 1
        return self.per_image[image]


def test_several_views_go_to_the_provider_in_one_call(make_client):
    vision = MultiVision([item("서울우유 1L", "우유"), item("우유", "우유", 0.95)])

    response = make_client(vision).post(
        "/analyze", files=views(jpeg("a.jpg", b"\xff\xd8a"), jpeg("b.jpg", b"\xff\xd8b"))
    )

    assert response.status_code == 200
    assert vision.single_calls == []
    assert [[i.data for i in call] for call in vision.many_calls] == [[b"\xff\xd8a", b"\xff\xd8b"]]
    assert response.json() == {
        "candidates": [
            {"name": "우유", "raw_texts": ["서울우유 1L", "우유"], "confidence": 0.95},
        ]
    }


def test_repeated_labels_from_overlapping_views_are_listed_once(make_client):
    vision = MultiVision([item("서울우유 1L", "우유"), item("서울우유 1L", "우유")])

    response = make_client(vision).post("/analyze", files=views(jpeg("a.jpg"), jpeg("b.jpg")))

    assert response.json()["candidates"][0]["raw_texts"] == ["서울우유 1L"]


def test_single_image_part_keeps_the_original_path(make_client):
    vision = MultiVision([item("계란", "계란")])

    response = make_client(vision).post("/analyze", files={"image": jpeg("a.jpg")})

    assert response.status_code == 200
    assert len(vision.single_calls) == 1 and vision.many_calls == []


def test_one_part_named_images_is_handled_like_image(make_client):
    vision = MultiVision([item("계란", "계란")])

    response = make_client(vision).post("/analyze", files=views(jpeg("a.jpg")))

    assert response.status_code == 200
    assert len(vision.single_calls) == 1 and vision.many_calls == []


def test_provider_without_multi_support_gets_one_request_per_image(make_client):
    vision = SingleOnlyVision(
        {b"\xff\xd8a": [item("계란", "계란")], b"\xff\xd8b": [item("달걀", "계란")]}
    )

    response = make_client(vision).post(
        "/analyze", files=views(jpeg("a.jpg", b"\xff\xd8a"), jpeg("b.jpg", b"\xff\xd8b"))
    )

    assert vision.calls == 2
    assert response.json()["candidates"] == [
        {"name": "계란", "raw_texts": ["계란", "달걀"], "confidence": 0.9}
    ]


def test_fifteen_images_are_accepted_and_sixteen_are_not(make_client):
    vision = MultiVision()
    client = make_client(vision)

    assert (
        client.post("/analyze", files=views(*[jpeg(f"{n}.jpg") for n in range(15)])).status_code
        == 200
    )
    too_many = client.post("/analyze", files=views(*[jpeg(f"{n}.jpg") for n in range(16)]))

    assert too_many.status_code == 422
    assert len(vision.many_calls) == 1


def test_sending_image_and_images_together_is_rejected(make_client):
    response = make_client(MultiVision()).post(
        "/analyze", files=[("image", jpeg("a.jpg")), ("images", jpeg("b.jpg"))]
    )

    assert response.status_code == 422


def test_sending_no_image_is_rejected(make_client):
    assert make_client(MultiVision()).post("/analyze").status_code == 422


def test_one_unsupported_type_rejects_the_whole_request(make_client):
    vision = MultiVision()

    response = make_client(vision).post(
        "/analyze", files=views(jpeg("a.jpg"), ("notes.txt", b"hi", "text/plain"))
    )

    assert response.status_code == 415
    assert vision.many_calls == []


def test_one_empty_image_rejects_the_whole_request(make_client):
    response = make_client(MultiVision()).post(
        "/analyze", files=views(jpeg("a.jpg"), ("empty.jpg", b"", "image/jpeg"))
    )

    assert response.status_code == 422


def test_total_size_limit_applies_to_several_views(make_client, monkeypatch):
    monkeypatch.setattr(vision_router, "MAX_TOTAL_BYTES", 10)
    vision = MultiVision()
    client = make_client(vision)

    over = client.post("/analyze", files=views(jpeg("a.jpg", b"x" * 6), jpeg("b.jpg", b"y" * 6)))
    within = client.post("/analyze", files=views(jpeg("a.jpg", b"x" * 5), jpeg("b.jpg", b"y" * 5)))

    assert over.status_code == 413
    assert within.status_code == 200


@pytest.mark.parametrize(
    "error,code", [(VisionError("bad"), 502), (VisionUnavailableError("busy"), 503)]
)
def test_provider_failures_on_several_views_use_the_existing_codes(make_client, error, code):
    response = make_client(MultiVision(error=error)).post(
        "/analyze", files=views(jpeg("a.jpg"), jpeg("b.jpg"))
    )

    assert response.status_code == code


def test_fixture_provider_merges_every_view():
    provider = FixtureVisionProvider(FIXTURES)
    a, b = ImageInput(b"photo-a", "image/jpeg"), ImageInput(b"photo-b", "image/jpeg")

    assert provider.detect_many([a, b]) == (
        provider.detect(a.data, a.mime_type) + provider.detect(b.data, b.mime_type)
    )


def openrouter_recording(captured: list[dict]) -> OpenRouterVisionProvider:
    def respond(request):
        captured.append(json.loads(request.content))
        body = {"choices": [{"finish_reason": "stop", "message": {"content": '{"items": []}'}}]}
        return httpx.Response(200, json=body)

    return OpenRouterVisionProvider("key", "test/model", transport=httpx.MockTransport(respond))


def test_openrouter_single_request_is_unchanged():
    captured: list[dict] = []

    openrouter_recording(captured).detect(b"x", "image/png")

    content = captured[0]["messages"][0]["content"]
    assert content[0] == {"type": "text", "text": PROMPT}
    assert [part["type"] for part in content] == ["text", "image_url"]
    assert content[1]["image_url"]["url"] == "data:image/png;base64,eA=="


def test_openrouter_sends_all_views_in_one_request():
    captured: list[dict] = []
    images = [ImageInput(b"x", "image/png"), ImageInput(b"y", "image/jpeg")]

    openrouter_recording(captured).detect_many(images)

    assert len(captured) == 1
    content = captured[0]["messages"][0]["content"]
    assert [part["type"] for part in content] == ["text", "image_url", "image_url"]
    assert "2 photos" in content[0]["text"] and "same refrigerator" in content[0]["text"]
    assert content[2]["image_url"]["url"] == (
        "data:image/jpeg;base64," + base64.b64encode(b"y").decode()
    )


def test_gemini_sends_all_views_then_the_multi_view_prompt():
    class Recording:
        def generate_content(self, **kwargs):
            self.contents = kwargs["contents"]
            return SimpleNamespace(text="[]", usage_metadata=None)

    models = Recording()
    provider = GeminiVisionProvider(SimpleNamespace(models=models), "m", prompt="custom prompt")

    provider.detect_many([ImageInput(b"a", "image/jpeg"), ImageInput(b"b", "image/png")])

    assert len(models.contents) == 3
    assert "2 photos" in models.contents[-1]
    assert models.contents[-1] != "custom prompt"
