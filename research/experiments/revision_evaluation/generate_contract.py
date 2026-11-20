# AI-assisted with Codex, 2026-11-20; reviewed by Soohyun An
"""Generate deterministic v1 JSON Schema and the committed contract fixture bundle."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .contract import (
    METADATA_SCHEMA,
    OBSERVATION_SCHEMA,
    SUMMARY_SCHEMA,
    fixture_root,
    schema_document,
    validate_artifact,
)

HERE = Path(__file__).resolve().parent
STAMP = "2026-11-20T00:00:00Z"
RUN_ID = "contract-v1-fixture"
HASH = "a" * 64


def _number(value: float | None = None, *, applicability: str | None = None) -> dict:
    """Build the explicit value/unavailable/not-applicable numeric representation."""

    state = applicability or ("value" if value is not None else "unavailable")
    return {"applicability": state, "value": value}


def _usage(input_tokens=None, output_tokens=None, reasoning_tokens=None, cached_tokens=None):
    """Build token usage while preserving independently missing categories."""

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "cached_tokens": cached_tokens,
    }


def _recipe() -> dict:
    """Return the deterministic source recipe shared by contract scenarios."""

    return {
        "dish_id": "fixture-rice",
        "source": "contract_fixture",
        "servings": 1,
        "ingredients": [
            {"name": "밥", "amount": "1공기", "role": "main"},
            {"name": "대파", "amount": "1/4대", "role": "secondary"},
            {"name": "소금", "amount": "1꼬집", "role": "seasoning"},
        ],
        "steps": [
            {"n": 1, "text": "대파를 썬다."},
            {"n": 2, "text": "밥과 함께 볶는다."},
        ],
        "tips": [],
    }


def _revised_answer(*, explain_omission: bool = True) -> dict:
    """Return a realistic model answer that omits the unavailable source ingredient."""

    change = {
        "kind": "omission",
        "reason": "대파가 없어서 생략했어요.",
        "ingredient_refs": [2],
        "step_refs": [1, 2],
    }
    return {
        "can_revise": True,
        "refusal_reason": "",
        "servings": 1,
        "ingredients": [
            {"name": "밥", "amount": "1공기"},
            {"name": "소금", "amount": "1꼬집"},
        ],
        "steps": ["밥에 소금을 넣고 볶는다."],
        "tips": [],
        "changes": [change] if explain_omission else [],
    }


def _service_response(answer: dict, *, availability=None) -> dict:
    """Project a checked model answer into the complete production response shape."""

    return {
        "status": "revised",
        "dish_id": "fixture-rice",
        "original": _recipe(),
        "availability": availability or ["owned", "unavailable", "assumed"],
        "revised": {
            "servings": answer["servings"],
            "ingredients": answer["ingredients"],
            "steps": [
                {"n": index, "text": text} for index, text in enumerate(answer["steps"], 1)
            ],
            "tips": answer["tips"],
        },
        "changes": answer["changes"],
        "refusal_reason": None,
        "error": None,
        "notice": "AI가 만든 제안이에요. 맛과 알레르기는 직접 확인해 주세요.",
    }


def _unchanged_response() -> dict:
    """Return the production no-call response, which uses status revised with identical content."""

    recipe = _recipe()
    answer = {
        "servings": recipe["servings"],
        "ingredients": [
            {"name": row["name"], "amount": row["amount"]} for row in recipe["ingredients"]
        ],
        "steps": [step["text"] for step in recipe["steps"]],
        "tips": recipe["tips"],
        "changes": [],
    }
    return _service_response(answer, availability=["owned", "owned", "assumed"])


def _request(purpose: str) -> dict:
    """Return a safe logical request snapshot for an initial call or re-ask."""

    return {
        "name": f"revision_{purpose}",
        "system": "Return the requested recipe revision as JSON.",
        "user": f"Fixture {purpose} request.",
        "schema": {"type": "object"},
        "sha256": HASH,
    }


def _http(index: int, status: int = 200, text: str = "{}", *, cost: float = 0.0001) -> dict:
    """Build a completed HTTP-attempt fixture with response data only on success."""

    return {
        "index": index,
        "state": "response_received",
        "prepared_at": STAMP,
        "request_sha256": HASH,
        "model": "fixture/model",
        "counts_against_budget": True,
        "delivery": "confirmed",
        "status_code": status,
        "provider_round_trip_s": 0.25,
        "finish_reason": "stop" if status == 200 else None,
        "safe_response_text": text if status == 200 else None,
        "usage": _usage(10, 20, 0, 0) if status == 200 else None,
        "cost_usd": _number(cost) if status == 200 else _number(),
    }


def _prepared(index: int) -> dict:
    """Build an uncertain pre-request checkpoint that still consumes attempt budget."""

    return {
        "index": index,
        "state": "request_prepared",
        "prepared_at": STAMP,
        "request_sha256": HASH,
        "model": "fixture/model",
        "counts_against_budget": True,
        "delivery": "unknown",
        "status_code": None,
        "provider_round_trip_s": None,
        "finish_reason": None,
        "safe_response_text": None,
        "usage": None,
        "cost_usd": _number(),
    }


def _call(index: int, purpose: str, attempts: list[dict], answer: Any, *, parsed=True) -> dict:
    """Build one logical call and keep JSON parsing distinct from answer structure."""

    return {
        "index": index,
        "purpose": purpose,
        "request": _request(purpose),
        "http_attempts": attempts,
        "parsing": {
            "attempted": any(a["safe_response_text"] is not None for a in attempts),
            "succeeded": parsed
            if any(a["safe_response_text"] is not None for a in attempts)
            else None,
            "error": None if parsed else "invalid JSON",
        },
        "decoded_answer": answer,
    }


def _telemetry(calls: list[dict], *, interrupted=False) -> dict:
    """Aggregate one attempt without inventing cost for interrupted delivery."""

    attempts = [attempt for call in calls for attempt in call["http_attempts"]]
    received = [attempt for attempt in attempts if attempt["state"] == "response_received"]
    input_tokens = sum((a["usage"] or {}).get("input_tokens", 0) for a in received)
    output_tokens = sum((a["usage"] or {}).get("output_tokens", 0) for a in received)
    measured = [a["cost_usd"]["value"] for a in received if a["cost_usd"]["value"] is not None]
    # A partial or interrupted set cannot be labelled as a complete measured total.
    cost = (
        _number(sum(measured)) if len(measured) == len(received) and not interrupted else _number()
    )
    return {
        "logical_calls": len(calls),
        "reasks": sum(call["purpose"] == "reask" for call in calls),
        "http_attempts": len(attempts),
        "http_429_retries": sum(a["status_code"] == 429 for a in attempts),
        "provider_round_trip_s": _number(sum(a["provider_round_trip_s"] or 0 for a in received))
        if received
        else _number(applicability="not_applicable"),
        "revision_s": _number(0.8) if not interrupted else _number(),
        "observed_wall_s": _number(0.82) if not interrupted else _number(),
        "checkpoint_persistence_s": _number(0.02),
        "non_http_remainder_s": _number(0.3) if received and not interrupted else _number(),
        "tokens": _usage(input_tokens, output_tokens, 0, 0) if received else _usage(),
        "cost_usd": cost,
    }


def _input(availability=None) -> dict:
    """Build the immutable input and effective assumed-staples snapshot."""

    return {
        "dish_id": "fixture-rice",
        "dish_name": "Fixture Rice",
        "supplied_ingredients": ["밥"],
        "effective_assumed_staples": ["소금"],
        "availability": availability or ["owned", "unavailable", "assumed"],
        "original_recipe": _recipe(),
    }


def _evaluation(
    calls: list[dict], *, structural=True, deleted_ingredient_explanation: tuple[int, int] = (0, 0)
) -> dict:
    """Build deterministic findings without repairing or discarding decoded answers."""

    answers = []
    for call in calls:
        parsed = call["parsing"]["succeeded"]
        answers.append(
            {
                "logical_call_index": call["index"],
                "structure_valid": structural if parsed else None,
                "reference_valid": structural if parsed else None,
                "issues": [] if structural or not parsed else ["missing required fields"],
            }
        )
    covered, total = deleted_ingredient_explanation
    return {
        "answers": answers,
        "deleted_ingredient_explanation": {
            "numerator": covered,
            "denominator": total,
            "value": covered / total if total else None,
        },
    }


def observation(
    case_id: str,
    outcome: str | None,
    source: str | None,
    calls: list[dict],
    *,
    execution_attempt: int = 1,
    state: str = "completed",
    checkpoint_stage: str = "terminal",
    checkpoint_revision: int = 1,
    checks: list[dict] | None = None,
    structural=True,
    error: str | None = None,
    final_response: dict | None = None,
    availability=None,
    deleted_ingredient_explanation: tuple[int, int] = (0, 0),
) -> dict:
    """Build and validate one terminal or interrupted execution-attempt artifact."""

    interrupted = state != "completed"
    value = {
        "artifact_schema": OBSERVATION_SCHEMA,
        "run_id": RUN_ID,
        "case_id": case_id,
        "repetition": 3 if case_id == "resumed" else 1,
        "execution_attempt": execution_attempt,
        "input": _input(availability),
        "execution": {
            "state": state,
            "checkpoint_revision": checkpoint_revision,
            "checkpoint_stage": checkpoint_stage,
            "started_at": STAMP,
            "finished_at": STAMP if not interrupted else None,
            "terminal_outcome": outcome,
            "outcome_source": source,
            "final_service_response": final_response,
            "sanitized_error": error,
        },
        "model_calls": calls,
        "checks": checks or [],
        "deterministic_evaluation": _evaluation(
            calls,
            structural=structural,
            deleted_ingredient_explanation=deleted_ingredient_explanation,
        ),
        "telemetry": _telemetry(calls, interrupted=interrupted),
    }
    validate_artifact(value)
    return value


def fixture_observations() -> dict[str, dict]:
    """Return representative observations for every required v1 execution path."""

    revised_answer = _revised_answer()
    unexplained_answer = _revised_answer(explain_omission=False)
    malformed = _call(1, "initial", [_http(1, text="{bad")], None, parsed=False)
    invalid = _call(1, "initial", [_http(1, text="[]")], [], parsed=True)
    first = _call(
        1,
        "initial",
        [
            _http(1, 429, cost=0),
            _http(2, text=json.dumps(unexplained_answer, ensure_ascii=False)),
        ],
        unexplained_answer,
    )
    second = _call(
        2,
        "reask",
        [_http(1, text=json.dumps(revised_answer, ensure_ascii=False))],
        revised_answer,
    )
    api_attempt = _http(1, status=503, cost=0)
    api_attempt["state"] = "transport_error"
    api_attempt["delivery"] = "failed"
    return {
        "unchanged__r01/attempt-001.json": observation(
            "unchanged",
            "unchanged",
            "no_change",
            [],
            final_response=_unchanged_response(),
            availability=["owned", "owned", "assumed"],
        ),
        "revised-after-reask-429__r01/attempt-001.json": observation(
            "revised-after-reask-429",
            "revised",
            "model",
            [first, second],
            checks=[
                {
                    "phase": "initial",
                    "result": "violation",
                    "code": "unexplained_change",
                    "message": "A dropped ingredient has no reason",
                },
                {"phase": "final", "result": "passed", "code": None, "message": None},
            ],
            final_response=_service_response(revised_answer),
            deleted_ingredient_explanation=(1, 1),
        ),
        "refused-prescreen__r01/attempt-001.json": observation(
            "refused-prescreen",
            "refused",
            "prescreen",
            [],
            final_response={"status": "refused", "refusal_reason": "missing identity"},
        ),
        "check-failed__r01/attempt-001.json": observation(
            "check-failed",
            "check_failed",
            "production_check",
            [
                _call(
                    1,
                    "initial",
                    [_http(1, text=json.dumps(unexplained_answer, ensure_ascii=False))],
                    unexplained_answer,
                ),
                _call(
                    2,
                    "reask",
                    [_http(1, text=json.dumps(unexplained_answer, ensure_ascii=False))],
                    unexplained_answer,
                ),
            ],
            checks=[
                {
                    "phase": "initial",
                    "result": "violation",
                    "code": "unexplained_change",
                    "message": "A dropped ingredient has no reason",
                },
                {
                    "phase": "final",
                    "result": "violation",
                    "code": "unexplained_change",
                    "message": "A dropped ingredient has no reason",
                },
            ],
            final_response={"status": "failed"},
        ),
        "response-error-json__r01/attempt-001.json": observation(
            "response-error-json",
            "response_error",
            "response",
            [malformed],
            error="invalid JSON",
        ),
        "response-error-structure__r01/attempt-001.json": observation(
            "response-error-structure",
            "response_error",
            "response",
            [invalid],
            structural=False,
            error="invalid response structure",
        ),
        "api-error__r01/attempt-001.json": observation(
            "api-error",
            "api_error",
            "transport",
            [_call(1, "initial", [api_attempt], None)],
            error="model service unavailable",
        ),
        "resumed__r03/attempt-001.json": observation(
            "resumed",
            None,
            None,
            [_call(1, "initial", [_prepared(1)], None)],
            execution_attempt=1,
            state="interrupted",
            checkpoint_stage="request_prepared",
            checkpoint_revision=2,
        ),
        "resumed__r03/attempt-002.json": observation(
            "resumed",
            "revised",
            "model",
            [
                _call(
                    1,
                    "initial",
                    [_http(1, text=json.dumps(revised_answer, ensure_ascii=False))],
                    revised_answer,
                )
            ],
            execution_attempt=2,
            checkpoint_revision=4,
            final_response=_service_response(revised_answer),
            deleted_ingredient_explanation=(1, 1),
        ),
    }


def fixture_metadata(observations: dict[str, dict]) -> dict:
    """Build run metadata that selects completed attempts but retains interrupted ones."""

    refs = {name: f"observations/{name}" for name in observations}
    plan = []
    for name, value in observations.items():
        if value["execution_attempt"] != 1 or value["case_id"] == "resumed":
            continue
        plan.append(
            {
                "case_id": value["case_id"],
                "repetition": value["repetition"],
                "state": "completed",
                "observation_refs": [refs[name]],
                "selected_completed_attempt": 1,
            }
        )
    plan.append(
        {
            "case_id": "resumed",
            "repetition": 3,
            "state": "completed",
            "observation_refs": [
                refs["resumed__r03/attempt-001.json"],
                refs["resumed__r03/attempt-002.json"],
            ],
            "selected_completed_attempt": 2,
        }
    )
    consumed = sum(value["telemetry"]["http_attempts"] for value in observations.values())
    value = {
        "artifact_schema": METADATA_SCHEMA,
        "observation_schema": OBSERVATION_SCHEMA,
        "run_id": RUN_ID,
        "state": "completed",
        "created_at": STAMP,
        "updated_at": STAMP,
        "compatibility_fingerprint": "b" * 64,
        "effective_assumed_staples": ["소금"],
        "model": {"id": "fixture/model", "temperature": 0},
        "pricing": {
            "source": "fixture",
            "input_per_million_usd": 0.1,
            "output_per_million_usd": 0.4,
        },
        "http_attempt_budget": {"maximum": 20, "consumed": consumed, "remaining": 20 - consumed},
        "plan": plan,
        "resume_history": [{"resumed_at": STAMP, "from_execution_attempt": 1}],
    }
    validate_artifact(value)
    return value


def fixture_summary(observations: dict[str, dict]) -> dict:
    """Build authoritative aggregate metrics from every fixture observation."""

    completed = [v for v in observations.values() if v["execution"]["state"] == "completed"]
    outcomes = {
        name: 0
        for name in (
            "unchanged",
            "revised",
            "refused",
            "check_failed",
            "response_error",
            "api_error",
        )
    }
    for value in completed:
        outcomes[value["execution"]["terminal_outcome"]] += 1
    returned = [
        call
        for value in observations.values()
        for call in value["model_calls"]
        if call["parsing"]["attempted"]
    ]
    parsed = [call for call in returned if call["parsing"]["succeeded"]]
    structurally_valid = sum(
        finding["structure_valid"] is True
        for value in observations.values()
        for finding in value["deterministic_evaluation"]["answers"]
        if finding["structure_valid"] is not None
    )
    total_attempts = sum(v["telemetry"]["http_attempts"] for v in observations.values())
    explanation_numerator = sum(
        value["deterministic_evaluation"]["deleted_ingredient_explanation"]["numerator"]
        for value in observations.values()
    )
    explanation_denominator = sum(
        value["deterministic_evaluation"]["deleted_ingredient_explanation"]["denominator"]
        for value in observations.values()
    )
    value = {
        "artifact_schema": SUMMARY_SCHEMA,
        "observation_schema": OBSERVATION_SCHEMA,
        "run_id": RUN_ID,
        "complete": True,
        "generated_at": STAMP,
        "observation_refs": [f"observations/{name}" for name in observations],
        "outcomes": outcomes,
        "json_parse_success": {
            "numerator": len(parsed),
            "denominator": len(returned),
            "value": len(parsed) / len(returned),
        },
        "structural_validity": {
            "numerator": structurally_valid,
            "denominator": len(parsed),
            "value": structurally_valid / len(parsed),
        },
        "reference_validity": {
            "numerator": structurally_valid,
            "denominator": len(parsed),
            "value": structurally_valid / len(parsed),
        },
        "explanation_coverage": {
            "numerator": explanation_numerator,
            "denominator": explanation_denominator,
            "value": explanation_numerator / explanation_denominator
            if explanation_denominator
            else None,
        },
        "totals": {
            "completed_repetitions": len(completed),
            "incomplete_attempts": len(observations) - len(completed),
            "logical_calls": sum(v["telemetry"]["logical_calls"] for v in observations.values()),
            "http_attempts": total_attempts,
            "tokens": _usage(),
            "cost_usd": _number(),
        },
    }
    validate_artifact(value)
    return value


def _write(path: Path, value: dict) -> None:
    """Write canonical UTF-8 JSON so committed assets remain deterministic."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def generate() -> list[Path]:
    """Regenerate all committed contract assets and return their paths."""
    observations = fixture_observations()
    paths = [HERE / "schema.json"]
    _write(paths[0], schema_document())
    root = fixture_root()
    for relative, value in observations.items():
        path = root / "observations" / relative
        _write(path, value)
        paths.append(path)
    for name, value in (
        ("metadata.json", fixture_metadata(observations)),
        ("summary.json", fixture_summary(observations)),
    ):
        path = root / name
        _write(path, value)
        paths.append(path)
    return paths


def content_digest(path: Path) -> str:
    """Return a stable digest used by deterministic-generation tests."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    for generated in generate():
        print(generated.relative_to(HERE))
