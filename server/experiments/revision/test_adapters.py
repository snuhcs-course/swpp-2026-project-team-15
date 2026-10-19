"""Mock HTTP boundary only; these tests never send provider API requests."""
# AI-generated initial importer with Codex (GPT-6.1 Sol)
# 2026-10-14 to 2026-10-17; reviewed by Soohyun An

from io import BytesIO
from http.client import IncompleteRead
import json
import os
from urllib.error import HTTPError, URLError
from unittest.mock import MagicMock, patch

from server.recipe_revision import APIError, ResponseFormatError, build_request
from server.recipe_revision.adapters import ChatCompletionsLLM, _NoRedirect
from experiments.revision.support import OfflineTestCase, inventory, sample_recipe


class AdapterTests(OfflineTestCase):
    """Validate one-attempt transport, structured requests and safe error recording."""

    def adapter(self, transport):
        return ChatCompletionsLLM("https://provider.example.test/v1/chat/completions", "chosen-model", "secret-key",
                                  timeout=7, temperature=0.2, max_completion_tokens=500, transport=transport)

    def transport(self, body):
        transport = MagicMock()
        transport.return_value.__enter__.return_value.read.return_value = body.encode("utf-8")
        return transport

    def test_request_schema_settings_and_allowlisted_metadata(self):
        transport = self.transport(json.dumps({"id": "req-1", "choices": [{"finish_reason": "stop", "message": {
            "content": "model text"}}], "usage": {"total_tokens": 4, "extra_secret": "secret-key"}}))
        adapter = self.adapter(transport)
        response = adapter.generate(build_request(sample_recipe(), inventory()))
        transport.assert_called_once()
        args, kwargs = transport.call_args
        request = args[0]
        self.assertEqual(kwargs, {"timeout": 7})
        payload = json.loads(request.data)
        self.assertEqual(len(payload["messages"]), 2)
        self.assertTrue(payload["response_format"]["json_schema"]["strict"])
        self.assertEqual(payload["model"], "chosen-model")
        self.assertEqual(payload["temperature"], 0.2)
        self.assertEqual(payload["max_completion_tokens"], 500)
        self.assertEqual(request.get_header("Authorization"), "Bearer secret-key")
        self.assertNotIn("secret-key", json.dumps(adapter.configuration()))
        self.assertEqual(response.metadata, {"request_id": "req-1", "usage": {"total_tokens": 4}})

    def test_http_and_timeout_errors_are_sanitized_and_not_retried(self):
        failures = (HTTPError("https://example.test", 429, "secret-key", {}, BytesIO(b"secret-key")),
                    URLError("secret-key"), TimeoutError("secret-key"), OSError("secret-key"),
                    IncompleteRead(b"partial"))
        for failure in failures:
            transport = MagicMock(side_effect=failure)
            with self.subTest(failure=failure), self.assertRaises(APIError) as caught:
                self.adapter(transport).generate(build_request(sample_recipe(), inventory()))
            self.assertNotIn("secret-key", str(caught.exception))
            self.assertEqual(transport.call_count, 1)

    def test_invalid_envelopes_refusals_and_truncation_preserve_only_model_text(self):
        for body in ("{bad secret-key", "[]", "{}", json.dumps({"choices": [{"finish_reason": "length",
                           "message": {"content": "{}"}}]}),
                     json.dumps({"choices": [{"finish_reason": "stop", "message": {
                         "refusal": "provider refusal", "content": None}}]})):
            transport = self.transport(body)
            with self.subTest(body=body), self.assertRaises(ResponseFormatError) as caught:
                self.adapter(transport).generate(build_request(sample_recipe(), inventory()))
            self.assertEqual(caught.exception.stage, "provider_response")
            self.assertEqual(caught.exception.raw_response, "{}" if '"length"' in body else None)
            self.assertNotIn("secret-key", str(caught.exception))
            self.assertEqual(transport.call_count, 1)

    def test_configuration_rejected_before_transport(self):
        for settings in ({"endpoint": "http://example.test"}, {"endpoint": "https://u:p@example.test"},
                         {"endpoint": "https://example.test?a=secret"}, {"model": ""}, {"api_key": ""},
                         {"timeout": float("nan")}, {"timeout": 0}, {"temperature": 3},
                         {"max_completion_tokens": -1}):
            config = {"endpoint": "https://example.test", "model": "test", "api_key": "secret", **settings}
            with self.subTest(config=settings), self.assertRaises(ValueError):
                ChatCompletionsLLM(**config)

    def test_environment_is_read_only_when_constructing_live_adapter(self):
        with patch.dict(os.environ, {"REVISION_LLM_ENDPOINT": "https://example.test/chat/completions",
                                     "REVISION_LLM_MODEL": "environment-model", "REVISION_LLM_API_KEY": "secret-key"}):
            adapter = ChatCompletionsLLM.from_environment()
        self.assertEqual(adapter.model, "environment-model")
        self.assertNotIn("secret-key", json.dumps(adapter.configuration()))

    def test_redirects_are_not_followed(self):
        self.assertIsNone(_NoRedirect().redirect_request(None, None, 307, "redirect", {}, "https://other.test"))

    def test_non_utf8_excludes_provider_body_and_stops_as_format_error(self):
        transport = self.transport("")
        transport.return_value.__enter__.return_value.read.return_value = b"invalid \xff body"
        with self.assertRaises(ResponseFormatError) as caught:
            self.adapter(transport).generate(build_request(sample_recipe(), inventory()))
        self.assertIsNone(caught.exception.raw_response)
        self.assertEqual(caught.exception.stage, "provider_response")
