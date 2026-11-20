# AI-generated with Claude Code (Opus 5.5), 2026-10-11 to 2026-10-14; reviewed by Jaehyuk Choi.

# Modified with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
# Changes: The test app serves dishes and recognition only (no recipe database).
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.vision.exceptions import VisionError
from app.vision.schemas import DetectedItem


class StubVision:
    def __init__(
        self, items: list[DetectedItem] | None = None, error: VisionError | None = None
    ) -> None:
        self.items = items or []
        self.error = error

    def detect(self, image: bytes, mime_type: str) -> list[DetectedItem]:
        if self.error:
            raise self.error
        return self.items


@pytest.fixture
def make_client():
    def build(vision: StubVision) -> TestClient:
        return TestClient(create_app(vision))

    return build
