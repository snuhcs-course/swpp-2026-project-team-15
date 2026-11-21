# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Capture real, non-secret run provenance using the existing immutable identity helpers."""

import subprocess
from datetime import UTC, datetime
from pathlib import Path

from .compatibility import (
    REPO_ROOT,
    capture_code_identity,
    capture_input_identities,
    compatibility_fingerprint,
)
from .contract import METADATA_SCHEMA, OBSERVATION_SCHEMA, RunMetadata
from .live import LiveSettings
from .persistence import _require_safe, _safe_run_id
from .planning import FROZEN_MANIFEST, ExecutionPlan

FROZEN_RECIPES = FROZEN_MANIFEST.with_name("fixtures.json")


def prepare_metadata(
    run_id: str,
    plan: ExecutionPlan,
    settings: LiveSettings,
    *,
    manifest_path: Path = FROZEN_MANIFEST,
    recipes_path: Path = FROZEN_RECIPES,
    repository_root: Path = REPO_ROOT,
    secrets: tuple[str, ...] = (),
) -> RunMetadata:
    """Return fresh metadata for run_new(), without creating files or reading credentials.

    Capture actual HEAD/working bytes, production templates/schema, supplied input
    snapshots and exact selected fixture bytes. Hash the full ordered plan, then
    return an empty index for publish_plan() to populate. No illustrative fixture
    hashes, environment dumps, configuration-file discovery or network calls occur.
    """
    if (
        not _safe_run_id(run_id)
        or not plan.units
        or len({(unit.case_id, unit.repetition) for unit in plan.units})
        != len(plan.units)
        or set(plan.inputs) != {unit.case_id for unit in plan.units}
        or any(
            unit.state != "not_started" or unit.observation_refs for unit in plan.units
        )
        or any(
            tuple(value.effective_assumed_staples) != plan.effective_assumed_staples
            for value in plan.inputs.values()
        )
    ):
        raise ValueError("provenance requires a valid fresh run plan")
    _require_safe(
        {
            "run_id": run_id,
            "plan": [unit.model_dump() for unit in plan.units],
            "inputs": {case: value.model_dump() for case, value in plan.inputs.items()},
            "model": settings.model_metadata(),
            "pricing": settings.pricing_metadata(),
        },
        secrets,
    )
    try:
        identities = capture_input_identities(plan, manifest_path, recipes_path)
        code = capture_code_identity(repository_root)
    except (OSError, ValueError, subprocess.SubprocessError):
        raise ValueError("could not capture run provenance") from None
    stamp = datetime.now(UTC).isoformat()
    value = RunMetadata(
        artifact_schema=METADATA_SCHEMA,
        observation_schema=OBSERVATION_SCHEMA,
        run_id=run_id,
        state="running",
        created_at=stamp,
        updated_at=stamp,
        compatibility_fingerprint="0" * 64,
        code_identity=code,
        identities=identities,
        effective_assumed_staples=list(plan.effective_assumed_staples),
        model=settings.model_metadata(),
        pricing=settings.pricing_metadata(),
        http_attempt_budget={
            "maximum": settings.maximum,
            "consumed": 0,
            "remaining": settings.maximum,
        },
        plan=[unit.model_copy(deep=True) for unit in plan.units],
        resume_history=[],
    )
    value.compatibility_fingerprint = compatibility_fingerprint(value)
    _require_safe(value.model_dump(by_alias=True), secrets)
    value.plan = []
    return value
