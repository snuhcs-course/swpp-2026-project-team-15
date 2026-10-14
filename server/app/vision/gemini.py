# AI-generated with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.
"""Gemini-backed recognition. Requests only the fields the app uses to keep tokens low."""

import logging

import httpx
from google import genai
from google.genai import types
from pydantic import ValidationError

from app.vision.exceptions import VisionError, VisionUnavailableError
from app.vision.providers import DETECTED_ITEMS
from app.vision.schemas import DetectedItem

PROMPT = (
    "List the food items visible in this refrigerator or pantry photo. "
    "For each item give name_raw (label text or description as seen), "
    "category (a generic Korean ingredient name usable in a recipe, e.g. 신라면 -> 라면) "
    "and confidence between 0 and 1. Omit non-food objects."
)

logger = logging.getLogger(__name__)

# The free tier answers 429 when the per-minute quota is used up.
_RATE_LIMITED = 429
REQUEST_TIMEOUT_MS = 30_000


class GeminiVisionProvider:
    def __init__(
        self,
        client: genai.Client,
        model: str,
        prompt: str = PROMPT,
        response_schema: type = list[DetectedItem],
    ) -> None:
        self._client = client
        self._model = model
        self._prompt = prompt
        self._response_schema = response_schema

    def detect(self, image: bytes, mime_type: str) -> list[DetectedItem]:
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=[types.Part.from_bytes(data=image, mime_type=mime_type), self._prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=self._response_schema,
                ),
            )
        except genai.errors.ClientError as exc:
            if exc.code == _RATE_LIMITED:
                raise VisionUnavailableError("Gemini rate limit reached") from exc
            raise VisionError(f"Gemini rejected the request: {exc}") from exc
        except (genai.errors.ServerError, httpx.TimeoutException) as exc:
            raise VisionUnavailableError(f"Gemini is unavailable: {exc}") from exc

        if usage := response.usage_metadata:
            logger.info("Gemini %s used %s tokens", self._model, usage.total_token_count)
        try:
            return DETECTED_ITEMS.validate_json(response.text or "")
        except ValidationError as exc:
            raise VisionError("Gemini returned an unexpected response") from exc
