# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Offline manifest loading and explicit sequential repetition planning."""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from app.dishes.roles import DishCatalog, RecipeBook
from pydantic import BaseModel, ConfigDict, Field

from .contract import ObservationInput, PlanUnit, RunMetadata
from .staples import StaplesRunStore, StaplesSnapshot

FROZEN_MANIFEST = (
    Path(__file__).resolve().parent.parent / "dish_revision" / "cases.json"
)


class ManifestCase(BaseModel):
    """Validate execution inputs while retaining labels and annotations unchanged."""

    model_config = ConfigDict(extra="allow", strict=True)
    id: str = Field(min_length=1)
    dish_id: str = Field(min_length=1)
    ingredients: list[str]


def load_manifest(path: Path = FROZEN_MANIFEST) -> list[ManifestCase]:
    """Read schema-1 cases offline; reject malformed/duplicate entries without filtering.

    Historical expect/note fields are retained as annotations, not interpreted as
    quality truth or used to change case selection or production decisions.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if (
            not isinstance(data, dict)
            or type(data.get("schema")) is not int
            or data["schema"] != 1
            or not isinstance(data.get("cases"), list)
            or not data["cases"]
        ):
            raise ValueError
        cases = [ManifestCase.model_validate(row) for row in data["cases"]]
        if len({case.id for case in cases}) != len(cases):
            raise ValueError
    except (OSError, UnicodeError, ValueError):
        # Validation exceptions may embed manifest content; expose no raw data.
        raise ValueError("manifest must contain unique valid schema-1 cases") from None
    return cases


@dataclass(frozen=True)
class ExecutionPlan:
    """Detached initial units and per-case inputs under one effective staples policy."""

    units: tuple[PlanUnit, ...]
    inputs: dict[str, ObservationInput]
    effective_assumed_staples: tuple[str, ...]


def build_plan(
    manifest: Sequence[ManifestCase],
    case_ids: Sequence[str],
    repetitions: int,
    *,
    recipes: RecipeBook,
    catalog: DishCatalog,
    snapshot: StaplesSnapshot,
) -> ExecutionPlan:
    """Expand caller-ordered explicit cases into one-based sequential repetitions.

    Validate selection before resolving recipes or computing availability. No model
    is constructed, no cases generated or relabelled, and no artifacts are written.
    Empty ingredient lists are valid fridges and are never silently excluded.
    """
    if type(repetitions) is not int or repetitions < 1:
        raise ValueError("repetitions must be a positive integer")
    if isinstance(case_ids, (str, bytes)) or not case_ids:
        raise ValueError("case selection must be a nonempty sequence of IDs")
    if any(not isinstance(case_id, str) for case_id in case_ids):
        raise ValueError("selected case IDs must be strings")
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("duplicate selected case IDs")
    cases = [ManifestCase.model_validate(case.model_dump()) for case in manifest]
    by_id = {case.id: case for case in cases}
    if len(by_id) != len(cases):
        raise ValueError("duplicate manifest case IDs")
    if any(case_id not in by_id for case_id in case_ids):
        raise ValueError("unknown selected case ID")
    inputs = {}
    units = []
    for case_id in case_ids:
        case = by_id[case_id]
        recipe, dish = recipes.get(case.dish_id), catalog.get(case.dish_id)
        if recipe is None or dish is None:
            raise ValueError("selected case has no source recipe or catalog dish")
        inputs[case_id] = snapshot.input_snapshot(recipe, dish.name, case.ingredients)
        units.extend(
            PlanUnit(
                case_id=case_id,
                repetition=repetition,
                state="not_started",
                observation_refs=[],
                selected_completed_attempt=None,
                cumulative_telemetry=None,
            )
            for repetition in range(1, repetitions + 1)
        )
    return ExecutionPlan(tuple(units), inputs, snapshot.names)


def publish_plan(
    plan: ExecutionPlan, store: StaplesRunStore, metadata: RunMetadata
) -> RunMetadata:
    """Publish an initial plan/policy through existing atomic metadata persistence.

    The caller supplies real run identities/configuration; this layer invents no
    fingerprints or code hashes. Resume and progress updates are not initial plans
    and must not be reset through this helper. Return a detached metadata value.
    """
    if (
        metadata.plan
        or metadata.state != "running"
        or metadata.http_attempt_budget.consumed
        or metadata.resume_history
        or (store.root / "metadata.json").exists()
    ):
        raise ValueError("initial plan requires fresh unstarted metadata")
    if plan.effective_assumed_staples != store.snapshot.names:
        raise ValueError("plan and run store must share the effective staples snapshot")
    value = store.snapshot.metadata_snapshot(metadata)
    value.plan = [unit.model_copy(deep=True) for unit in plan.units]
    store.write_metadata(value)
    return value
