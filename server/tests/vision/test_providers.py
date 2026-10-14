# AI-generated with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors as genai_errors

from app.config import SERVER_DIR
from app.vision.exceptions import VisionError, VisionUnavailableError
from app.vision.gemini import GeminiVisionProvider
from app.vision.providers import FixtureVisionProvider
from app.vision.schemas import DetectedItem
from app.vision.service import to_candidates

FIXTURES = SERVER_DIR / "fixtures" / "vision"


def test_fixture_provider_is_deterministic_per_image():
    provider = FixtureVisionProvider(FIXTURES)

    assert provider.detect(b"photo-a", "image/jpeg") == provider.detect(b"photo-a", "image/jpeg")


def test_fixture_provider_requires_fixtures(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        FixtureVisionProvider(tmp_path)


def test_candidates_merge_same_category_and_keep_order():
    items = [
        DetectedItem(name_raw="신라면", category="라면", confidence=0.7),
        DetectedItem(name_raw="달걀 10구", category="달걀", confidence=0.9),
        DetectedItem(name_raw="너구리", category="라면", confidence=0.95),
        DetectedItem(name_raw="?", category="  ", confidence=0.1),
    ]

    candidates = to_candidates(items)

    assert [c.name for c in candidates] == ["라면", "달걀"]
    assert candidates[0].raw_texts == ["신라면", "너구리"]
    assert candidates[0].confidence == 0.95


class FakeModels:
    def __init__(self, text: str = "", error: Exception | None = None) -> None:
        self.text = text
        self.error = error
        self.calls = 0

    def generate_content(self, **_kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return SimpleNamespace(text=self.text, usage_metadata=None)


def gemini_with(models: FakeModels) -> GeminiVisionProvider:
    return GeminiVisionProvider(SimpleNamespace(models=models), model="test-model")


def test_gemini_provider_parses_structured_response():
    payload = [{"name_raw": "국산 다진마늘", "category": "다진마늘", "confidence": 1.0}]
    models = FakeModels(json.dumps(payload, ensure_ascii=False))
    provider = GeminiVisionProvider(SimpleNamespace(models=models), model="test-model")

    assert provider.detect(b"img", "image/jpeg") == [DetectedItem(**payload[0])]
    assert models.calls == 1


def test_gemini_provider_rejects_malformed_response():
    with pytest.raises(VisionError):
        gemini_with(FakeModels("not json")).detect(b"img", "image/jpeg")


@pytest.mark.parametrize(
    "error",
    [
        genai_errors.ClientError(429, {"error": {"message": "quota"}}),
        genai_errors.ServerError(503, {"error": {"message": "overloaded"}}),
        httpx.ReadTimeout("timed out"),
    ],
)
def test_gemini_provider_marks_transient_failures_as_unavailable(error):
    with pytest.raises(VisionUnavailableError):
        gemini_with(FakeModels(error=error)).detect(b"img", "image/jpeg")


def test_gemini_provider_reports_rejected_request_as_permanent_error():
    error = genai_errors.ClientError(400, {"error": {"message": "bad image"}})

    with pytest.raises(VisionError) as raised:
        gemini_with(FakeModels(error=error)).detect(b"img", "image/jpeg")

    assert not isinstance(raised.value, VisionUnavailableError)
