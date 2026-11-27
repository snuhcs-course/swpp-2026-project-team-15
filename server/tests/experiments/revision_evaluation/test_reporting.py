# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Verify Markdown is a deterministic, non-mutating projection of summary JSON."""

import hashlib
import json

import pytest
from experiments.revision_evaluation.contract import RunSummary, fixture_root
from experiments.revision_evaluation.reporting import render_summary


def fixture_summary():
    """Load only authoritative summary JSON, not metadata or observation artifacts."""
    return RunSummary.model_validate_json(
        (fixture_root() / "summary.json").read_text(encoding="utf-8")
    )


def test_fixed_json_renders_deterministically_without_mutation():
    summary = fixture_summary()
    before = summary.model_dump()
    report = render_summary(summary)
    reordered = json.loads(
        json.dumps(before), object_pairs_hook=lambda pairs: dict(reversed(pairs))
    )
    assert render_summary(RunSummary.model_validate(reordered)) == report
    assert render_summary(summary) == report
    assert summary.model_dump() == before
    assert hashlib.sha256(report.encode("utf-8")).hexdigest() == (
        "80448f5e390e64953ebd518e1ee032fd837090e02fcf3a12089853e8f2aca3f9"
    )
    assert report.endswith("\n")


def test_report_keeps_counts_provenance_subtotals_and_scope_visible():
    report = render_summary(fixture_summary())
    assert "6/7 (0.857142857143)" in report
    assert "2/3 (0.666666666667)" in report
    assert "| revision\\_s | 8 | exclude | 0.8 | 0.8 |" in report
    assert "| input\\_tokens | unavailable | null | 70 |" in report
    assert "provenance: missing; total: null; confirmed subtotal: 0.0007" in report
    assert "Semantic success: not_applicable" in report
    for phrase in (
        "unknown in-flight",
        "not pure application processing",
        "checkpoint persistence",
        "not complete totals",
        "No-call",
        "no Judge usage",
    ):
        assert phrase in report
    for reference in fixture_summary().observation_refs:
        assert reference.replace("_", "\\_") in report


def test_renderer_uses_stored_summary_values_without_reaggregation():
    summary = fixture_summary()
    summary.latency.revision_s.p50_s.value = 123.25
    summary.json_parse_success.numerator = 1
    summary.json_parse_success.denominator = 4
    summary.json_parse_success.value = 0.25
    report = render_summary(summary)
    assert "| revision\\_s | 8 | exclude | 123.25 | 0.8 |" in report
    assert "1/4 (0.25)" in report


@pytest.mark.parametrize("state", ["unavailable", "not_applicable", "value"])
def test_zero_missing_and_na_remain_distinct(state):
    summary = fixture_summary()
    latency = summary.latency.revision_s
    latency.sample_count = 1 if state == "value" else 0
    for value in (latency.p50_s, latency.p95_s):
        value.applicability = state
        value.value = 0 if state == "value" else None
    report = render_summary(summary)
    displayed = "0" if state == "value" else state
    assert (
        f"| revision\\_s | {latency.sample_count} | exclude | {displayed} | {displayed} |" in report
    )


def test_estimated_prices_and_named_semantic_metric_are_projected():
    summary = fixture_summary()
    cost = summary.totals.cost_usd
    cost.applicability = "value"
    cost.value = cost.confirmed_subtotal = 1e-15
    cost.provenance = "estimated"
    cost.price_inputs = {"output_per_million_usd": 0.4, "input_per_million_usd": 0.1}
    summary.semantic_success = summary.semantic_success.model_validate(
        {
            "applicability": "value",
            "definition": "reviewed-test/v1",
            "rate": {"numerator": 1, "denominator": 2, "value": 0.5},
        }
    )
    report = render_summary(summary)
    assert "provenance: estimated; total: 1e-15; confirmed subtotal: 1e-15" in report
    assert "Price inputs:" in report
    assert "reviewed-test/v1; rate: 1/2 (0.5)" in report


def test_untrusted_labels_cannot_inject_html_rows_or_links():
    summary = fixture_summary()
    summary.cases[0].case_id = "bad|case\n<script>[link](https://example.test)"
    summary.run_id = "*heading*"
    report = render_summary(summary)
    assert "bad\\|case<br>&lt;script&gt;\\[link\\]" in report
    assert "Run: \\*heading\\*" in report
    assert "<script>" not in report


def test_renderer_rejects_unsupported_schema():
    summary = fixture_summary()
    summary.artifact_schema = "revision-evaluation-summary/v2"
    with pytest.raises(ValueError):
        render_summary(summary)
