# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
# Cumulative consistency validation added with Codex, 2026-11-21; human review pending.
"""Pure v1 summary aggregation over an explicit plan and retained observations."""

import math
from collections.abc import Mapping, Sequence

from .contract import (
    OBSERVATION_SCHEMA,
    SUMMARY_SCHEMA,
    CaseSummary,
    Observation,
    OptionalNumber,
    OutcomeCounts,
    Percentiles,
    Rate,
    RunMetadata,
    RunSummary,
    validate_plan_unit_observations,
)
from .telemetry import aggregate_telemetry, validate_cumulative_telemetry


def _rate(numerator: int, denominator: int) -> Rate:
    """Retain counts and leave an empty denominator explicitly inapplicable."""
    return Rate(
        numerator=numerator,
        denominator=denominator,
        value=numerator / denominator if denominator else None,
    )


def _outcomes(observations: Sequence[Observation]) -> OutcomeCounts:
    """Count only selected completed observations, never incomplete executions."""
    counts = dict.fromkeys(OutcomeCounts.model_fields, 0)
    for observation in observations:
        counts[observation.execution.terminal_outcome] += 1
    return OutcomeCounts(**counts)


def _percentiles(values: list[float]) -> Percentiles:
    """Use the contract fixture's linear interpolation, excluding incomplete attempts."""
    ordered = sorted(values)

    def percentile(quantile: float) -> OptionalNumber:
        if not ordered:
            return OptionalNumber(applicability="not_applicable", value=None)
        position = (len(ordered) - 1) * quantile
        lower, upper = math.floor(position), math.ceil(position)
        value = ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)
        return OptionalNumber(applicability="value", value=value)

    return Percentiles(
        sample_count=len(ordered),
        incomplete_attempt_policy="exclude",
        p50_s=percentile(0.5),
        p95_s=percentile(0.95),
    )


def summarize_run(
    metadata: RunMetadata,
    observations: Mapping[str, Observation],
    *,
    generated_at: str,
) -> RunSummary:
    """Summarize stored evidence without rescoring it, reading files or mutating inputs.

    Mapping keys are the metadata's run-relative artifact references. Reject an
    inconsistent index rather than silently dropping unplanned evidence or counting
    one execution twice. Metadata selects final outcomes; every retained attempt
    contributes response findings, check failures and cumulative usage. Semantic
    quality is deliberately not inferred from operational completion.
    """
    refs = [ref for unit in metadata.plan for ref in unit.observation_refs]
    units = [(unit.case_id, unit.repetition) for unit in metadata.plan]
    if len(set(units)) != len(units) or len(set(refs)) != len(refs):
        raise ValueError("plan units and observation references must be unique")
    if set(refs) != set(observations):
        raise ValueError("observations must match the complete planned reference set")
    retained = [observations[ref] for ref in refs]
    identities = [(item.case_id, item.repetition, item.execution_attempt) for item in retained]
    if len(set(identities)) != len(identities):
        raise ValueError("execution attempt identities must be unique")
    if any(item.run_id != metadata.run_id for item in retained):
        raise ValueError("observations belong to a different run")

    selected = []
    for unit in metadata.plan:
        attempts = [observations[ref] for ref in unit.observation_refs]
        validate_plan_unit_observations(unit, attempts)
        completed = [item for item in attempts if item.execution.state == "completed"]
        expected = "completed" if completed else "incomplete" if attempts else "not_started"
        if unit.state != expected or len(completed) > 1:
            raise ValueError("plan state must select exactly one completed result when available")
        validate_cumulative_telemetry(unit, attempts)
        selected.extend(completed)
    complete = bool(metadata.plan) and len(selected) == len(metadata.plan)
    if metadata.state == "completed" and not complete:
        raise ValueError("completed run has missing planned results")
    totals = aggregate_telemetry([item.telemetry for item in retained])
    if totals.http_attempts != metadata.http_attempt_budget.consumed:
        raise ValueError("HTTP budget must count every retained attempt")

    calls = [call for item in retained for call in item.model_calls]
    returned = [call for call in calls if call.parsing.attempted]
    findings = [finding for item in retained for finding in item.deterministic_evaluation.answers]

    def validity(field: str) -> Rate:
        entries = [getattr(finding, field) for finding in findings]
        return _rate(
            sum(entry is True for entry in entries),
            sum(entry is not None for entry in entries),
        )

    failures = {"initial": {}, "final": {}}
    for item in retained:
        for check in item.checks:
            if check.result == "violation" and check.code is not None:
                counts = failures[check.phase]
                counts[check.code] = counts.get(check.code, 0) + 1
    coverage = [item.deterministic_evaluation.deleted_ingredient_explanation for item in retained]
    cases = []
    for case_id in dict.fromkeys(unit.case_id for unit in metadata.plan):
        planned = sum(unit.case_id == case_id for unit in metadata.plan)
        observed = [item for item in selected if item.case_id == case_id]
        cases.append(
            CaseSummary(
                case_id=case_id,
                planned_repetitions=planned,
                completed_repetitions=len(observed),
                all_planned_completed=len(observed) == planned,
                outcomes=_outcomes(observed),
            )
        )

    return RunSummary(
        artifact_schema=SUMMARY_SCHEMA,
        observation_schema=OBSERVATION_SCHEMA,
        run_id=metadata.run_id,
        complete=complete,
        generated_at=generated_at,
        observation_refs=refs,
        outcomes=_outcomes(selected),
        json_parse_success=_rate(
            sum(call.parsing.succeeded is True for call in returned), len(returned)
        ),
        structural_validity=validity("structure_valid"),
        reference_validity=validity("reference_valid"),
        explanation_coverage=_rate(
            sum(rate.numerator for rate in coverage),
            sum(rate.denominator for rate in coverage),
        ),
        initial_failure_codes=failures["initial"],
        final_failure_codes=failures["final"],
        latency={
            name: _percentiles(
                [
                    getattr(item.telemetry, name).value
                    for item in selected
                    if getattr(item.telemetry, name).applicability == "value"
                ]
            )
            for name in ("revision_s", "observed_wall_s", "checkpoint_persistence_s")
        },
        cases=cases,
        semantic_success={
            "applicability": "not_applicable",
            "definition": None,
            "rate": None,
        },
        totals={
            "completed_repetitions": len(selected),
            "incomplete_attempts": len(retained) - len(selected),
            **totals.model_dump(),
        },
    )
