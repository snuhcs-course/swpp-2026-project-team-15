# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Atomic, run-scoped JSON persistence for v1 evaluation artifacts."""

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from .contract import Observation, RunMetadata, validate_plan_unit_observations
from .telemetry import validate_cumulative_telemetry


class PersistenceError(RuntimeError):
    """A sanitized storage failure that must stop execution before further requests."""


def _safe_run_id(value: str) -> bool:
    """Allow a single portable directory name, excluding Windows device names."""
    reserved = {"CON", "PRN", "AUX", "NUL"} | {
        f"{prefix}{number}" for prefix in ("COM", "LPT") for number in range(1, 10)
    }
    return (
        bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value))
        and value.upper() not in reserved
    )


def _case_directory(case_id: str) -> str:
    """Map case IDs to portable paths without changing IDs stored in artifacts."""
    if _safe_run_id(case_id):
        return case_id
    # Frozen case IDs may contain colons. Hash the full original ID so different
    # spellings with the same readable prefix do not silently share a directory.
    prefix = re.sub(r"[^A-Za-z0-9_-]", "_", case_id)[:40] or "case"
    return f"case-{prefix}-{hashlib.sha256(case_id.encode('utf-8')).hexdigest()[:16]}"


def _redact(value, secrets: tuple[str, ...]):
    """Copy metadata while masking credential fields and configured secret values."""
    sensitive = {"apikey", "authorization", "password", "secret", "token", "accesstoken"}
    if isinstance(value, dict):
        return {
            _redact(key, secrets): "[REDACTED]"
            if re.sub(r"[^a-z]", "", key.lower()) in sensitive
            else _redact(item, secrets)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item, secrets) for item in value]
    if isinstance(value, str):
        for secret in secrets:
            value = value.replace(secret, "[REDACTED]")
    return value


def _preserve_evidence(previous, current) -> None:
    """Allow unknown findings to fill in and lists to grow, never erase known evidence."""
    if previous is None:
        return
    if isinstance(previous, dict) and isinstance(current, dict):
        for key, value in previous.items():
            if key not in current:
                raise ValueError("recorded evidence cannot be removed or replaced")
            _preserve_evidence(value, current[key])
    elif isinstance(previous, list) and isinstance(current, list):
        if len(current) < len(previous):
            raise ValueError("recorded evidence cannot be removed or replaced")
        for old, new in zip(previous, current, strict=False):
            _preserve_evidence(old, new)
    elif previous != current:
        raise ValueError("recorded evidence cannot be removed or replaced")


def _validate_evidence_update(previous: Observation, current: Observation) -> None:
    """Permit checkpoint progress while retaining immutable inputs and recorded events.

    Prepared HTTP attempts may acquire their terminal result; terminal attempts
    and known decoded answers are frozen. Telemetry is derived from retained evidence
    and may be recomputed rather than treated as an append-only event stream.
    """
    if (
        previous.input != current.input
        or previous.execution.started_at != current.execution.started_at
    ):
        raise ValueError("attempt input and start time cannot change")
    if len(current.model_calls) < len(previous.model_calls):
        raise ValueError("recorded model calls cannot be removed")
    for old, new in zip(previous.model_calls, current.model_calls, strict=False):
        if (old.index, old.purpose, old.request) != (new.index, new.purpose, new.request):
            raise ValueError("recorded logical request cannot change")
        if len(new.http_attempts) < len(old.http_attempts):
            raise ValueError("recorded HTTP attempts cannot be removed")
        for old_http, new_http in zip(old.http_attempts, new.http_attempts, strict=False):
            if old_http.state != "request_prepared":
                if old_http != new_http:
                    raise ValueError("recorded HTTP result cannot change")
            else:
                # Only the result fields are unknown at a prepared checkpoint.
                for field in (
                    "index",
                    "prepared_at",
                    "request_sha256",
                    "model",
                    "counts_against_budget",
                ):
                    if getattr(old_http, field) != getattr(new_http, field):
                        raise ValueError("prepared HTTP request cannot change")
                if new_http.cost_usd.confirmed_subtotal < old_http.cost_usd.confirmed_subtotal:
                    raise ValueError("recorded cost subtotal cannot decrease")
        if old.parsing.attempted:
            if old.parsing != new.parsing:
                raise ValueError("recorded parsing result cannot change")
        else:
            for field in ("succeeded", "error"):
                recorded = getattr(old.parsing, field)
                if recorded is not None and recorded != getattr(new.parsing, field):
                    raise ValueError("recorded parsing result cannot change")
        # The HTTP hook records parsing before complete() returns its decoded value.
        if old.decoded_answer is not None and old.decoded_answer != new.decoded_answer:
            raise ValueError("recorded decoded answer cannot change")
    # Check events are complete decisions, not partially populated findings.
    if current.checks[: len(previous.checks)] != previous.checks:
        raise ValueError("recorded check events cannot be removed or replaced")
    _preserve_evidence(
        [item.model_dump() for item in previous.deterministic_evaluation.answers],
        [item.model_dump() for item in current.deterministic_evaluation.answers],
    )
    coverage = previous.deterministic_evaluation.deleted_ingredient_explanation
    if (
        coverage.denominator
        and coverage != current.deterministic_evaluation.deleted_ingredient_explanation
    ):
        raise ValueError("recorded coverage cannot change")
    for field in (
        "finished_at",
        "terminal_outcome",
        "outcome_source",
        "final_service_response",
        "sanitized_error",
    ):
        recorded = getattr(previous.execution, field)
        if recorded is not None and recorded != getattr(current.execution, field):
            raise ValueError("recorded execution result cannot change")


