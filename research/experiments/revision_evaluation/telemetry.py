# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Auditable attempt/repetition telemetry without inventing in-flight measurements."""

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass

from .contract import (
    Cost,
    ModelCall,
    Observation,
    OptionalNumber,
    Telemetry,
    TokenTotal,
    TokenTotals,
)

TIME_FIELDS = (
    "provider_round_trip_s",
    "revision_s",
    "observed_wall_s",
    "checkpoint_persistence_s",
    "non_http_remainder_s",
)
COUNT_FIELDS = (
    "logical_calls",
    "reasks",
    "http_attempts",
    "http_429_responses",
    "http_429_retries",
)


def _number(value=None, *, state="unavailable") -> OptionalNumber:
    """Represent a known number, an unknown measurement or an inapplicable metric."""
    return OptionalNumber(applicability="value" if value is not None else state, value=value)


@dataclass(frozen=True)
class TokenPrices:
    """Explicit per-million-token inputs; cached/reasoning discounts are not inferred."""

    input_per_million_usd: float
    output_per_million_usd: float

    def __post_init__(self):
        for value in asdict(self).values():
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError("token prices must be finite nonnegative numbers")


@dataclass(frozen=True)
class RevisionTiming:
    """Measured Revision-call window, excluding attempt creation/final publication I/O.

    Wall time encloses the actual revise() call, including its checkpoints. A
    snapshot during an incomplete call has no final wall/Revision latency. Its
    completed checkpoint overhead can still be recorded independently.
    """

    observed_wall_s: float | None = None
    checkpoint_persistence_s: float | None = None

    def __post_init__(self):
        for value in asdict(self).values():
            if value is not None and (not math.isfinite(value) or value < 0):
                raise ValueError("timing must be finite and nonnegative")
        if (
            self.observed_wall_s is not None
            and self.checkpoint_persistence_s is not None
            and self.checkpoint_persistence_s > self.observed_wall_s + 1e-9
        ):
            raise ValueError("checkpoint time cannot exceed its Revision wall window")


def _sum_numbers(values: Sequence[OptionalNumber]) -> OptionalNumber:
    """Ignore N/A but propagate unavailable durations rather than summing partial time."""
    applicable = [value for value in values if value.applicability != "not_applicable"]
    if not applicable:
        return _number(state="not_applicable")
    if any(value.applicability != "value" for value in applicable):
        return _number()
    return _number(math.fsum(value.value for value in applicable))


def _sum_tokens(entries: Sequence[TokenTotal]) -> TokenTotal:
    """Keep independently known token subtotals when another attempt is unknown."""
    applicable = [entry for entry in entries if entry.applicability != "not_applicable"]
    subtotal = sum(entry.confirmed_subtotal for entry in applicable)
    complete = bool(applicable) and all(entry.applicability == "value" for entry in applicable)
    return TokenTotal(
        applicability="value" if complete else "unavailable" if applicable else "not_applicable",
        value=subtotal if complete else None,
        confirmed_subtotal=subtotal,
    )


def _sum_costs(costs: Sequence[Cost]) -> Cost:
    """Preserve measured/estimated/missing provenance and every known subtotal."""
    applicable = [cost for cost in costs if cost.provenance != "not_applicable"]
    subtotal = math.fsum(cost.confirmed_subtotal for cost in applicable)
    complete = bool(applicable) and all(cost.applicability == "value" for cost in applicable)
    estimated = [cost for cost in applicable if cost.provenance == "estimated"]
    prices = estimated[0].price_inputs if estimated else None
    if any(cost.price_inputs != prices for cost in estimated):
        raise ValueError("cannot combine costs with different estimate price inputs")
    provenance = (
        "estimated"
        if complete and estimated
        else "measured"
        if complete
        else "missing"
        if applicable
        else "not_applicable"
    )
    return Cost(
        applicability="value" if complete else "unavailable" if applicable else "not_applicable",
        value=subtotal if complete else None,
        confirmed_subtotal=subtotal,
        provenance=provenance,
        price_inputs=prices if provenance == "estimated" else None,
    )


