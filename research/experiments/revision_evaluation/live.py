# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Explicit live authorization and production-model assembly behind a durable cap."""

import os
from dataclasses import asdict, dataclass

import httpx
from app.dishes.llm import DEFAULT_MODEL, MAX_TOKENS, DishLLM

from .budgeting import BudgetedRunStore, read_run_budget
from .checkpointing import (
    AttemptCheckpointer,
    CheckpointModelCallRecorder,
    CheckpointTransport,
)
from .contract import RunMetadata
from .telemetry import TokenPrices


@dataclass(frozen=True)
class LiveSettings:
    """Non-secret settings; temperature/token defaults remain production policy."""

    model_id: str
    maximum: int
    prices: TokenPrices | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.model_id, str) or not self.model_id.strip():
            raise ValueError("model ID must be nonempty")
        if type(self.maximum) is not int or self.maximum < 1:
            raise ValueError("HTTP-attempt maximum must be a positive integer")
        if self.prices is not None and not isinstance(self.prices, TokenPrices):
            raise ValueError("token prices must use explicit validated price inputs")

    def model_metadata(self) -> dict:
        """Describe the exact production settings, without a credential field."""
        return {"id": self.model_id, "temperature": 0, "max_tokens": MAX_TOKENS}

    def pricing_metadata(self) -> dict:
        """Retain explicit estimate inputs, or an empty configuration for missing cost."""
        return asdict(self.prices) if self.prices is not None else {}


def resolve_live_settings(
    *,
    model_id: str | None = None,
    maximum: int | None = None,
    input_price: float | None = None,
    output_price: float | None = None,
    stored: RunMetadata | None = None,
) -> LiveSettings:
    """Resolve explicit start settings or unchanged resume settings; never reset a cap."""
    if stored is not None:
        if maximum is not None and maximum != stored.http_attempt_budget.maximum:
            raise ValueError("HTTP-attempt maximum cannot change on resume")
        maximum = stored.http_attempt_budget.maximum
        model_id = stored.model.get("id") if model_id is None else model_id
        if (
            stored.model.get("temperature", 0) != 0
            or stored.model.get("max_tokens", MAX_TOKENS) != MAX_TOKENS
        ):
            raise ValueError("stored model settings do not match production policy")
        if input_price is None and output_price is None:
            input_price = stored.pricing.get("input_per_million_usd")
            output_price = stored.pricing.get("output_per_million_usd")
    if (input_price is None) != (output_price is None):
        raise ValueError("both input and output token prices must be configured")
    prices = TokenPrices(input_price, output_price) if input_price is not None else None
    return LiveSettings(
        DEFAULT_MODEL if model_id is None else model_id, maximum, prices
    )


def require_live_key(allow_live_api: bool) -> str:
    """Read only the configured environment key, and only after explicit opt-in."""
    if allow_live_api is not True:
        raise ValueError("live model access requires explicit opt-in")
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key.strip():
        raise ValueError("live model access requires a configured API key")
    return key


def make_live_model(
    settings: LiveSettings,
    checkpointer: AttemptCheckpointer,
    *,
    allow_live_api: bool,
    transport: httpx.BaseTransport | None = None,
) -> CheckpointModelCallRecorder:
    """Create a fresh call recorder using unchanged production retry/time policies.

    The caller must first publish a complete compatible run configuration. Every
    billable send is subsequently gated by the store's durable checkpoint budget.
    Neither construction nor authorization sends a request or advances the run.
    """
    key = require_live_key(allow_live_api)
    store = checkpointer.store
    if not isinstance(store, BudgetedRunStore) or store.maximum != settings.maximum:
        raise ValueError("live model requires the matching budgeted run store")
    state = read_run_budget(store.root, maximum=settings.maximum)
    if (
        state.metadata.model != settings.model_metadata()
        or state.metadata.pricing != settings.pricing_metadata()
        or checkpointer.prices != settings.prices
    ):
        raise ValueError("live model settings do not match the persisted run")
    if state.budget.remaining == 0:
        raise ValueError("HTTP-attempt budget exhausted")
    recorded = CheckpointTransport(
        transport if transport is not None else httpx.HTTPTransport(),
        checkpointer=checkpointer,
    )
    model = DishLLM(
        key, settings.model_id, transport=recorded, clock=checkpointer.policy_time
    )
    return CheckpointModelCallRecorder(model, checkpointer=checkpointer)
