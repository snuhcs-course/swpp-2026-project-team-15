# AI-generated Judge contract tests with Codex, 2026-11-22; reviewed by Soohyun An
"""Offline contract tests for the minimal single-observation Revision Judge."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from experiments.revision_evaluation.contract import fixture_root
from experiments.revision_evaluation.judge import (
    JUDGE_MAX_TOKENS,
    PROMPT_SHA256,
    RUBRIC_ID,
    JudgeInputError,
    JudgeOutputError,
    main,
    prepare_observation,
    validate_judgment,
)

from app.dishes.llm import DishLLM


def _fixture(name: str) -> Path:
    return fixture_root() / "observations" / name / "attempt-001.json"


def _criterion(state="scored", score=2, evidence=None) -> dict:
    return {"state": state, "score": score, "reason": "판단 근거", "evidence": evidence or []}


def _judgment(prepared) -> dict:
    refused = prepared.observation.execution.terminal_outcome == "refused"
    criteria = {name: _criterion() for name in "ABCDE"}
    if refused:
        criteria.update({name: _criterion("not_applicable", None) for name in "BCDE"})
    elif not prepared.actual_change:
        criteria["E"] = _criterion("not_applicable", None)
    return {
        "method_choices": [] if refused else ["대파 생략"],
        "required_adjustments": [] if refused else ["대파 준비 단계 제거"],
        "criteria": criteria,
    }


def test_status_specific_payload_is_complete_and_minimal():
    revised = prepare_observation(_fixture("revised-after-reask-429__r01"))
    refused = prepare_observation(_fixture("refused-prescreen__r01"))
    assert set(revised.payload) == {
        "inventory", "effective_staples", "dish_name", "original", "result"
    }
    assert revised.payload["original"]["ingredients"][1] == {
        "name": "대파", "amount": "1/4대", "role": "secondary", "availability": "unavailable"
    }
    assert revised.payload["result"]["changes"][0]["reason"] == "대파가 없어서 생략했어요."
    assert refused.payload["result"] == {"status": "refused", "reason": "missing identity"}
    encoded = json.dumps(revised.payload, ensure_ascii=False)
    for excluded in ("model_calls", "checks", "deterministic_evaluation", "telemetry", "expect"):
        assert excluded not in encoded


@pytest.mark.parametrize(
    "name",
    ["unchanged__r01", "check-failed__r01", "response-error-json__r01",
     "response-error-structure__r01", "api-error__r01", "resumed__r03"],
)
def test_ineligible_observations_are_rejected(name):
    with pytest.raises(JudgeInputError):
        prepare_observation(_fixture(name))


def test_valid_applicability_and_deferral_variants():
    revised = prepare_observation(_fixture("revised-after-reask-429__r01"))
    refused = prepare_observation(_fixture("refused-prescreen__r01"))
    assert validate_judgment(_judgment(revised), revised)
    assert validate_judgment(_judgment(refused), refused)
    value = _judgment(revised)
    value["method_choices"] = value["required_adjustments"] = []
    value["criteria"]["B"] = value["criteria"]["C"] = _criterion("not_applicable", None)
    assert validate_judgment(value, revised)
    value = _judgment(revised)
    value["criteria"]["B"] = _criterion("deferred", None, ["대체 재료 상태 정보"])
    assert validate_judgment(value, revised)


@pytest.mark.parametrize(
    "case",
    ["a_na", "b_mismatch", "c_mismatch", "c_single_one", "d_na", "deduction_no_evidence",
     "deferred_no_evidence", "changed_e_na", "changed_e_deferred", "extra_field",
     "refused_subject", "refused_b"],
)
def test_invalid_score_state_contracts(case):
    refused = case.startswith("refused")
    prepared = prepare_observation(
        _fixture("refused-prescreen__r01" if refused else "revised-after-reask-429__r01")
    )
    value = _judgment(prepared)
    if case == "a_na":
        value["criteria"]["A"] = _criterion("not_applicable", None)
    elif case == "b_mismatch":
        value["method_choices"] = []
    elif case == "c_mismatch":
        value["required_adjustments"] = []
    elif case == "c_single_one":
        value["criteria"]["C"] = _criterion("scored", 1, ["일부 반영"])
    elif case == "d_na":
        value["criteria"]["D"] = _criterion("not_applicable", None)
    elif case == "deduction_no_evidence":
        value["criteria"]["A"] = _criterion("scored", 1)
    elif case == "deferred_no_evidence":
        value["criteria"]["B"] = _criterion("deferred", None)
    elif case == "changed_e_na":
        value["criteria"]["E"] = _criterion("not_applicable", None)
    elif case == "changed_e_deferred":
        value["criteria"]["E"] = _criterion("deferred", None, ["변경 설명 판단 근거 부족"])
    elif case == "extra_field":
        value["aggregate_pass"] = True
    elif case == "refused_subject":
        value["method_choices"] = ["없는 선택"]
    elif case == "refused_b":
        value["criteria"]["B"] = _criterion()
    with pytest.raises(JudgeOutputError):
        validate_judgment(value, prepared)


def test_e_uses_actual_change_before_explanation_presence():
    source = prepare_observation(_fixture("revised-after-reask-429__r01"))
    unexplained = replace(source, has_change_explanation=False)
    with pytest.raises(JudgeOutputError):
        validate_judgment(_judgment(unexplained), unexplained)
    zero = _judgment(unexplained)
    zero["criteria"]["E"] = _criterion("scored", 0, ["변경 설명 없음"])
    assert validate_judgment(zero, unexplained)
    unchanged = replace(source, actual_change=False, has_change_explanation=False)
    assert validate_judgment(_judgment(unchanged), unchanged)


def test_offline_preview_makes_zero_calls_and_preserves_source(capsys):
    path = _fixture("revised-after-reask-429__r01")
    before = path.read_bytes()

    def forbidden_factory(key, model):
        raise AssertionError("offline preview constructed a model")

    assert main([str(path)], model_factory=forbidden_factory) == 0
    output = json.loads(capsys.readouterr().out)
    assert (output["judge_calls"], output["rubric_id"], output["prompt_sha256"]) == (
        0, RUBRIC_ID, PROMPT_SHA256
    )
    assert path.read_bytes() == before


def test_live_mode_calls_existing_client_once_and_links_source(monkeypatch, capsys):
    path = _fixture("revised-after-reask-429__r01")
    prepared, calls = prepare_observation(path), []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        answer = {"choices": [{"finish_reason": "stop", "message": {
            "content": json.dumps(_judgment(prepared))}}]}
        return httpx.Response(200, json=answer)

    def factory(key: str, model: str) -> DishLLM:
        return DishLLM(key, model, transport=httpx.MockTransport(handler), retry_waits=())

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    args = [str(path), "--allow-live-api", "--model", "judge-model"]
    assert main(args, model_factory=factory) == 0
    output = json.loads(capsys.readouterr().out)
    assert len(calls) == 1 and calls[0]["max_tokens"] == JUDGE_MAX_TOKENS
    assert output["judge_model"] == "judge-model"
    assert output["source"]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_invalid_live_output_uses_fixed_safe_failure(monkeypatch, capsys):
    class InvalidModel:
        def complete(self, *args):
            return {"private": "provider-secret"}

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    path = _fixture("revised-after-reask-429__r01")
    assert main([str(path), "--allow-live-api"], model_factory=lambda *_: InvalidModel()) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "revision Judge rejected the model output\n"
    assert "provider-secret" not in captured.err