def attempt_telemetry(
    calls: Sequence[ModelCall],
    *,
    timing: RevisionTiming | None = None,
    prices: TokenPrices | None = None,
) -> Telemetry:
    """Compute one attempt from its complete retained trace, not only its last answer.

    A prepared request always consumes an HTTP identity but has unknown billing.
    Provider cost takes precedence; token pricing is used only when both input
    and output counts are known, never for an uncertain prepared request.
    """
    attempts = [attempt for call in calls for attempt in call.http_attempts]
    timing = timing or RevisionTiming()
    tokens = {}
    for name in TokenTotals.model_fields:
        entries = [getattr(attempt.usage, name) if attempt.usage else None for attempt in attempts]
        tokens[name] = _sum_tokens(
            [
                TokenTotal(
                    applicability="value" if value is not None else "unavailable",
                    value=value,
                    confirmed_subtotal=value if value is not None else 0,
                )
                for value in entries
            ]
        )
    costs = []
    for attempt in attempts:
        cost = attempt.cost_usd.model_copy(deep=True)
        usage = attempt.usage
        if (
            cost.provenance == "missing"
            and cost.confirmed_subtotal == 0
            and prices is not None
            and attempt.state == "response_received"
            and usage is not None
            and usage.input_tokens is not None
            and usage.output_tokens is not None
        ):
            estimate = (
                usage.input_tokens * prices.input_per_million_usd
                + usage.output_tokens * prices.output_per_million_usd
            ) / 1_000_000
            cost = Cost(
                applicability="value",
                value=estimate,
                confirmed_subtotal=estimate,
                provenance="estimated",
                price_inputs=asdict(prices),
            )
        costs.append(cost)
    provider = _sum_numbers([_number(attempt.provider_round_trip_s) for attempt in attempts])
    revision = None
    if timing.observed_wall_s is not None and timing.checkpoint_persistence_s is not None:
        revision = max(0, timing.observed_wall_s - timing.checkpoint_persistence_s)
    remainder = None
    if revision is not None and (not attempts or provider.applicability == "value"):
        # This includes retry waits and other unobserved work, not pure processing.
        difference = revision - (provider.value or 0)
        if difference < -1e-9:
            raise ValueError("provider duration exceeds measured Revision time")
        remainder = max(0, difference)
    return Telemetry(
        logical_calls=len(calls),
        reasks=sum(call.purpose == "reask" for call in calls),
        http_attempts=len(attempts),
        http_429_responses=sum(attempt.status_code == 429 for attempt in attempts),
        http_429_retries=sum(
            attempt.status_code == 429 for call in calls for attempt in call.http_attempts[:-1]
        ),
        provider_round_trip_s=provider,
        revision_s=_number(revision),
        observed_wall_s=_number(timing.observed_wall_s),
        checkpoint_persistence_s=_number(timing.checkpoint_persistence_s),
        non_http_remainder_s=_number(remainder),
        tokens=TokenTotals(**tokens),
        cost_usd=_sum_costs(costs),
    )


def aggregate_telemetry(values: Sequence[Telemetry]) -> Telemetry:
    """Combine all attempts, excluding only N/A values and never losing known subtotals."""
    return Telemetry(
        **{name: sum(getattr(value, name) for value in values) for name in COUNT_FIELDS},
        **{name: _sum_numbers([getattr(value, name) for value in values]) for name in TIME_FIELDS},
        tokens=TokenTotals(
            **{
                name: _sum_tokens([getattr(value.tokens, name) for value in values])
                for name in TokenTotals.model_fields
            }
        ),
        cost_usd=_sum_costs([value.cost_usd for value in values]),
    )


def repetition_telemetry(observations: Sequence[Observation]) -> Telemetry:
    """Include interrupted/superseded attempts once, rejecting mixed repetition identities."""
    identities = {(value.run_id, value.case_id, value.repetition) for value in observations}
    attempts = [value.execution_attempt for value in observations]
    if len(identities) > 1 or len(set(attempts)) != len(attempts):
        raise ValueError("expected unique execution attempts of one repetition")
    return aggregate_telemetry([value.telemetry for value in observations])
