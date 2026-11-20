# AI-assisted with Codex, 2026-11-20; reviewed by Soohyun An
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
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
GitObjectId = Annotated[str, Field(pattern=r"^[0-9a-f]{40}([0-9a-f]{24})?$")]


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


class Cost(StrictModel):
    """Preserve whether a cost was observed, estimated, missing, or inapplicable."""

    applicability: Literal["value", "unavailable", "not_applicable"]
    value: NonNegativeFloat | None
    provenance: Literal["measured", "estimated", "missing", "not_applicable"]
    price_inputs: dict[str, NonNegativeFloat] | None

    @model_validator(mode="after")
    def check_provenance(self) -> Cost:
        """Keep cost value, provenance, and estimation inputs mutually consistent."""
        if self.provenance in {"measured", "estimated"}:
            if self.applicability != "value" or self.value is None:
                raise ValueError("measured or estimated cost requires a value")
        elif self.provenance == "missing":
            if self.applicability != "unavailable" or self.value is not None:
                raise ValueError("missing cost must be unavailable")
        elif self.applicability != "not_applicable" or self.value is not None:
            raise ValueError("inapplicable cost must use not_applicable")
        if self.provenance == "estimated":
            if not self.price_inputs:
                raise ValueError("estimated cost requires price inputs")
        elif self.price_inputs is not None:
            raise ValueError("only estimated cost may carry price inputs")
        return self


# Store every aggregate rate with the counts needed to audit its denominator.
class Rate(StrictModel):
    numerator: NonNegativeInt
    denominator: NonNegativeInt
    value: float | None = Field(ge=0, le=1)

    @model_validator(mode="after")
    def check_rate(self) -> Rate:
        """Reject internally inconsistent rate representations."""
        if self.numerator > self.denominator:
            raise ValueError("rate numerator cannot exceed denominator")
        if self.denominator == 0 and self.value is not None:
            raise ValueError("zero-denominator rates must have a null value")
        if self.denominator > 0:
            expected = self.numerator / self.denominator
            if self.value is None or abs(self.value - expected) > 1e-12:
                raise ValueError("rate value must equal numerator / denominator")
        return self


# Preserve source fields rather than rebuilding recipes from current service data.
class RecipeIngredient(StrictModel):
    name: str
    amount: str | None
    role: Literal["main", "secondary", "seasoning"]


class RecipeStep(StrictModel):
    n: PositiveInt
    text: str


# This snapshot makes later rescoring independent of mutable recipe storage.
class SourceRecipeSnapshot(StrictModel):
    dish_id: str
    source: str
    servings: int | None
    ingredients: list[RecipeIngredient]
    steps: list[RecipeStep]
    tips: list[str]


# Record the effective policy inputs, including the staples list used at execution time.
class ObservationInput(StrictModel):
    dish_id: str
    dish_name: str
    supplied_ingredients: list[str]
    effective_assumed_staples: list[str]
    availability: list[Literal["owned", "assumed", "unavailable"]]
    original_recipe: SourceRecipeSnapshot

    @model_validator(mode="after")
    def check_availability_rows(self) -> ObservationInput:
        """Keep one availability decision for every preserved source ingredient row."""
        if len(self.availability) != len(self.original_recipe.ingredients):
            raise ValueError("availability must align with source ingredient rows")
        return self


# Keep both auditable safe content and a stable identity for compatibility checks.
class RequestSnapshot(StrictModel):
    name: str
    system: str
    user: str
    response_schema: dict[str, Any] = Field(alias="schema")
    sha256: Sha256


# Token categories remain independently nullable because providers may omit a subset.
class Usage(StrictModel):
    input_tokens: NonNegativeInt | None
    output_tokens: NonNegativeInt | None
    reasoning_tokens: NonNegativeInt | None
    cached_tokens: NonNegativeInt | None


# A durable request_prepared identity consumes budget even when delivery cannot
# be confirmed, preventing resume from spending the same budget unit again.
class HttpAttempt(StrictModel):
    index: PositiveInt
    state: Literal["request_prepared", "response_received", "transport_error"]
    prepared_at: str
    request_sha256: Sha256
    model: str
    counts_against_budget: Literal[True]
    delivery: Literal["unknown", "confirmed", "failed"]
    status_code: int | None = Field(default=None, ge=100, le=599)
    provider_round_trip_s: NonNegativeFloat | None
    finish_reason: str | None
    safe_response_text: str | None
    usage: Usage | None
    cost_usd: Cost

    @model_validator(mode="after")
    def check_attempt_state(self) -> HttpAttempt:
        """Keep response-derived fields unknown until a response is durably observed."""
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
        elif self.state == "transport_error":
            if not (
                self.delivery == "failed"
                and self.status_code is None
                and self.finish_reason is None
                and self.safe_response_text is None
                and self.usage is None
                and self.cost_usd.provenance == "missing"
            ):
                raise ValueError("transport_error cannot contain response-derived fields")
        elif self.delivery != "confirmed" or self.status_code is None:
            raise ValueError("response_received requires confirmed delivery and an HTTP status")
        return self


