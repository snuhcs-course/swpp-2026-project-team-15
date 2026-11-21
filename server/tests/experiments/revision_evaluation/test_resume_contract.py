# AI-assisted with Codex, 2026-11-22; reviewed by Soohyun An
"""Audit every durable boundary of mock interrupted/resumed runs against frozen v1."""

import json

import httpx
import pytest
from experiments.revision_evaluation import runner
from experiments.revision_evaluation.contract import (
    OBSERVATION_SCHEMA,
    fixture_root,
    schema_document,
    validate_artifact,
    validate_fixture_bundle,
)

from tests.experiments.revision_evaluation.test_resume import files, interrupted_run
from tests.experiments.revision_evaluation.test_runner import answer, artifacts
from tests.experiments.revision_evaluation.test_runner import no_network as no_network


def assert_observation_shape(value, fixture):
    """Compare public envelopes, not recipe/prompt content or variable-size evidence."""
    assert value.keys() == fixture.keys()
    for section in ("input", "execution", "deterministic_evaluation", "telemetry"):
        assert value[section].keys() == fixture[section].keys()
    for call in value["model_calls"]:
        reference = fixture["model_calls"][0]
        assert call.keys() == reference.keys()
        assert call["request"].keys() == reference["request"].keys()
        assert call["parsing"].keys() == reference["parsing"].keys()
        for attempt in call["http_attempts"]:
            assert attempt.keys() == reference["http_attempts"][0].keys()
            assert attempt["cost_usd"].keys() == reference["http_attempts"][0]["cost_usd"].keys()


@pytest.mark.parametrize("boundary", ["request_prepared", "during_send", "response_received"])
def test_all_saved_checkpoints_and_resumed_outputs_match_frozen_contract(
    tmp_path, monkeypatch, boundary
):
    """Preserve uncertain delivery and old bytes while validating every actual write."""
    root = fixture_root()
    committed = json.loads((root.parent.parent / "schema.json").read_text(encoding="utf-8"))
    # Validation uses the strict models that generated the committed JSON Schema;
    # equality makes drift explicit without adding a JSON Schema dependency.
    assert committed == schema_document()
    _, fixtures, _ = validate_fixture_bundle()
    reference = next(
        item.model_dump(by_alias=True)
        for item in fixtures
        if item.case_id == "resumed" and item.execution_attempt == 2
    )
    publications = []
    original_write = runner._EvaluatedStore._write

    def record(self, relative, value):
        original_write(self, relative, value)
        raw = json.loads((self.root / relative).read_text(encoding="utf-8"))
        validate_artifact(raw)
        if raw["artifact_schema"] == OBSERVATION_SCHEMA:
            assert_observation_shape(raw, reference)
        publications.append(raw)

    monkeypatch.setattr(runner._EvaluatedStore, "_write", record)
    plan, seed, kwargs, sends = interrupted_run(tmp_path, monkeypatch, boundary)
    run_root = tmp_path / seed.run_id
    before = files(run_root)
    checkpoint = json.loads(before["observations/runner-case__r03/attempt-001.json"])
    attempt = checkpoint["model_calls"][0]["http_attempts"][0]
    received = boundary == "response_received"
    assert checkpoint["execution"]["terminal_outcome"] is None
    assert attempt["delivery"] == ("confirmed" if received else "unknown")
    assert attempt["state"] == ("response_received" if received else "request_prepared")
    assert attempt["usage"] == (
        {"input_tokens": 10, "output_tokens": 20, "reasoning_tokens": None, "cached_tokens": None}
        if received
        else None
    )
    assert attempt["cost_usd"]["value"] == (0.01 if received else None)
    assert len(sends) == (2 if boundary == "request_prepared" else 3)
    resumed_sends = []
    runner.run_resume(
        run_root,
        plan,
        seed.identities,
        seed.code_identity,
        transport_factory=lambda: httpx.MockTransport(
            lambda request: resumed_sends.append(request) or answer()
        ),
        **kwargs,
    )
    metadata, summary, observations = artifacts(tmp_path)
    assert len(resumed_sends) == 1 and len(observations) == 4
    assert summary.complete and [unit.selected_completed_attempt for unit in metadata.plan] == [
        1,
        1,
        2,
    ]
    assert metadata.http_attempt_budget.consumed == summary.totals.http_attempts == 4
    assert metadata.http_attempt_budget.maximum == 20
    assert summary.totals.incomplete_attempts == 1
    assert summary.totals.cost_usd.confirmed_subtotal == pytest.approx(0.04 if received else 0.03)
    assert summary.totals.cost_usd.value == (pytest.approx(0.04) if received else None)
    assert summary.totals.tokens.input_tokens.value == (40 if received else None)
    assert summary.totals.tokens.input_tokens.confirmed_subtotal == (40 if received else 30)
    after = files(run_root)
    assert all(
        after[ref] == content for ref, content in before.items() if ref.startswith("observations/")
    )
    stages = {
        item["execution"]["checkpoint_stage"]
        for item in publications
        if item["artifact_schema"] == OBSERVATION_SCHEMA
    }
    assert {
        "attempt_created",
        "request_prepared",
        "response_received",
        "json_parsed",
        "check_completed",
        "terminal",
    } <= stages
