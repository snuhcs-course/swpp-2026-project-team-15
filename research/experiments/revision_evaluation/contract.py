"""Strict v1 models and deterministic JSON Schema for Revision evaluation artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.json_schema import models_json_schema

METADATA_SCHEMA = "revision-evaluation-metadata/v1"
OBSERVATION_SCHEMA = "revision-evaluation-observation/v1"
SUMMARY_SCHEMA = "revision-evaluation-summary/v1"
ARTIFACT_SCHEMAS = (METADATA_SCHEMA, OBSERVATION_SCHEMA, SUMMARY_SCHEMA)

PositiveInt = Annotated[int, Field(ge=1)]
NonNegativeInt = Annotated[int, Field(ge=0)]
NonNegativeFloat = Annotated[float, Field(ge=0)]


class StrictModel(BaseModel):
    """Forbid unversioned fields from silently entering the public contract."""

    model_config = ConfigDict(extra="forbid")


class OptionalNumber(StrictModel):
    """Represent a number while distinguishing unavailable and inapplicable values."""

    applicability: Literal["value", "unavailable", "not_applicable"]
    value: NonNegativeFloat | None

    @model_validator(mode="after")
    def check_value_matches_applicability(self) -> OptionalNumber:
        if (self.applicability == "value") != (self.value is not None):
            raise ValueError("value must be present exactly when applicability is 'value'")
        return self


class Rate(StrictModel):
    numerator: NonNegativeInt
    denominator: NonNegativeInt
    value: float | None = Field(ge=0, le=1)

    @model_validator(mode="after")
    def check_rate(self) -> Rate:
        if self.numerator > self.denominator:
            raise ValueError("rate numerator cannot exceed denominator")
        if self.denominator == 0 and self.value is not None:
            raise ValueError("zero-denominator rates must have a null value")
        if self.denominator > 0:
            expected = self.numerator / self.denominator
            if self.value is None or abs(self.value - expected) > 1e-12:
                raise ValueError("rate value must equal numerator / denominator")
        return self


class RecipeIngredient(StrictModel):
    name: str
    amount: str | None
    role: Literal["main", "secondary", "seasoning"]


class RecipeStep(StrictModel):
    n: PositiveInt
    text: str


class SourceRecipeSnapshot(StrictModel):
    dish_id: str
    source: str
    servings: int | None
    ingredients: list[RecipeIngredient]
    steps: list[RecipeStep]
    tips: list[str]


class ObservationInput(StrictModel):
    dish_id: str
    dish_name: str
    supplied_ingredients: list[str]
    effective_assumed_staples: list[str]
    availability: list[Literal["owned", "assumed", "unavailable"]]
    original_recipe: SourceRecipeSnapshot


class RequestSnapshot(StrictModel):
    name: str
    system: str
    user: str
    response_schema: dict[str, Any] = Field(alias="schema")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Usage(StrictModel):
    input_tokens: NonNegativeInt | None
    output_tokens: NonNegativeInt | None
    reasoning_tokens: NonNegativeInt | None
    cached_tokens: NonNegativeInt | None


class HttpAttempt(StrictModel):
    index: PositiveInt
    state: Literal["request_prepared", "response_received", "transport_error"]
    prepared_at: str
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model: str
    counts_against_budget: Literal[True]
    delivery: Literal["unknown", "confirmed", "failed"]
    status_code: int | None = Field(default=None, ge=100, le=599)
    provider_round_trip_s: NonNegativeFloat | None
    finish_reason: str | None
    safe_response_text: str | None
    usage: Usage | None
    cost_usd: OptionalNumber

    @model_validator(mode="after")
    def check_attempt_state(self) -> HttpAttempt:
        if self.state == "request_prepared":
            unavailable = (
                self.delivery == "unknown"
                and self.status_code is None
                and self.provider_round_trip_s is None
                and self.finish_reason is None
                and self.safe_response_text is None
                and self.usage is None
                and self.cost_usd.applicability == "unavailable"
            )
            if not unavailable:
                raise ValueError("request_prepared must retain unknown response and cost fields")
        return self


class ParsingResult(StrictModel):
    attempted: bool
    succeeded: bool | None
    error: str | None


class ModelCall(StrictModel):
    index: PositiveInt
    purpose: Literal["initial", "reask"]
    request: RequestSnapshot
    http_attempts: list[HttpAttempt]
    parsing: ParsingResult
    decoded_answer: dict[str, Any] | list[Any] | str | int | float | bool | None


class CheckEvent(StrictModel):
    phase: Literal["initial", "final"]
    result: Literal["passed", "violation", "refusal_needed", "not_run"]
    code: str | None
    message: str | None


class AnswerEvaluation(StrictModel):
    logical_call_index: PositiveInt
    structure_valid: bool | None
    reference_valid: bool | None
    issues: list[str]


class DeterministicEvaluation(StrictModel):
    answers: list[AnswerEvaluation]
    deleted_ingredient_explanation: Rate


class Execution(StrictModel):
    state: Literal["running", "completed", "interrupted"]
    checkpoint_revision: PositiveInt
    checkpoint_stage: Literal[
        "attempt_created",
        "request_prepared",
        "response_received",
        "json_parsed",
        "check_completed",
        "terminal",
    ]
    started_at: str
    finished_at: str | None
    terminal_outcome: (
        Literal["unchanged", "revised", "refused", "check_failed", "response_error", "api_error"]
        | None
    )
    outcome_source: (
        Literal["no_change", "prescreen", "model", "production_check", "response", "transport"]
        | None
    )
    final_service_response: dict[str, Any] | None
    sanitized_error: str | None

    @model_validator(mode="after")
    def check_terminal_state(self) -> Execution:
        if self.state == "completed":
            if self.checkpoint_stage != "terminal" or self.finished_at is None:
                raise ValueError("completed execution must be a finished terminal checkpoint")
            if self.terminal_outcome is None or self.outcome_source is None:
                raise ValueError("completed execution requires an outcome and source")
        elif self.terminal_outcome is not None or self.outcome_source is not None:
            raise ValueError("incomplete execution cannot have a terminal outcome")
        return self


class Telemetry(StrictModel):
    logical_calls: NonNegativeInt
    reasks: NonNegativeInt
    http_attempts: NonNegativeInt
    http_429_retries: NonNegativeInt
    provider_round_trip_s: OptionalNumber
    revision_s: OptionalNumber
    observed_wall_s: OptionalNumber
    checkpoint_persistence_s: OptionalNumber
    non_http_remainder_s: OptionalNumber
    tokens: Usage
    cost_usd: OptionalNumber


class Observation(StrictModel):
    artifact_schema: Literal[OBSERVATION_SCHEMA]
    run_id: str
    case_id: str
    repetition: PositiveInt
    execution_attempt: PositiveInt
    input: ObservationInput
    execution: Execution
    model_calls: list[ModelCall]
    checks: list[CheckEvent]
    deterministic_evaluation: DeterministicEvaluation
    telemetry: Telemetry

    @model_validator(mode="after")
    def check_attempt_counts(self) -> Observation:
        attempts = [attempt for call in self.model_calls for attempt in call.http_attempts]
        if self.telemetry.logical_calls != len(self.model_calls):
            raise ValueError("logical-call telemetry does not match model_calls")
        if self.telemetry.http_attempts != len(attempts):
            raise ValueError("HTTP-attempt telemetry must include prepared requests")
        for call in self.model_calls:
            if [attempt.index for attempt in call.http_attempts] != list(
                range(1, len(call.http_attempts) + 1)
            ):
                raise ValueError("HTTP attempts must be one-based and contiguous per logical call")
        return self


class PlanUnit(StrictModel):
    case_id: str
    repetition: PositiveInt
    state: Literal["completed", "incomplete", "not_started"]
    observation_refs: list[str]
    selected_completed_attempt: PositiveInt | None


class HttpAttemptBudget(StrictModel):
    maximum: PositiveInt
    consumed: NonNegativeInt
    remaining: NonNegativeInt

    @model_validator(mode="after")
    def check_budget(self) -> HttpAttemptBudget:
        if self.consumed > self.maximum or self.remaining != self.maximum - self.consumed:
            raise ValueError("HTTP-attempt budget arithmetic is inconsistent")
        return self


class RunMetadata(StrictModel):
    artifact_schema: Literal[METADATA_SCHEMA]
    observation_schema: Literal[OBSERVATION_SCHEMA]
    run_id: str
    state: Literal["running", "interrupted", "completed"]
    created_at: str
    updated_at: str
    compatibility_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    effective_assumed_staples: list[str]
    model: dict[str, Any]
    pricing: dict[str, Any]
    http_attempt_budget: HttpAttemptBudget
    plan: list[PlanUnit]
    resume_history: list[dict[str, Any]]


class OutcomeCounts(StrictModel):
    unchanged: NonNegativeInt
    revised: NonNegativeInt
    refused: NonNegativeInt
    check_failed: NonNegativeInt
    response_error: NonNegativeInt
    api_error: NonNegativeInt


class RunTotals(StrictModel):
    completed_repetitions: NonNegativeInt
    incomplete_attempts: NonNegativeInt
    logical_calls: NonNegativeInt
    http_attempts: NonNegativeInt
    tokens: Usage
    cost_usd: OptionalNumber


class RunSummary(StrictModel):
    artifact_schema: Literal[SUMMARY_SCHEMA]
    observation_schema: Literal[OBSERVATION_SCHEMA]
    run_id: str
    complete: bool
    generated_at: str
    observation_refs: list[str]
    outcomes: OutcomeCounts
    json_parse_success: Rate
    structural_validity: Rate
    reference_validity: Rate
    explanation_coverage: Rate
    totals: RunTotals


Artifact = RunMetadata | Observation | RunSummary


class ContractVersionError(ValueError):
    """Raised when an artifact does not declare one of the frozen v1 schema IDs."""


def validate_artifact(value: dict[str, Any]) -> Artifact:
    """Validate one artifact after selecting its model only from the explicit schema ID."""
    schema = value.get("artifact_schema")
    models: dict[str, type[RunMetadata] | type[Observation] | type[RunSummary]] = {
        METADATA_SCHEMA: RunMetadata,
        OBSERVATION_SCHEMA: Observation,
        SUMMARY_SCHEMA: RunSummary,
    }
    model = models.get(schema)
    if model is None:
        raise ContractVersionError(f"unsupported artifact schema: {schema!r}")
    return model.model_validate(value)


def schema_document() -> dict[str, Any]:
    """Return one deterministic JSON Schema document with all public v1 entry points."""
    roots, shared = models_json_schema(
        [(RunMetadata, "validation"), (Observation, "validation"), (RunSummary, "validation")],
        title="Revision evaluation artifact contract v1",
        description="Full Runner artifacts; Judge payload selection is a separate contract.",
        ref_template="#/$defs/{model}",
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://mylittlechef.invalid/schemas/revision-evaluation/v1",
        "title": "Revision evaluation artifact contract v1",
        "description": "Full Runner artifacts; Judge payload selection is a separate contract.",
        "oneOf": [roots[(model, "validation")] for model in (RunMetadata, Observation, RunSummary)],
        "$defs": shared.get("$defs", {}),
    }


def fixture_root() -> Path:
    """Return the committed self-contained contract fixture directory."""
    return Path(__file__).with_name("fixtures") / "contract-v1"


def validate_fixture_bundle(
    root: Path | None = None,
) -> tuple[RunMetadata, list[Observation], RunSummary]:
    """Validate a self-contained bundle, including references and budget accounting."""
    bundle = (root or fixture_root()).resolve()

    def read(relative: str) -> dict[str, Any]:
        path = (bundle / relative).resolve()
        if bundle not in path.parents:
            raise ValueError(f"artifact reference escapes fixture root: {relative}")
        return __import__("json").loads(path.read_text(encoding="utf-8"))

    metadata = RunMetadata.model_validate(read("metadata.json"))
    summary = RunSummary.model_validate(read("summary.json"))
    refs = list(dict.fromkeys(summary.observation_refs))
    observations = [Observation.model_validate(read(reference)) for reference in refs]
    if any(value.run_id != metadata.run_id for value in [summary, *observations]):
        raise ValueError("all bundle artifacts must share one run_id")
    metadata_refs = [reference for unit in metadata.plan for reference in unit.observation_refs]
    if set(metadata_refs) != set(refs):
        raise ValueError("metadata and summary observation references differ")
    consumed = sum(value.telemetry.http_attempts for value in observations)
    if (
        metadata.http_attempt_budget.consumed != consumed
        or summary.totals.http_attempts != consumed
    ):
        raise ValueError("HTTP-attempt budget must include every stored prepared identity")
    return metadata, observations, summary
