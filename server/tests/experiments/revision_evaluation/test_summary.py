# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Offline summary tests for selection, independent denominators and partial plans."""

from copy import deepcopy

import pytest
from experiments.revision_evaluation.contract import Observation, RunMetadata
from experiments.revision_evaluation.generate_contract import (
    STAMP,
    fixture_metadata,
    fixture_observations,
    fixture_summary,
)
from experiments.revision_evaluation.summary import summarize_run
from experiments.revision_evaluation.telemetry import repetition_telemetry


def bundle():
    """Load detached fixture objects without depending on Runner orchestration."""
    raw = fixture_observations()
    return (
        RunMetadata.model_validate(fixture_metadata(raw)),
        {f"observations/{ref}": Observation.model_validate(value) for ref, value in raw.items()},
    )


def refresh_totals(metadata, observations):
    """Keep synthetic metadata consistent when a test changes retained telemetry."""
    for unit in metadata.plan:
        attempts = [observations[ref] for ref in unit.observation_refs]
        unit.cumulative_telemetry = repetition_telemetry(attempts) if attempts else None


def test_summary_matches_independent_contract_fixture_without_mutation():
    metadata, observations = bundle()
    before = deepcopy((metadata, observations))
    result = summarize_run(metadata, observations, generated_at=STAMP)
    assert result.model_dump() == fixture_summary(fixture_observations())
    assert (metadata, observations) == before
    assert result.totals.incomplete_attempts == 1
    assert result.totals.http_attempts == metadata.http_attempt_budget.consumed
    assert result.totals.cost_usd.value is None
    assert result.totals.cost_usd.confirmed_subtotal > 0
    assert result.semantic_success.applicability == "not_applicable"


def test_partial_plan_counts_missing_repetitions_not_extra_attempts():
    metadata, observations = bundle()
    metadata.state = "interrupted"
    unit = metadata.plan[-1]
    observations.pop(unit.observation_refs.pop())
    unit.state = "incomplete"
    unit.selected_completed_attempt = None
    # Add a genuinely not-started repetition, not a fabricated observation.
    pending = unit.model_copy(deep=True)
    pending.repetition = 4
    pending.state = "not_started"
    pending.observation_refs = []
    pending.cumulative_telemetry = None
    metadata.plan.append(pending)
    metadata.http_attempt_budget.consumed -= 1
    metadata.http_attempt_budget.remaining += 1
    refresh_totals(metadata, observations)
    result = summarize_run(metadata, observations, generated_at=STAMP)
    case = result.cases[-1]
    assert not result.complete
    assert (case.planned_repetitions, case.completed_repetitions) == (2, 0)
    assert not case.all_planned_completed
    assert result.totals.incomplete_attempts == 1
    assert result.totals.completed_repetitions == 7
    assert result.totals.http_attempts == metadata.http_attempt_budget.consumed


def test_denominators_remain_independent_and_keep_interrupted_findings():
    metadata, observations = bundle()
    interrupted = next(
        item for item in observations.values() if item.execution.state == "interrupted"
    )
    interrupted.deterministic_evaluation.answers = [
        next(item for item in observations.values() if item.deterministic_evaluation.answers)
        .deterministic_evaluation.answers[0]
        .model_copy(deep=True)
    ]
    finding = interrupted.deterministic_evaluation.answers[0]
    finding.structure_valid = False
    finding.reference_valid = None
    result = summarize_run(metadata, observations, generated_at=STAMP)
    assert result.structural_validity.denominator == result.reference_validity.denominator + 1
    assert result.json_parse_success.denominator > result.json_parse_success.numerator
    assert result.structural_validity.denominator == result.json_parse_success.numerator + 1


def test_percentiles_interpolate_available_completed_samples_only():
    metadata, observations = bundle()
    completed = [item for item in observations.values() if item.execution.state == "completed"]
    for item in completed:
        item.telemetry.revision_s.applicability = "unavailable"
        item.telemetry.revision_s.value = None
    for item, duration in zip(completed, (0, 10), strict=False):
        item.telemetry.revision_s.applicability = "value"
        item.telemetry.revision_s.value = duration
    interrupted = next(
        item for item in observations.values() if item.execution.state == "interrupted"
    )
    interrupted.telemetry.revision_s.applicability = "value"
    interrupted.telemetry.revision_s.value = 1000
    refresh_totals(metadata, observations)
    latency = summarize_run(metadata, observations, generated_at=STAMP).latency.revision_s
    assert latency.sample_count == 2
    assert latency.p50_s.value == 5
    assert latency.p95_s.value == 9.5
    assert latency.incomplete_attempt_policy == "exclude"


def test_empty_latency_and_rates_are_not_applicable():
    metadata, observations = bundle()
    unit = metadata.plan[0]  # A genuine no-call, completed observation.
    metadata.plan = [unit]
    observations = {ref: observations[ref] for ref in unit.observation_refs}
    metadata.http_attempt_budget.consumed = 0
    metadata.http_attempt_budget.remaining = metadata.http_attempt_budget.maximum
    observation = next(iter(observations.values()))
    observation.telemetry.revision_s.applicability = "unavailable"
    observation.telemetry.revision_s.value = None
    refresh_totals(metadata, observations)
    result = summarize_run(metadata, observations, generated_at=STAMP)
    assert result.json_parse_success.value is None
    assert result.structural_validity.denominator == result.reference_validity.denominator == 0
    assert result.explanation_coverage.value is None
    assert result.latency.revision_s.sample_count == 0
    assert result.latency.revision_s.p50_s.applicability == "not_applicable"
    assert result.latency.observed_wall_s.sample_count == 1


@pytest.mark.parametrize(
    "corruption",
    [
        "missing",
        "extra",
        "duplicate_ref",
        "duplicate_unit",
        "duplicate_attempt",
        "wrong_run",
        "wrong_case",
        "wrong_selection",
        "wrong_state",
        "budget",
        "incomplete_run",
    ],
)
def test_reject_inconsistent_plan_and_observation_index(corruption):
    metadata, observations = bundle()
    first_ref = metadata.plan[0].observation_refs[0]
    first = observations[first_ref]
    if corruption == "missing":
        observations.pop(first_ref)
    elif corruption == "extra":
        observations["unplanned.json"] = first
    elif corruption == "duplicate_ref":
        metadata.plan[0].observation_refs.append(first_ref)
    elif corruption == "duplicate_unit":
        metadata.plan.append(metadata.plan[0].model_copy(deep=True))
    elif corruption == "duplicate_attempt":
        ref = metadata.plan[-1].observation_refs[-1]
        observations[ref].execution_attempt = 1
    elif corruption == "wrong_run":
        first.run_id = "different"
    elif corruption == "wrong_case":
        first.case_id = "different"
    elif corruption == "wrong_selection":
        metadata.plan[-1].selected_completed_attempt = 1
    elif corruption == "wrong_state":
        metadata.plan[0].state = "not_started"
    elif corruption == "budget":
        metadata.http_attempt_budget.consumed -= 1
    else:
        unit = metadata.plan[-1]
        observations.pop(unit.observation_refs.pop())
        unit.state = "incomplete"
        unit.selected_completed_attempt = None
    with pytest.raises(ValueError):
        summarize_run(metadata, observations, generated_at=STAMP)
