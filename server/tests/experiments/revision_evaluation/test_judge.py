# AI-generated Judge contract tests with Codex, 2026-11-22; reviewed by Soohyun An
"""Offline contract tests for the minimal single-observation Revision Judge."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from experiments.revision_evaluation import judge
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


@pytest.fixture(autouse=True)
def isolated_credentials(monkeypatch, tmp_path):
    """Redirect dotenv to a disposable file and restore any loaded test key afterward."""
    monkeypatch.setattr(judge, "SERVER_ENV_FILE", tmp_path / ".env")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.delenv("OPENROUTER_API_KEY")


def _fixture(name: str) -> Path:
    return fixture_root() / "observations" / name / "attempt-001.json"


def _criterion(state="scored", score=2, evidence=None) -> dict:
    reason = None if state == "scored" and score == 2 else "판단 근거"
    return {"state": state, "score": score, "reason": reason, "evidence": evidence}


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
    value["criteria"]["B"] = _criterion("deferred", None)
    value["criteria"]["B"]["reason"] = "대체 재료 상태 정보 부족"
    assert validate_judgment(value, revised)


@pytest.mark.parametrize(
    "case",
    ["a_na", "b_mismatch", "c_mismatch", "c_single_one", "d_na", "deduction_no_evidence",
     "deferred_no_reason", "changed_e_na", "changed_e_deferred", "extra_field",
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
    elif case == "deferred_no_reason":
        value["criteria"]["B"] = _criterion("deferred", None)
        value["criteria"]["B"]["reason"] = None
    elif case == "changed_e_na":
        value["criteria"]["E"] = _criterion("not_applicable", None)
    elif case == "changed_e_deferred":
        value["criteria"]["E"] = _criterion("deferred", None)
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


@pytest.mark.parametrize("score", [0, 1])
def test_compact_output_preserves_deductions_and_missing_information(score):
    prepared = prepare_observation(_fixture("revised-after-reask-429__r01"))
    value = _judgment(prepared)
    value["criteria"]["B"] = _criterion("scored", score, ["필요한 역할 미충족"])
    value["criteria"]["A"] = _criterion("deferred", None)
    value["criteria"]["A"]["reason"] = "요리 정체성 판단에 필요한 원본 정보 부족"
    output = validate_judgment(value, prepared)["criteria"]
    assert output["B"] == value["criteria"]["B"]
    assert output["A"] == {
        "state": "deferred", "score": None,
        "reason": "요리 정체성 판단에 필요한 원본 정보 부족",
    }
    assert output["D"] == {"state": "scored", "score": 2}


@pytest.mark.parametrize(
    "state,score,field,content",
    [("scored", 2, "reason", "잘 반영됨"), ("scored", 2, "evidence", ["일치함"]),
     ("scored", 0, "reason", None), ("scored", 1, "evidence", None),
     ("scored", 1, "evidence", []), ("deferred", None, "reason", " "),
     ("deferred", None, "evidence", ["추가 설명"]),
     ("not_applicable", None, "evidence", ["불필요한 근거"])],
)
def test_invalid_compact_explanation_fields(state, score, field, content):
    prepared = prepare_observation(_fixture("revised-after-reask-429__r01"))
    value = _judgment(prepared)
    value["criteria"]["B"] = _criterion(
        state, score, ["감점 근거"] if state == "scored" and score != 2 else None
    )
    if state == "not_applicable":
        value["method_choices"] = []
    value["criteria"]["B"][field] = content
    with pytest.raises(JudgeOutputError):
        validate_judgment(value, prepared)


def test_refused_output_and_strict_nullable_provider_schema():
    prepared = prepare_observation(_fixture("refused-prescreen__r01"))
    output = validate_judgment(_judgment(prepared), prepared)["criteria"]
    assert output["A"] == {"state": "scored", "score": 2}
    assert output["B"] == {
        "state": "not_applicable", "score": None, "reason": "판단 근거"
    }
    schema = judge.JUDGMENT_SCHEMA["$defs"]["Criterion"]
    assert set(schema["required"]) == {"state", "score", "reason", "evidence"}
    for field in ("reason", "evidence"):
        assert {"type": "null"} in schema["properties"][field]["anyOf"]
        invalid = _judgment(prepared)
        del invalid["criteria"]["A"][field]
        with pytest.raises(JudgeOutputError):
            validate_judgment(invalid, prepared)


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
    assert output["artifact_schema"] == "revision-evaluation-judgment/v2"
    assert output["judgment"]["criteria"]["D"] == {"state": "scored", "score": 2}
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


@pytest.mark.parametrize(
    "file_key,process_key,expected_key",
    [("file-key", None, "file-key"), ("file-key", "process-key", "process-key"),
     (None, "process-key", "process-key"), (None, None, None),
     ("", None, None), ("   ", None, None),
     ("file-key", "", None), ("file-key", "   ", None)],
)
def test_live_credentials_from_file_or_environment(
    file_key, process_key, expected_key, monkeypatch, tmp_path, capsys
):
    path = _fixture("revised-after-reask-429__r01")
    prepared = prepare_observation(path)
    if file_key is not None:
        judge.SERVER_ENV_FILE.write_text(
            f'OPENROUTER_API_KEY="{file_key}"\nDISH_LLM_MODEL=file-model\n', encoding="utf-8"
        )
    if process_key is not None:
        monkeypatch.setenv("OPENROUTER_API_KEY", process_key)
    monkeypatch.setenv("DISH_LLM_MODEL", "process-model")
    monkeypatch.chdir(tmp_path)
    calls = []

    class Model:
        def complete(self, *args):
            return _judgment(prepared)

    def factory(key, model):
        calls.append((key, model))
        return Model()

    code = main([str(path), "--allow-live-api"], model_factory=factory)
    captured = capsys.readouterr()
    if expected_key is None:
        assert code == 2 and calls == [] and captured.out == ""
        assert captured.err == "revision Judge rejected the input\n"
    else:
        assert code == 0 and calls == [(expected_key, judge.DEFAULT_MODEL)]
        assert json.loads(captured.out)["judge_model"] == judge.DEFAULT_MODEL
        assert expected_key not in captured.out + captured.err


@pytest.mark.parametrize("mode", ["offline", "ineligible", "invalid"])
def test_non_live_or_invalid_input_never_loads_credentials(mode, monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError("credentials or model accessed before valid live opt-in")

    monkeypatch.setattr(judge, "load_dotenv", forbidden)
    name = "unchanged__r01" if mode == "ineligible" else "revised-after-reask-429__r01"
    path = _fixture(name) if mode != "invalid" else judge.SERVER_ENV_FILE
    args = [str(path)] + ([] if mode == "offline" else ["--allow-live-api"])
    assert main(args, model_factory=forbidden) == (0 if mode == "offline" else 2)
    capsys.readouterr()


@pytest.mark.parametrize("error", [OSError("private-file-secret"), UnicodeError("private-key")])
def test_dotenv_read_errors_are_safe(error, monkeypatch, capsys):
    def fail(*args, **kwargs):
        raise error

    def forbidden(*args):
        raise AssertionError("model constructed after credentials failure")

    monkeypatch.setattr(judge, "load_dotenv", fail)
    path = _fixture("revised-after-reask-429__r01")
    assert main([str(path), "--allow-live-api"], model_factory=forbidden) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "revision Judge rejected the input\n"