# Parsing is recorded separately from structural and reference validity.
class ParsingResult(StrictModel):
    attempted: bool
    succeeded: bool | None
    error: str | None


# One logical call may contain multiple HTTP attempts after transport retries.
class ModelCall(StrictModel):
    index: PositiveInt
    purpose: Literal["initial", "reask"]
    request: RequestSnapshot
    http_attempts: list[HttpAttempt]
    parsing: ParsingResult
    decoded_answer: dict[str, Any] | list[Any] | str | int | float | bool | None


# These events mirror production checks; they do not define replacement policy.
class CheckEvent(StrictModel):
    phase: Literal["initial", "final"]
    result: Literal["passed", "violation", "refusal_needed", "not_run"]
    code: str | None
    message: str | None


# Deterministic findings annotate answers without repairing or discarding them.
class AnswerEvaluation(StrictModel):
    logical_call_index: PositiveInt
    structure_valid: bool | None
    reference_valid: bool | None
    issues: list[str]


# Keep offline findings independent of production checks and later Judge scores.
class DeterministicEvaluation(StrictModel):
    answers: list[AnswerEvaluation]
    deleted_ingredient_explanation: Rate


# An execution attempt is immutable once completed or preserved as interrupted.
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
        """Prevent incomplete attempts from receiving fabricated terminal outcomes."""
        if self.state == "completed":
            if self.checkpoint_stage != "terminal" or self.finished_at is None:
                raise ValueError("completed execution must be a finished terminal checkpoint")
            if self.terminal_outcome is None or self.outcome_source is None:
                raise ValueError("completed execution requires an outcome and source")
        elif self.terminal_outcome is not None or self.outcome_source is not None:
            raise ValueError("incomplete execution cannot have a terminal outcome")
        return self


# Timing fields separate checkpoint overhead from observed Revision behavior.
class Telemetry(StrictModel):
    logical_calls: NonNegativeInt
    reasks: NonNegativeInt
    http_attempts: NonNegativeInt
    http_429_responses: NonNegativeInt
    http_429_retries: NonNegativeInt
    provider_round_trip_s: OptionalNumber
    revision_s: OptionalNumber
    observed_wall_s: OptionalNumber
    checkpoint_persistence_s: OptionalNumber
    non_http_remainder_s: OptionalNumber
    tokens: Usage
    cost_usd: Cost


# One observation corresponds to one execution attempt, not one planned repetition.
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
        """Ensure telemetry counts the exact logical calls and durable HTTP identities."""
        attempts = [attempt for call in self.model_calls for attempt in call.http_attempts]
        if [call.index for call in self.model_calls] != list(
            range(1, len(self.model_calls) + 1)
        ):
            raise ValueError("logical calls must be one-based and contiguous")
        if self.telemetry.logical_calls != len(self.model_calls):
            raise ValueError("logical-call telemetry does not match model_calls")
        reasks = sum(call.purpose == "reask" for call in self.model_calls)
        if self.telemetry.reasks != reasks:
            raise ValueError("re-ask telemetry does not match model_calls")
        if self.telemetry.http_attempts != len(attempts):
            raise ValueError("HTTP-attempt telemetry must include prepared requests")
        responses_429 = sum(attempt.status_code == 429 for attempt in attempts)
        if self.telemetry.http_429_responses != responses_429:
            raise ValueError("HTTP 429 response telemetry does not match HTTP attempts")
        # A terminal 429 is a response but not a retry unless another request follows it.
        retries_429 = sum(
            previous.status_code == 429
            for call in self.model_calls
            for previous in call.http_attempts[:-1]
        )
        if self.telemetry.http_429_retries != retries_429:
            raise ValueError("HTTP 429 retry telemetry does not match HTTP attempts")
        for call in self.model_calls:
            if [attempt.index for attempt in call.http_attempts] != list(
                range(1, len(call.http_attempts) + 1)
            ):
                raise ValueError("HTTP attempts must be one-based and contiguous per logical call")
        return self


# A plan unit retains all attempts while selecting at most one completed result.
class PlanUnit(StrictModel):
    case_id: str
    repetition: PositiveInt
    state: Literal["completed", "incomplete", "not_started"]
    observation_refs: list[str]
    selected_completed_attempt: PositiveInt | None
    cumulative_telemetry: Telemetry | None


# Budget consumption is cumulative across interrupted and resumed attempts.
class HttpAttemptBudget(StrictModel):
    maximum: PositiveInt
    consumed: NonNegativeInt
    remaining: NonNegativeInt

    @model_validator(mode="after")
    def check_budget(self) -> HttpAttemptBudget:
        """Reject budget totals that could permit overspending after resume."""
        if self.consumed > self.maximum or self.remaining != self.maximum - self.consumed:
            raise ValueError("HTTP-attempt budget arithmetic is inconsistent")
        return self


