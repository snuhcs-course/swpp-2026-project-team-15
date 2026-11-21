# AI-assisted with Codex, 2026-11-20; reviewed by Soohyun An
"""Generate deterministic v1 JSON Schema and the committed contract fixture bundle."""

from __future__ import annotations

import hashlib
import json
import math
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


def _cost(
    value: float | None = None,
    *,
    provenance: str | None = None,
    price_inputs: dict[str, float] | None = None,
    confirmed_subtotal: float | None = None,
) -> dict:
    """Build a cost value with explicit measured, estimated, missing, or N/A provenance."""

    source = provenance or ("measured" if value is not None else "missing")
    applicability = {
        "measured": "value",
        "estimated": "value",
        "missing": "unavailable",
        "not_applicable": "not_applicable",
    }[source]
    return {
        "applicability": applicability,
        "value": value,
        "confirmed_subtotal": (
            value
            if value is not None
            else confirmed_subtotal
            if confirmed_subtotal
            else 0
        ),
        "provenance": source,
        "price_inputs": price_inputs,
    }


def _usage(
    input_tokens=None, output_tokens=None, reasoning_tokens=None, cached_tokens=None
):
    """Build token usage while preserving independently missing categories."""

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "cached_tokens": cached_tokens,
    }


def _token_total(
    value: int | None = None,
    *,
    applicability: str | None = None,
    confirmed_subtotal: int = 0,
) -> dict:
    """Build a complete, partial, or inapplicable aggregate token count."""

    state = applicability or ("value" if value is not None else "unavailable")
    return {
        "applicability": state,
        "value": value,
        "confirmed_subtotal": value if value is not None else confirmed_subtotal,
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
                {"n": index, "text": text}
                for index, text in enumerate(answer["steps"], 1)
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
            {"name": row["name"], "amount": row["amount"]}
            for row in recipe["ingredients"]
        ],
        "steps": [step["text"] for step in recipe["steps"]],
        "tips": recipe["tips"],
        "changes": [],
    }
    return _service_response(answer, availability=["owned", "owned", "assumed"])


def _refused_response(reason: str) -> dict:
    """Return the complete production response for a prescreen refusal."""

    return {
        "status": "refused",
        "dish_id": "fixture-rice",
        "original": _recipe(),
        "availability": ["owned", "unavailable", "assumed"],
        "revised": None,
        "changes": [],
        "refusal_reason": reason,
        "error": None,
        "notice": "AI가 만든 제안이에요. 맛과 알레르기는 직접 확인해 주세요.",
    }


def _failed_response(code: str) -> dict:
    """Return the complete production response for a rejected model answer."""

    return {
        "status": "failed",
        "dish_id": "fixture-rice",
        "original": _recipe(),
        "availability": ["owned", "unavailable", "assumed"],
        "revised": None,
        "changes": [],
        "refusal_reason": None,
        "error": {
            "code": code,
            "message": "바꾼 레시피가 규칙을 어겨서 보여 드릴 수 없어요.",
        },
        "notice": "AI가 만든 제안이에요. 맛과 알레르기는 직접 확인해 주세요.",
    }


def _request(purpose: str) -> dict:
    """Return a safe logical request snapshot for an initial call or re-ask."""

    return {
        "name": f"revision_{purpose}",
        "system": "Return the requested recipe revision as JSON.",
        "user": f"Fixture {purpose} request.",
        "schema": {"type": "object"},
        "sha256": HASH,
    }


def _http(
    index: int, status: int = 200, text: str = "{}", *, cost: float = 0.0001
) -> dict:
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
        "cost_usd": _cost(cost) if status == 200 else _cost(),
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
        "cost_usd": _cost(),
    }


def _transport_error(index: int) -> dict:
    """Build a failed transport attempt without fabricating an HTTP response."""

    return {
        "index": index,
        "state": "transport_error",
        "prepared_at": STAMP,
        "request_sha256": HASH,
        "model": "fixture/model",
        "counts_against_budget": True,
        "delivery": "failed",
        "status_code": None,
        "provider_round_trip_s": 0.25,
        "finish_reason": None,
        "safe_response_text": None,
        "usage": None,
        "cost_usd": _cost(),
    }


