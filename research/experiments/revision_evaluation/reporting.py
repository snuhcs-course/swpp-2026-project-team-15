# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Deterministic Markdown projection of authoritative v1 summary JSON data."""

import html
import json

from .contract import OptionalNumber, Rate, RunSummary


def _text(value: str) -> str:
    """Escape artifact labels so they cannot inject Markdown rows, links or HTML."""
    value = html.escape(value, quote=True).replace("\r\n", "\n").replace("\r", "\n")
    for character in ("\\", "|", "`", "*", "_", "[", "]", "#"):
        value = value.replace(character, "\\" + character)
    return value.replace("\n", "<br>")


def _number(value: float) -> str:
    """Format numeric values without locale, including small nonzero costs."""
    return str(value) if isinstance(value, int) else format(value, ".12g")


def _optional(value: OptionalNumber) -> str:
    """Keep measured zero, unavailable and N/A visibly distinct."""
    return _number(value.value) if value.applicability == "value" else value.applicability


def _rate(value: Rate) -> str:
    """Display stored counts and the stored rate without recomputing the metric."""
    rate = "not_applicable" if value.value is None else _number(value.value)
    return f"{value.numerator}/{value.denominator} ({rate})"


def render_summary(summary: RunSummary) -> str:
    """Return Markdown using only the supplied summary; perform no I/O or aggregation.

    Revalidation rejects malformed/unsupported summaries. No metadata, observation,
    clock, model, environment or current configuration participates in rendering.
    List order is retained; dictionary entries use sorted keys for regeneration.
    """
    summary = RunSummary.model_validate(summary.model_dump())
    lines = [
        "# Revision evaluation summary",
        "",
        "Source: summary.json (authoritative); this report is a presentation only.",
        "",
        f"Run: {_text(summary.run_id)}  ",
        f"Schema: {_text(summary.artifact_schema)}  ",
        f"Observation schema: {_text(summary.observation_schema)}  ",
        f"Generated: {_text(summary.generated_at)}  ",
        f"All planned repetitions completed: {str(summary.complete).lower()}",
        "",
        "## Outcomes",
        "",
        "| Outcome | Completed repetitions |",
        "| --- | ---: |",
    ]
    lines.extend(
        f"| {_text(name)} | {count} |"
        for name, count in sorted(summary.outcomes.model_dump().items())
    )
    lines.extend(
        [
            "",
            "## Deterministic metrics",
            "",
            "| Metric | Numerator/denominator (rate) |",
            "| --- | --- |",
        ]
    )
    for name in (
        "json_parse_success",
        "structural_validity",
        "reference_validity",
        "explanation_coverage",
    ):
        lines.append(f"| {_text(name)} | {_rate(getattr(summary, name))} |")
    semantic = summary.semantic_success
    lines.extend(["", f"Semantic success: {semantic.applicability}."])
    if semantic.definition is not None:
        lines.append(f"Definition: {_text(semantic.definition)}; rate: {_rate(semantic.rate)}.")
    lines.extend(
        [
            "",
            "## Check failures",
            "",
            "| Phase | Code | Count |",
            "| --- | --- | ---: |",
        ]
    )
    for phase, counts in (
        ("initial", summary.initial_failure_codes),
        ("final", summary.final_failure_codes),
    ):
        if not counts:
            lines.append(f"| {phase} | none | 0 |")
        lines.extend(
            f"| {phase} | {_text(code)} | {count} |" for code, count in sorted(counts.items())
        )
    lines.extend(
        [
            "",
            "## Latency (seconds)",
            "",
            "| Metric | Samples | Incomplete attempt policy | p50 | p95 |",
            "| --- | ---: | --- | ---: | ---: |",
        ]
    )
    for name, value in summary.latency:
        lines.append(
            f"| {_text(name)} | {value.sample_count} | {_text(value.incomplete_attempt_policy)} | "
            f"{_optional(value.p50_s)} | {_optional(value.p95_s)} |"
        )
    lines.extend(
        [
            "",
            "## Per-case repetition consistency",
            "",
            "| Case | Planned | Completed | All completed | Outcome distribution |",
            "| --- | ---: | ---: | --- | --- |",
        ]
    )
    for case in summary.cases:
        outcomes = ", ".join(
            f"{_text(name)}={count}" for name, count in sorted(case.outcomes.model_dump().items())
        )
        lines.append(
            f"| {_text(case.case_id)} | {case.planned_repetitions} | "
            f"{case.completed_repetitions} | {str(case.all_planned_completed).lower()} | "
            f"{outcomes} |"
        )
    lines.extend(
        [
            "",
            "## Cumulative totals (all execution attempts)",
            "",
            "| Metric | Value |",
            "| --- | --- |",
        ]
    )
    for name, value in summary.totals:
        if isinstance(value, int):
            lines.append(f"| {_text(name)} | {value} |")
        elif isinstance(value, OptionalNumber):
            lines.append(f"| {_text(name)} | {_optional(value)} |")
    lines.extend(
        [
            "",
            "### Tokens",
            "",
            "| Category | Applicability | Total | Confirmed subtotal |",
            "| --- | --- | ---: | ---: |",
        ]
    )
    for name, value in summary.totals.tokens:
        total = "null" if value.value is None else _number(value.value)
        lines.append(
            f"| {_text(name)} | {value.applicability} | {total} | {value.confirmed_subtotal} |"
        )
    cost = summary.totals.cost_usd
    total = "null" if cost.value is None else _number(cost.value)
    lines.extend(
        [
            "",
            "### Cost (USD)",
            "",
            f"Applicability: {cost.applicability}; provenance: {cost.provenance}; "
            f"total: {total}; confirmed subtotal: {_number(cost.confirmed_subtotal)}.",
        ]
    )
    if cost.price_inputs is not None:
        lines.append(f"Price inputs: {_text(json.dumps(cost.price_inputs, sort_keys=True))}.")
    lines.extend(
        [
            "",
            "## Metric scope and limitations",
            "",
            "- Outcomes use selected completed attempts. Incomplete attempts are not extra "
            "repetitions; all retained attempts contribute cumulative calls, tokens and costs.",
            "- JSON parsing uses returned response texts; structure uses parsed answers. "
            "Reference validity has its own recorded denominator. No-call and no-response "
            "paths do not count as parse failures.",
            "- Explanation coverage counts explained deleted source-ingredient rows over "
            "detected deleted rows in terminal revising answers. A zero denominator is "
            "not_applicable, not success.",
            "- Latency sample counts and incomplete-attempt policies are explicit above. "
            "Percentiles are stored values, not recalculated by this report.",
            "- Revision latency excludes measured checkpoint persistence; observed wall time "
            "includes it. Checkpoint overhead covers the measured Revision-call window, "
            "not all run setup/final publication I/O.",
            "- Non-HTTP remainder may include retry waits and unobserved work; "
            "it is not pure application processing time.",
            "- A persisted request_prepared identity consumes HTTP budget even when delivery "
            "is unknown. A request may have reached the provider without durable response/usage; "
            "unknown in-flight tokens and cost are not zero or assumed free.",
            "- unavailable means missing measurement; not_applicable means the metric does "
            "not apply. Confirmed subtotals are not complete totals. Estimated costs depend "
            "on retained price inputs and are not provider-measured costs.",
            "- Operational completion, JSON validity and deterministic checks do not establish "
            "semantic recipe quality. Semantic success is not applicable without a named "
            "versioned definition; no Judge usage is included.",
            "",
            "## Observation references",
            "",
        ]
    )
    lines.extend(f"- {_text(reference)}" for reference in summary.observation_refs)
    return "\n".join(lines) + "\n"
