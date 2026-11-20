"""Bounded, single-attempt OpenRouter image recognition; no secret-bearing errors."""

# Modified with Claude Code (Opus 5.5), 2026-11-20: calls go through the openai SDK client.

import base64
import json
from collections.abc import Sequence
from typing import Any

import httpx
import openai
from openai.types.chat import ChatCompletionContentPartParam
from pydantic import ValidationError

from app.json_lists import salvage_list
from app.openrouter import json_schema_format, openrouter_client
from app.vision.exceptions import VisionError, VisionUnavailableError
from app.vision.gemini import PROMPT, multi_view_prompt
from app.vision.providers import DETECTED_ITEMS, ImageInput
from app.vision.schemas import DetectedItem

TIMEOUT = 45.0  # seconds for the one attempt


class OpenRouterVisionProvider:
    def __init__(self, api_key: str, model: str, *, transport: httpx.BaseTransport | None = None):
        self._client = openrouter_client(api_key, timeout=TIMEOUT, transport=transport)
        self._model = model

    def detect(self, image: bytes, mime_type: str) -> list[DetectedItem]:
        return self._request([ImageInput(image, mime_type)], PROMPT)

    def detect_many(self, images: Sequence[ImageInput]) -> list[DetectedItem]:
        """Send all views in one request so the model lists each distinct item once."""
        return self._request(images, multi_view_prompt(len(images)))

    def _request(self, images: Sequence[ImageInput], prompt: str) -> list[DetectedItem]:
        schema: dict[str, Any] = {
            "type": "object",
            "properties": {"items": DETECTED_ITEMS.json_schema()},
            "required": ["items"],
            "additionalProperties": False,
        }
        # Keep $defs at the root, where the generated refs resolve.
        definitions = schema["properties"]["items"].pop("$defs", {})
        if definitions:
            schema["$defs"] = definitions
            for value in definitions.values():
                value["additionalProperties"] = False
        content: list[ChatCompletionContentPartParam] = [{"type": "text", "text": prompt}]
        for i in images:
            url = f"data:{i.mime_type};base64,{base64.b64encode(i.data).decode()}"
            content.append({"type": "image_url", "image_url": {"url": url}})
        try:
            completion = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": content}],
                response_format=json_schema_format("detected_items", schema),
                max_tokens=2048,
                temperature=0,
                extra_body={"provider": {"require_parameters": True}},
            )
            choice = completion.choices[0]
            message = choice.message
            if message.refusal:
                raise VisionError("OpenRouter returned incomplete recognition")
            if choice.finish_reason == "length":
                # The model can loop on package text until the token limit; the items it finished
                # are still real (research/experiments/recheck_leftovers, item 2).
                data = salvage_list(message.content or "")
                if not data or "items" not in data:
                    raise VisionError("OpenRouter returned incomplete recognition")
                return DETECTED_ITEMS.validate_python(data["items"])
            if choice.finish_reason != "stop":
                raise VisionError("OpenRouter returned incomplete recognition")
            data = json.loads(message.content or "")
            return DETECTED_ITEMS.validate_python(data["items"])
        except openai.APIStatusError as exc:
            if exc.status_code == 429 or exc.status_code >= 500:
                raise VisionUnavailableError("OpenRouter is temporarily unavailable") from None
            raise VisionError("OpenRouter rejected the request") from None
        except (openai.APITimeoutError, openai.APIConnectionError):
            raise VisionUnavailableError("OpenRouter connection failed") from None
        except (ValueError, KeyError, TypeError, IndexError, AttributeError, ValidationError):
            raise VisionError("OpenRouter returned invalid recognition") from None