def _call(
    index: int, purpose: str, attempts: list[dict], answer: Any, *, parsed=True
) -> dict:
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
    received = [
        attempt for attempt in attempts if attempt["state"] == "response_received"
    ]
    timed = [
        attempt for attempt in attempts if attempt["provider_round_trip_s"] is not None
    ]
    usage = _sum_usage(
        [
            attempt["usage"] if attempt["usage"] is not None else _usage()
            for attempt in attempts
        ]
    )
    measured = [
        a["cost_usd"]["value"] for a in received if a["cost_usd"]["value"] is not None
    ]
    # A partial or interrupted set cannot be labelled as a complete measured total.
    if not attempts:
        cost = _cost(provenance="not_applicable")
    elif len(measured) == len(received) == len(attempts) and not interrupted:
        cost = _cost(sum(measured))
    else:
        cost = _cost(confirmed_subtotal=sum(measured))
    return {
        "logical_calls": len(calls),
        "reasks": sum(call["purpose"] == "reask" for call in calls),
        "http_attempts": len(attempts),
        "http_429_responses": sum(a["status_code"] == 429 for a in attempts),
        "http_429_retries": sum(
            previous["status_code"] == 429
            for call in calls
            for previous in call["http_attempts"][:-1]
        ),
        "provider_round_trip_s": _number(sum(a["provider_round_trip_s"] for a in timed))
        if timed
        else _number(applicability="not_applicable"),
        "revision_s": _number(0.8) if not interrupted else _number(),
        "observed_wall_s": _number(0.82) if not interrupted else _number(),
        "checkpoint_persistence_s": _number(0.02),
        "non_http_remainder_s": _number(0.3)
        if received and not interrupted
        else _number(),
        "tokens": usage,
        "cost_usd": cost,
    }


def _sum_optional(values: list[dict]) -> dict:
    """Sum compatible optional measurements without converting unknown values to zero."""

    applicable = [
        value for value in values if value["applicability"] != "not_applicable"
    ]
    if not applicable:
        return _number(applicability="not_applicable")
    if any(value["applicability"] != "value" for value in applicable):
        return _number()
    return _number(sum(value["value"] for value in applicable))


def _sum_usage(values: list[dict]) -> dict:
    """Aggregate raw usage while retaining known subtotals and applicability."""

    if not values:
        return {
            key: _token_total(applicability="not_applicable")
            for key in (
                "input_tokens",
                "output_tokens",
                "reasoning_tokens",
                "cached_tokens",
            )
        }
    result = {}
    for key in ("input_tokens", "output_tokens", "reasoning_tokens", "cached_tokens"):
        entries = [value[key] for value in values]
        subtotal = sum(value for value in entries if value is not None)
        result[key] = (
            _token_total(subtotal)
            if all(value is not None for value in entries)
            else _token_total(confirmed_subtotal=subtotal)
        )
    return result


def _sum_token_totals(values: list[dict]) -> dict:
    """Combine attempt aggregates without treating N/A as missing usage."""

    result = {}
    for key in ("input_tokens", "output_tokens", "reasoning_tokens", "cached_tokens"):
        entries = [value[key] for value in values]
        applicable = [
            entry for entry in entries if entry["applicability"] != "not_applicable"
        ]
        subtotal = sum(entry["confirmed_subtotal"] for entry in applicable)
        if not applicable:
            result[key] = _token_total(applicability="not_applicable")
        elif all(entry["applicability"] == "value" for entry in applicable):
            result[key] = _token_total(subtotal)
        else:
            result[key] = _token_total(confirmed_subtotal=subtotal)
    return result


def _sum_cost(values: list[dict]) -> dict:
    """Aggregate only complete measured costs; otherwise retain missing or N/A provenance."""

    applicable = [value for value in values if value["provenance"] != "not_applicable"]
    if not applicable:
        return _cost(provenance="not_applicable")
    if all(value["provenance"] == "measured" for value in applicable):
        return _cost(sum(value["value"] for value in applicable))
    return _cost(
        confirmed_subtotal=sum(value["confirmed_subtotal"] for value in applicable)
    )