class RunStore:
    """Own one newly created run directory and atomically replace active JSON files.

    This sequential store does not implement resume, run orchestration, or HTTP
    budgeting. The caller supplies contract-valid observations and metadata;
    metadata references are checked against saved observations before publication.
    """

    def __init__(self, parent: Path, run_id: str, *, secrets: tuple[str, ...] = ()) -> None:
        if not _safe_run_id(run_id):
            raise ValueError("run ID must be a portable non-device name of at most 64 characters")
        self.run_id = run_id
        self.root = parent.resolve() / run_id
        self._secrets = tuple(
            sorted((secret for secret in secrets if secret), key=len, reverse=True)
        )
        try:
            # An existing run must never be mistaken for a new run and overwritten.
            self.root.mkdir(parents=True, exist_ok=False)
        except OSError:
            raise PersistenceError("could not create a new run directory") from None

    def _path(self, relative: str) -> Path:
        """Keep reads and writes within this run, including through existing symlinks."""
        if "\\" in relative or ":" in relative or ".." in Path(relative).parts:
            raise ValueError("artifact reference must stay inside the run")
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root) or path == self.root:
            raise ValueError("artifact reference must stay inside the run")
        return path

    def _write(self, relative: str, value: dict) -> None:
        """Flush a same-directory temporary file, then replace the target atomically."""
        path = self._path(relative)
        temporary = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path = self._path(relative)
            descriptor, name = tempfile.mkstemp(
                dir=path.parent, prefix=".checkpoint-", suffix=".tmp"
            )
            temporary = Path(name)
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(
                    value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
                )
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            # No truncation of the old target occurs before the replacement.
            os.replace(temporary, path)
        except (OSError, ValueError, TypeError):
            raise PersistenceError("could not persist artifact") from None
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass  # Cleanup must not mask the original persistence failure.

    def write_observation(self, observation: Observation) -> str:
        """Save a new attempt or replace only its still-running checkpoint; return its ref."""
        value = Observation.model_validate(observation.model_dump(by_alias=True))
        if value.run_id != self.run_id:
            raise ValueError("observation belongs to a different run")
        relative = (
            f"observations/{_case_directory(value.case_id)}__r{value.repetition:02d}/"
            f"attempt-{value.execution_attempt:03d}.json"
        )
        path = self._path(relative)
        if path.exists():
            try:
                previous = Observation.model_validate_json(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raise PersistenceError("could not read existing attempt") from None
            if (
                previous.run_id,
                previous.case_id,
                previous.repetition,
                previous.execution_attempt,
            ) != (
                value.run_id,
                value.case_id,
                value.repetition,
                value.execution_attempt,
            ):
                raise ValueError("attempt identity cannot change")
            if previous.execution.state != "running":
                raise ValueError("completed or interrupted attempts are immutable")
            if value.execution.checkpoint_revision <= previous.execution.checkpoint_revision:
                raise ValueError("checkpoint revision must increase")
            _validate_evidence_update(previous, value)
        self._write(relative, value.model_dump(by_alias=True))
        return relative

    def write_metadata(self, metadata: RunMetadata) -> None:
        """Publish sanitized metadata only when plan states and totals match saved attempts."""
        value = RunMetadata.model_validate(metadata.model_dump(by_alias=True))
        if value.run_id != self.run_id:
            raise ValueError("metadata belongs to a different run")
        for unit in value.plan:
            observations = []
            for reference in unit.observation_refs:
                path = self._path(reference)
                try:
                    observation = Observation.model_validate_json(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    raise PersistenceError("metadata references an unreadable attempt") from None
                if observation.run_id != self.run_id:
                    raise ValueError("metadata references a different run")
                observations.append(observation)
            validate_plan_unit_observations(unit, observations)
            completed = any(item.execution.state == "completed" for item in observations)
            expected = "completed" if completed else "incomplete" if observations else "not_started"
            if unit.state != expected:
                raise ValueError("plan state does not match saved attempts")
            validate_cumulative_telemetry(unit, observations)
        sanitized = _redact(value.model_dump(by_alias=True), self._secrets)
        checked = RunMetadata.model_validate(sanitized)
        if checked.run_id != self.run_id:
            raise ValueError("redaction cannot change run identity")
        self._write("metadata.json", checked.model_dump(by_alias=True))
