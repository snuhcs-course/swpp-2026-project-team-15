"""Offline protocol fixtures, explicitly not AI feasibility judgments."""
# AI-generated initial importer with Codex (GPT-6.1 Sol)
# 2026-10-14 to 2026-10-16; reviewed and revised by Soohyun An

import json
from pathlib import Path

from server.recipe_revision import APIError, LLMResponse, RevisionRequest
from .cases import Case, INVENTORIES, matrix

MOCK_REFUSAL = json.dumps({"result": {
    "can_revise": False, "reason": "MOCK ONLY: 판단을 생성하지 않는 오프라인 실행 확인용 결과입니다.",
    "changes": [], "revised_recipe": None,
}}, ensure_ascii=False)


class MockLLM:
    """Use canned outputs in matrix order; never import a network transport.

    A file maps selected, original 32 or all 40 case IDs to raw strings or api_error objects.
    Raw strings are intentional so malformed-response scenarios are reproducible.
    """

    def __init__(self, responses: dict | None = None, *, cases: tuple[Case, ...] | None = None):
        self.calls = 0
        self._cases = matrix() if cases is None else cases
        self._responses = responses
        if responses is not None:
            if not {case.case_id for case in self._cases} <= set(responses):
                raise ValueError("Mock fixtures must include every selected case ID")
            if set(responses) not in ({case.case_id for case in self._cases},
                                      {case.case_id for case in matrix()},
                                      {case.case_id for case in matrix(tuple(INVENTORIES))}):
                raise ValueError("Mock fixtures must contain exactly the selected, original 32 or all 40 case IDs")
            for value in responses.values():
                if not isinstance(value, str) and not (
                    isinstance(value, dict) and set(value) == {"api_error"}
                    and isinstance(value["api_error"], str) and value["api_error"].strip()
                ):
                    raise ValueError("Mock response must be raw text or a nonempty api_error object")

    @classmethod
    def from_file(cls, path: Path, *, cases: tuple[Case, ...] | None = None):
        """Read explicit local fixtures without inspecting live credentials."""
        values = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(values, dict):
            raise ValueError("Mock fixtures must be a case-ID mapping")
        return cls(values, cases=cases)

    def configuration(self) -> dict:
        return {"provider": "mock", "model": "offline-fixture-v1",
                "fixture_mode": "scripted" if self._responses is not None else "canned-refusal",
                "is_mock": True}

    def generate(self, request: RevisionRequest) -> LLMResponse:
        """Return one fixture, preserving the independent request API."""
        case = self._cases[self.calls]
        self.calls += 1
        value = self._responses[case.case_id] if self._responses is not None else MOCK_REFUSAL
        if isinstance(value, dict):
            raise APIError(value["api_error"])
        return LLMResponse(value, {"is_mock": True})
