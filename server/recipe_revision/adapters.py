"""Single-attempt HTTP adapter for Chat Completions-compatible structured output.

This module is optional: importing the revision core does not load network code.
Transport is injectable for tests. No credentials are read until from_environment
is explicitly called, and no network call is made until generate is called.
"""
# AI-generated initial importer with Codex (GPT-6.1 Sol)
# 2026-10-14 to 2026-10-17; reviewed by Soohyun An

import json
import math
import os
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .core import SCHEMA_VERSION, APIError, LLMResponse, ResponseFormatError, RevisionRequest
from .failures import Failure


class _NoRedirect(HTTPRedirectHandler):
    """Do not forward authorization to a redirected host or repeat a request."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ChatCompletionsLLM:
    """Configured HTTPS transport, JSON schema output, no retries or fallbacks.

    The endpoint must implement the Chat Completions messages/response_format
    protocol. Model and generation settings remain explicit run configuration.
    Raw provider errors are not recorded because they can echo secret headers.
    """

    def __init__(
        self,
        endpoint: str,
        model: str,
        api_key: str,
        *,
        timeout: float = 60,
        temperature: float | None = None,
        max_completion_tokens: int | None = None,
        transport=None,
    ):
        url = urlsplit(endpoint)
        if (
            url.scheme != "https"
            or not url.netloc
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ValueError("Endpoint must be HTTPS without credentials, query or fragment")
        if not model.strip() or not api_key.strip():
            raise ValueError("Live configuration requires model and API key")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Timeout must be finite and positive")
        if temperature is not None and (
            not math.isfinite(temperature) or not 0 <= temperature <= 2
        ):
            raise ValueError("Temperature must be in [0, 2]")
        if max_completion_tokens is not None and (
            type(max_completion_tokens) is not int or max_completion_tokens <= 0
        ):
            raise ValueError("Token limit must be a positive integer")
        self.endpoint, self.model = endpoint, model
        self._api_key = api_key
        self.timeout = timeout
        self.temperature = temperature
        self.max_completion_tokens = max_completion_tokens
        self._transport = transport if transport is not None else build_opener(_NoRedirect()).open

    @classmethod
    def from_environment(
        cls,
        *,
        model: str | None = None,
        timeout: float = 60,
        temperature: float | None = None,
        max_completion_tokens: int | None = None,
    ):
        """Read live credentials only after the caller explicitly opts into live mode."""
        return cls(
            os.environ.get("REVISION_LLM_ENDPOINT", ""),
            model or os.environ.get("REVISION_LLM_MODEL", ""),
            os.environ.get("REVISION_LLM_API_KEY", ""),
            timeout=timeout,
            temperature=temperature,
            max_completion_tokens=max_completion_tokens,
        )

    def configuration(self) -> dict:
        """Return allowlisted non-secret settings for run metadata."""
        return {
            "provider": "chat-completions",
            "endpoint": self.endpoint,
            "model": self.model,
            "timeout": self.timeout,
            "temperature": self.temperature,
            "max_completion_tokens": self.max_completion_tokens,
        }

    def generate(self, request: RevisionRequest) -> LLMResponse:
        """Send exactly one nonstreaming request and retain returned model content."""
        context = request.to_dict()
        payload = {
            "model": self.model,
            "messages": context["messages"],
            "stream": False,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": f"recipe_revision_v{SCHEMA_VERSION}",
                    "strict": True,
                    "schema": context["output_schema"],
                },
            },
        }
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        if self.max_completion_tokens is not None:
            payload["max_completion_tokens"] = self.max_completion_tokens
        if urlsplit(self.endpoint).hostname == "openrouter.ai":
            payload["provider"] = {"require_parameters": True}
        http_request = Request(
            self.endpoint,
            method="POST",
            data=json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with self._transport(http_request, timeout=self.timeout) as response:
                response_bytes = response.read()
        except HTTPError as exc:
            status = exc.code
            provider_code = None
            try:
                # Inspect a bounded body for known codes only; never retain its text.
                body = json.loads(exc.read(65536))
                provider_code = body.get("error", {}).get("code")
            except (ValueError, TypeError, AttributeError, OSError, HTTPException, RecursionError):
                pass
            finally:
                exc.close()
            if status == 401:
                code = "authentication"
            elif status == 403:
                code = "permission"
            elif status == 429:
                code = (
                    "quota_exceeded"
                    if provider_code in ("insufficient_quota", "quota_exceeded")
                    else "rate_limit"
                )
            elif 500 <= status <= 599:
                code = "provider_unavailable"
            elif provider_code in ("model_not_found", "invalid_api_key", "invalid_model"):
                code = "configuration"
            else:
                code = "api_error"
            raise APIError(
                f"LLM HTTP error {status}", failure=Failure(code, "api_request", status)
            ) from None
        except (TimeoutError, URLError, OSError, HTTPException) as exc:
            cause = exc.reason if isinstance(exc, URLError) else exc
            code = "timeout" if isinstance(cause, TimeoutError) else "connection"
            raise APIError(
                "LLM transport failed or timed out", failure=Failure(code, "api_request")
            ) from None
        try:
            body = response_bytes.decode("utf-8").replace(self._api_key, "[REDACTED]")
        except UnicodeError:
            raise ResponseFormatError(
                "Provider response is not UTF-8", stage="provider_response"
            ) from None
        try:
            data = json.loads(body)
            choice = data["choices"][0]
            message = choice["message"]
            content = message.get("content")
            if message.get("refusal") or choice.get("finish_reason") != "stop":
                raise ResponseFormatError(
                    "Provider refused or returned incomplete model output",
                    content if isinstance(content, str) else None,
                    stage="provider_response",
                )
            if not isinstance(content, str):
                raise ResponseFormatError(
                    "Provider returned no model text", stage="provider_response"
                )
            metadata = {}
            if isinstance(data.get("id"), str):
                metadata["request_id"] = data["id"]
            usage = data.get("usage")
            if isinstance(usage, dict):
                metadata["usage"] = {
                    key: usage[key]
                    for key in ("prompt_tokens", "completion_tokens", "total_tokens")
                    if type(usage.get(key)) is int
                }
            return LLMResponse(content, metadata)
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            raise ResponseFormatError(
                "Provider response envelope is invalid", stage="provider_response"
            ) from None
