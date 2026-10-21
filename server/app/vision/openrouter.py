"""Bounded, single-attempt OpenRouter image recognition; no secret-bearing errors."""

import base64
import json

import httpx
from pydantic import ValidationError

from app.vision.exceptions import VisionError, VisionUnavailableError
from app.vision.gemini import PROMPT
from app.vision.providers import DETECTED_ITEMS
from app.vision.schemas import DetectedItem

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterVisionProvider:
    def __init__(self, api_key: str, model: str, *, transport=None):
        self._api_key = api_key
        self._model = model
        self._transport = transport

    def detect(self, image: bytes, mime_type: str) -> list[DetectedItem]:
        schema = {
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
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64.b64encode(image).decode()}"
                            },
                        },
                    ],
                }
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "detected_items",
                    "strict": True,
                    "schema": schema,
                },
            },
            "provider": {"require_parameters": True},
            "max_tokens": 2048,
            "temperature": 0,
        }
        try:
            with httpx.Client(
                timeout=45, transport=self._transport, follow_redirects=False
            ) as client:
                response = client.post(
                    ENDPOINT,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                    },
                )
            if response.status_code == 429 or response.status_code >= 500:
                raise VisionUnavailableError("OpenRouter is temporarily unavailable")
            if response.status_code != 200:
                raise VisionError("OpenRouter rejected the request")
            choice = response.json()["choices"][0]
            if choice.get("finish_reason") != "stop" or choice["message"].get("refusal"):
                raise VisionError("OpenRouter returned incomplete recognition")
            data = json.loads(choice["message"]["content"])
            return DETECTED_ITEMS.validate_python(data["items"])
        except (httpx.TimeoutException, httpx.TransportError):
            raise VisionUnavailableError("OpenRouter connection failed") from None
        except (ValueError, KeyError, TypeError, IndexError, ValidationError):
            raise VisionError("OpenRouter returned invalid recognition") from None