class CodeIdentity(StrictModel):
    """Record both the checked-out commit and working-tree identity used by a run."""

    commit: GitObjectId
    tree: GitObjectId
    dirty: bool


class InputIdentities(StrictModel):
    """Keep the immutable prompt, schema, input, and fixture hashes behind compatibility."""

    prompt_sha256: Sha256
    response_schema_sha256: Sha256
    input_sha256: dict[str, Sha256]
    fixture_sha256: dict[str, Sha256]


# Metadata is the authoritative index for plan progress and resume compatibility.
class RunMetadata(StrictModel):
    artifact_schema: Literal[METADATA_SCHEMA]
    observation_schema: Literal[OBSERVATION_SCHEMA]
    run_id: str
    state: Literal["running", "interrupted", "completed"]
    created_at: str
    updated_at: str
    compatibility_fingerprint: Sha256
    code_identity: CodeIdentity
    identities: InputIdentities
    effective_assumed_staples: list[str]
    model: dict[str, Any]
    pricing: dict[str, Any]
    http_attempt_budget: HttpAttemptBudget
    plan: list[PlanUnit]
    resume_history: list[dict[str, Any]]


# Keep operational errors distinct from model refusals in aggregate reporting.
class OutcomeCounts(StrictModel):
    unchanged: NonNegativeInt
    revised: NonNegativeInt
    refused: NonNegativeInt
    check_failed: NonNegativeInt
    response_error: NonNegativeInt
    api_error: NonNegativeInt


class Percentiles(StrictModel):
    """Report percentile values together with their sample count and inclusion policy."""

    sample_count: NonNegativeInt
    incomplete_attempt_policy: Literal["exclude", "include_when_available"]
    p50_s: OptionalNumber
    p95_s: OptionalNumber

    @model_validator(mode="after")
    def check_samples(self) -> Percentiles:
        """Require percentiles exactly when at least one sample exists."""
        values_present = self.p50_s.applicability == self.p95_s.applicability == "value"
        if (self.sample_count > 0) != values_present:
            raise ValueError("percentile values must match whether samples exist")
        return self


class LatencySummary(StrictModel):
    revision_s: Percentiles
    observed_wall_s: Percentiles
    checkpoint_persistence_s: Percentiles


class CaseSummary(StrictModel):
    """Describe one case's planned repetitions and selected terminal results."""

    case_id: str
    planned_repetitions: PositiveInt
    completed_repetitions: NonNegativeInt
    all_planned_completed: bool
    outcomes: OutcomeCounts

    @model_validator(mode="after")
    def check_completion(self) -> CaseSummary:
        """Keep the completion flag derived from the explicit repetition counts."""
        if self.completed_repetitions > self.planned_repetitions:
            raise ValueError("completed repetitions cannot exceed planned repetitions")
        if self.all_planned_completed != (
            self.completed_repetitions == self.planned_repetitions
        ):
            raise ValueError("case completion flag does not match repetition counts")
        return self


class SemanticSuccess(StrictModel):
    """Keep semantic success unavailable until a named, versioned definition exists."""

    applicability: Literal["value", "not_applicable"]
    definition: str | None
    rate: Rate | None

    @model_validator(mode="after")
    def check_definition(self) -> SemanticSuccess:
        """Prevent an unnamed semantic-success value from entering the summary."""
        if self.applicability == "value":
            if not self.definition or self.rate is None:
                raise ValueError("semantic success requires a definition and rate")
        elif self.definition is not None or self.rate is not None:
            raise ValueError("inapplicable semantic success cannot carry a definition or rate")
        return self


# Totals include incomplete attempts so interrupted usage is not lost on resume.
class RunTotals(StrictModel):
    completed_repetitions: NonNegativeInt
    incomplete_attempts: NonNegativeInt
    logical_calls: NonNegativeInt
    reasks: NonNegativeInt
    http_attempts: NonNegativeInt
    http_429_responses: NonNegativeInt
    http_429_retries: NonNegativeInt
    provider_round_trip_s: OptionalNumber
    revision_s: OptionalNumber
    observed_wall_s: OptionalNumber
    checkpoint_persistence_s: OptionalNumber
    non_http_remainder_s: OptionalNumber
    tokens: Usage
    cost_usd: Cost


# JSON summary data is authoritative; any Markdown report is only a projection.
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
    initial_failure_codes: dict[str, NonNegativeInt]
    final_failure_codes: dict[str, NonNegativeInt]
    latency: LatencySummary
    cases: list[CaseSummary]
    semantic_success: SemanticSuccess
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
        # Fixture references are untrusted contract data; keep reads inside the bundle.
        if bundle not in path.parents:
            raise ValueError(f"artifact reference escapes fixture root: {relative}")
        return __import__("json").loads(path.read_text(encoding="utf-8"))

    metadata = RunMetadata.model_validate(read("metadata.json"))
    summary = RunSummary.model_validate(read("summary.json"))
    # Preserve declared order while avoiding duplicate files in aggregate accounting.
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