def _aggregate_telemetry(values: list[dict]) -> dict:
    """Build cumulative telemetry for all execution attempts of one repetition."""

    return {
        "logical_calls": sum(value["logical_calls"] for value in values),
        "reasks": sum(value["reasks"] for value in values),
        "http_attempts": sum(value["http_attempts"] for value in values),
        "http_429_responses": sum(value["http_429_responses"] for value in values),
        "http_429_retries": sum(value["http_429_retries"] for value in values),
        "provider_round_trip_s": _sum_optional(
            [value["provider_round_trip_s"] for value in values]
        ),
        "revision_s": _sum_optional([value["revision_s"] for value in values]),
        "observed_wall_s": _sum_optional(
            [value["observed_wall_s"] for value in values]
        ),
        "checkpoint_persistence_s": _sum_optional(
            [value["checkpoint_persistence_s"] for value in values]
        ),
        "non_http_remainder_s": _sum_optional(
            [value["non_http_remainder_s"] for value in values]
        ),
        "tokens": _sum_token_totals([value["tokens"] for value in values]),
        "cost_usd": _sum_cost([value["cost_usd"] for value in values]),
    }


def _percentiles(values: list[float]) -> dict:
    """Build deterministic linearly interpolated p50/p95 values for completed attempts."""

    ordered = sorted(values)

    def percentile(quantile: float) -> float:
        position = (len(ordered) - 1) * quantile
        lower, upper = math.floor(position), math.ceil(position)
        if lower == upper:
            return ordered[lower]
        return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)

    if not ordered:
        return {
            "sample_count": 0,
            "incomplete_attempt_policy": "exclude",
            "p50_s": _number(applicability="not_applicable"),
            "p95_s": _number(applicability="not_applicable"),
        }
    return {
        "sample_count": len(ordered),
        "incomplete_attempt_policy": "exclude",
        "p50_s": _number(percentile(0.5)),
        "p95_s": _number(percentile(0.95)),
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
    calls: list[dict],
    *,
    structural=True,
    deleted_ingredient_explanation: tuple[int, int] = (0, 0),
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
                "issues": []
                if structural or not parsed
                else ["missing required fields"],
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
    api_attempt = _transport_error(1)
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
            final_response=_refused_response("missing identity"),
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
            final_response=_failed_response("unexplained_change"),
            # A rejected answer still deleted a source row; lack of explanation
            # counts as uncovered rather than removing the row from the denominator.
            deleted_ingredient_explanation=(0, 1),
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
                "cumulative_telemetry": _aggregate_telemetry([value["telemetry"]]),
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
            "cumulative_telemetry": _aggregate_telemetry(
                [
                    observations["resumed__r03/attempt-001.json"]["telemetry"],
                    observations["resumed__r03/attempt-002.json"]["telemetry"],
                ]
            ),
        }
    )
    consumed = sum(
        value["telemetry"]["http_attempts"] for value in observations.values()
    )
    value = {
        "artifact_schema": METADATA_SCHEMA,
        "observation_schema": OBSERVATION_SCHEMA,
        "run_id": RUN_ID,
        "state": "completed",
        "created_at": STAMP,
        "updated_at": STAMP,
        "compatibility_fingerprint": "b" * 64,
        "code_identity": {"commit": "c" * 40, "tree": "d" * 40, "dirty": False},
        "identities": {
            "prompt_sha256": "e" * 64,
            "response_schema_sha256": "f" * 64,
            "input_sha256": {value["case_id"]: HASH for value in observations.values()},
            "fixture_sha256": {"contract-v1": "1" * 64},
        },
        "effective_assumed_staples": ["소금"],
        "model": {"id": "fixture/model", "temperature": 0},
        "pricing": {
            "source": "fixture",
            "input_per_million_usd": 0.1,
            "output_per_million_usd": 0.4,
        },
        "http_attempt_budget": {
            "maximum": 20,
            "consumed": consumed,
            "remaining": 20 - consumed,
        },
        "plan": plan,
        "resume_history": [{"resumed_at": STAMP, "from_execution_attempt": 1}],
    }
    validate_artifact(value)
    return value


