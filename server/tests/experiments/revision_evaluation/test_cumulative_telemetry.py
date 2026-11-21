# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Verify both publication boundaries reject stale totals without replacing evidence."""

from copy import deepcopy

import pytest
from experiments.revision_evaluation.contract import Observation, RunMetadata
from experiments.revision_evaluation.generate_contract import (
    STAMP,
    fixture_metadata,
    fixture_observations,
)
from experiments.revision_evaluation.persistence import RunStore
from experiments.revision_evaluation.summary import summarize_run
from experiments.revision_evaluation.telemetry import (
    repetition_telemetry,
    validate_cumulative_telemetry,
)


@pytest.fixture
def publication(tmp_path, request):
    """Use saved files for storage checks and the same reference index for summaries."""
    raw = fixture_observations()
    metadata = RunMetadata.model_validate(fixture_metadata(raw))
    observations = {
        f"observations/{ref}": Observation.model_validate(value) for ref, value in raw.items()
    }
    before = deepcopy(observations)
    if request.param == "storage":
        store = RunStore(tmp_path, metadata.run_id)
        for observation in observations.values():
            store.write_observation(observation)
        store.write_metadata(metadata)
        saved = {path: path.read_bytes() for path in store.root.rglob("*.json")}

        def publish():
            store.write_metadata(metadata)

        def unchanged():
            assert {path: path.read_bytes() for path in store.root.rglob("*.json")} == saved
    else:

        def publish():
            return summarize_run(metadata, observations, generated_at=STAMP)

        def unchanged():
            assert observations == before

    return metadata, observations, publish, unchanged


@pytest.mark.parametrize("publication", ["storage", "summary"], indirect=True)
@pytest.mark.parametrize(
    "change",
    [
        "count",
        "tokens",
        "token_subtotal",
        "cost_subtotal",
        "cost_value",
        "duration",
        "applicability",
        "provenance",
        "missing",
        "omit_interrupted",
        "empty_has_total",
    ],
)
def test_stale_cumulative_totals_are_rejected_without_writes(publication, change):
    metadata, observations, publish, unchanged = publication
    unit = metadata.plan[-1]  # Interrupted attempt plus completed resume.
    total = unit.cumulative_telemetry
    if change == "count":
        total.http_attempts += 1
    elif change == "tokens":
        total.tokens.input_tokens.applicability = "value"
        total.tokens.input_tokens.value = total.tokens.input_tokens.confirmed_subtotal
    elif change == "token_subtotal":
        total.tokens.input_tokens.confirmed_subtotal += 1
    elif change == "cost_subtotal":
        total.cost_usd.confirmed_subtotal += 0.01
    elif change == "cost_value":
        total = metadata.plan[0].cumulative_telemetry
        total.cost_usd = total.cost_usd.model_validate(
            {
                "applicability": "value",
                "value": 1,
                "confirmed_subtotal": 1,
                "provenance": "measured",
                "price_inputs": None,
            }
        )
    elif change == "duration":
        total.checkpoint_persistence_s.value += 0.01
    elif change == "applicability":
        total.provider_round_trip_s.applicability = "not_applicable"
        total.provider_round_trip_s.value = None
    elif change == "provenance":
        total = metadata.plan[2].cumulative_telemetry  # No-call refused path.
        total.cost_usd.applicability = "unavailable"
        total.cost_usd.provenance = "missing"
    elif change == "missing":
        unit.cumulative_telemetry = None
    elif change == "omit_interrupted":
        unit.cumulative_telemetry = repetition_telemetry([observations[unit.observation_refs[-1]]])
    else:
        pending = unit.model_copy(deep=True)
        pending.repetition = 4
        pending.state = "not_started"
        pending.selected_completed_attempt = None
        pending.observation_refs = []
        metadata.plan.append(pending)
    # Ensure the failure is cross-artifact consistency, not malformed field shapes.
    RunMetadata.model_validate(metadata.model_dump())
    before = metadata.model_dump()
    with pytest.raises(ValueError, match="cumulative telemetry"):
        publish()
    assert metadata.model_dump() == before
    unchanged()


@pytest.mark.parametrize("publication", ["storage", "summary"], indirect=True)
def test_float_roundoff_is_accepted_without_repairing_inputs(publication):
    metadata, _, publish, _ = publication
    total = metadata.plan[-1].cumulative_telemetry
    total.checkpoint_persistence_s.value += 1e-15
    total.cost_usd.confirmed_subtotal += 1e-15
    before = metadata.model_dump()
    publish()
    assert metadata.model_dump() == before


def test_estimate_price_inputs_are_exact_configuration_not_rounded_totals():
    raw = fixture_observations()
    metadata = RunMetadata.model_validate(fixture_metadata(raw))
    unit = metadata.plan[0]
    observation = Observation.model_validate(
        raw[unit.observation_refs[0].removeprefix("observations/")]
    )
    observation.telemetry.cost_usd = observation.telemetry.cost_usd.model_validate(
        {
            "applicability": "value",
            "value": 0.01,
            "confirmed_subtotal": 0.01,
            "provenance": "estimated",
            "price_inputs": {"input_per_million_usd": 1.0},
        }
    )
    unit.cumulative_telemetry = repetition_telemetry([observation])
    validate_cumulative_telemetry(unit, [observation])
    unit.cumulative_telemetry.cost_usd.price_inputs["input_per_million_usd"] += 1e-15
    with pytest.raises(ValueError, match="cumulative telemetry"):
        validate_cumulative_telemetry(unit, [observation])
