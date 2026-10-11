# AI-generated with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.
"""Gemini-backed recognition. Requests only the fields the app uses to keep tokens low."""

from google import genai
from google.genai import types
from pydantic import ValidationError

from app.vision.exceptions import VisionError
from app.vision.providers import DETECTED_ITEMS
from app.vision.schemas import DetectedItem

PROMPT = (
    "List the food items visible in this refrigerator or pantry photo. "
    "For each item give name_raw (label text or description as seen), "
    "category (a generic Korean ingredient name usable in a recipe, e.g. 신라면 -> 라면) "
    "and confidence between 0 and 1. Omit non-food objects."
)


class GeminiVisionProvider:
    def __init__(self, client: genai.Client, model: str) -> None:
        self._client = client
        self._model = model

    def detect(self, image: bytes, mime_type: str) -> list[DetectedItem]:
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=[types.Part.from_bytes(data=image, mime_type=mime_type), PROMPT],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=list[DetectedItem],
                ),
            )
            return DETECTED_ITEMS.validate_json(response.text or "")
        except (genai.errors.APIError, ValidationError) as exc:
            raise VisionError(f"Gemini recognition failed: {exc}") from exc