def fixture_summary(observations: dict[str, dict]) -> dict:
    """Build authoritative aggregate metrics from every fixture observation."""

    completed = [
        v for v in observations.values() if v["execution"]["state"] == "completed"
    ]
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
    answer_findings = [
        finding
        for value in observations.values()
        for finding in value["deterministic_evaluation"]["answers"]
    ]
    structural_findings = [
        finding for finding in answer_findings if finding["structure_valid"] is not None
    ]
    reference_findings = [
        finding for finding in answer_findings if finding["reference_valid"] is not None
    ]
    structurally_valid = sum(
        finding["structure_valid"] is True for finding in structural_findings
    )
    references_valid = sum(
        finding["reference_valid"] is True for finding in reference_findings
    )
    total_attempts = sum(v["telemetry"]["http_attempts"] for v in observations.values())
    explanation_numerator = sum(
        value["deterministic_evaluation"]["deleted_ingredient_explanation"]["numerator"]
        for value in observations.values()
    )
    explanation_denominator = sum(
        value["deterministic_evaluation"]["deleted_ingredient_explanation"][
            "denominator"
        ]
        for value in observations.values()
    )
    initial_failure_codes: dict[str, int] = {}
    final_failure_codes: dict[str, int] = {}
    for observation_value in observations.values():
        for check in observation_value["checks"]:
            if check["code"] is None or check["result"] == "passed":
                continue
            target = (
                initial_failure_codes
                if check["phase"] == "initial"
                else final_failure_codes
            )
            target[check["code"]] = target.get(check["code"], 0) + 1

    case_summaries = []
    for case_id in dict.fromkeys(value["case_id"] for value in observations.values()):
        attempts = [
            value for value in observations.values() if value["case_id"] == case_id
        ]
        selected = [
            value for value in attempts if value["execution"]["state"] == "completed"
        ]
        case_outcomes = {name: 0 for name in outcomes}
        for selected_value in selected:
            case_outcomes[selected_value["execution"]["terminal_outcome"]] += 1
        case_summaries.append(
            {
                "case_id": case_id,
                "planned_repetitions": 1,
                "completed_repetitions": len(selected),
                "all_planned_completed": len(selected) == 1,
                "outcomes": case_outcomes,
            }
        )

    def completed_measurements(name: str) -> list[float]:
        return [
            value["telemetry"][name]["value"]
            for value in completed
            if value["telemetry"][name]["applicability"] == "value"
        ]

    aggregate = _aggregate_telemetry(
        [value["telemetry"] for value in observations.values()]
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
            "denominator": len(structural_findings),
            "value": structurally_valid / len(structural_findings)
            if structural_findings
            else None,
        },
        "reference_validity": {
            "numerator": references_valid,
            "denominator": len(reference_findings),
            "value": references_valid / len(reference_findings)
            if reference_findings
            else None,
        },
        "explanation_coverage": {
            "numerator": explanation_numerator,
            "denominator": explanation_denominator,
            "value": explanation_numerator / explanation_denominator
            if explanation_denominator
            else None,
        },
        "initial_failure_codes": initial_failure_codes,
        "final_failure_codes": final_failure_codes,
        "latency": {
            "revision_s": _percentiles(completed_measurements("revision_s")),
            "observed_wall_s": _percentiles(completed_measurements("observed_wall_s")),
            "checkpoint_persistence_s": _percentiles(
                completed_measurements("checkpoint_persistence_s")
            ),
        },
        "cases": case_summaries,
        "semantic_success": {
            "applicability": "not_applicable",
            "definition": None,
            "rate": None,
        },
        "totals": {
            "completed_repetitions": len(completed),
            "incomplete_attempts": len(observations) - len(completed),
            "logical_calls": aggregate["logical_calls"],
            "reasks": aggregate["reasks"],
            "http_attempts": total_attempts,
            "http_429_responses": aggregate["http_429_responses"],
            "http_429_retries": aggregate["http_429_retries"],
            "provider_round_trip_s": aggregate["provider_round_trip_s"],
            "revision_s": aggregate["revision_s"],
            "observed_wall_s": aggregate["observed_wall_s"],
            "checkpoint_persistence_s": aggregate["checkpoint_persistence_s"],
            "non_http_remainder_s": aggregate["non_http_remainder_s"],
            "tokens": aggregate["tokens"],
            "cost_usd": aggregate["cost_usd"],
        },
    }
    validate_artifact(value)
    return value


def _write(path: Path, value: dict) -> None:
    """Write canonical UTF-8 JSON so committed assets remain deterministic."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
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
