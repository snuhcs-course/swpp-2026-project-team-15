# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Sequential HTTP-attempt budgets enforced at the durable checkpoint boundary."""

from dataclasses import dataclass
from pathlib import Path

from .compatibility import load_resume_metadata
from .contract import HttpAttemptBudget, Observation, RunMetadata
from .persistence import PersistenceError
from .staples import StaplesRunStore


class BudgetExceeded(RuntimeError):
    """The next prepared identity would exceed the run's immutable HTTP cap."""


@dataclass(frozen=True)
class BudgetState:
    """A read-only view of durable attempts, including unindexed active checkpoints."""

    metadata: RunMetadata
    observations: tuple[Observation, ...]
    budget: HttpAttemptBudget


def _identity(value: Observation) -> tuple[str, int, int]:
    """Identify an execution independently of its mutable checkpoint revision."""
    return value.case_id, value.repetition, value.execution_attempt


def _observations(root: Path, metadata: RunMetadata) -> tuple[Observation, ...]:
    """Read every durable observation, not just refs from potentially lagging metadata."""
    root = root.resolve()
    directory = root / "observations"
    if not directory.resolve().is_relative_to(root):
        raise ValueError("observation directory escapes the run")
    values, refs, identities = [], set(), set()
    for path in sorted(directory.rglob("*.json")):
        if not path.resolve().is_relative_to(root):
            raise ValueError("observation reference escapes the run")
        value = Observation.model_validate_json(path.read_text(encoding="utf-8"))
        if value.run_id != metadata.run_id or _identity(value) in identities:
            raise ValueError("durable observation identity is inconsistent")
        if not any(
            unit.case_id == value.case_id and unit.repetition == value.repetition
            for unit in metadata.plan
        ):
            raise ValueError("durable observation is not planned")
        identities.add(_identity(value))
        refs.add(path.relative_to(root).as_posix())
        values.append(value)
    declared = {ref for unit in metadata.plan for ref in unit.observation_refs}
    if not declared.issubset(refs):
        raise ValueError("metadata references missing durable evidence")
    return tuple(values)


def read_run_budget(root: Path, *, maximum: int | None = None) -> BudgetState:
    """Recompute consumption from all persisted prepared identities without any writes.

    A checkpoint may be newer than the metadata index. Its unknown delivery still
    consumes budget. A higher stored consumption than the evidence supports is an
    error, not permission to reclaim units from missing/erased observations.
    """
    try:
        metadata = load_resume_metadata(root)
        if maximum is not None and maximum != metadata.http_attempt_budget.maximum:
            raise ValueError("HTTP-attempt maximum cannot change")
        observations = _observations(root, metadata)
        consumed = sum(value.telemetry.http_attempts for value in observations)
        if consumed < metadata.http_attempt_budget.consumed:
            raise ValueError("durable budget evidence is missing")
        cap = metadata.http_attempt_budget.maximum
        return BudgetState(
            metadata,
            observations,
            HttpAttemptBudget(maximum=cap, consumed=consumed, remaining=cap - consumed),
        )
    except (OSError, ValueError):
        raise PersistenceError("could not validate durable HTTP budget") from None


class BudgetedRunStore(StaplesRunStore):
    """Check the original run cap before publishing any additional prepared identity.

    All I/O occurs inside AttemptCheckpointer's measured publication interval, so
    budget scanning cannot shorten production retry/re-ask time budgets. Existing
    atomic writes and evidence immutability remain owned by the parent store.
    This store is sequential, not a concurrent reservation/locking mechanism.
    """

    def __init__(self, parent: Path, run_id: str, *, maximum: int, **kwargs) -> None:
        if type(maximum) is not int or maximum < 1:
            raise ValueError("HTTP-attempt maximum must be a positive integer")
        self._maximum = maximum
        super().__init__(parent, run_id, **kwargs)

    @property
    def maximum(self) -> int:
        """Return the configured original cap, never a fresh per-resume allowance."""
        return self._maximum

    def write_observation(self, observation: Observation) -> str:
        """Reject over-budget intent before the inherited durable pre-send write."""
        value = Observation.model_validate(observation.model_dump(by_alias=True))
        state = read_run_budget(self.root, maximum=self.maximum)
        if state.metadata.state == "completed":
            raise ValueError("completed runs are immutable")
        if value.run_id != self.run_id or not any(
            unit.case_id == value.case_id and unit.repetition == value.repetition
            for unit in state.metadata.plan
        ):
            raise ValueError("observation is not part of this run plan")
        # Replace the active checkpoint's contribution, never add it a second time.
        consumed = (
            sum(
                previous.telemetry.http_attempts
                for previous in state.observations
                if _identity(previous) != _identity(value)
            )
            + value.telemetry.http_attempts
        )
        if consumed > self.maximum:
            raise BudgetExceeded("HTTP-attempt budget exhausted")
        return super().write_observation(value)

    def write_metadata(self, metadata: RunMetadata) -> None:
        """Publish only the original cap and the current durable cumulative count."""
        value = RunMetadata.model_validate(metadata.model_dump())
        if value.http_attempt_budget.maximum != self.maximum:
            raise ValueError("HTTP-attempt maximum cannot change")
        if (self.root / "metadata.json").exists():
            state = read_run_budget(self.root, maximum=self.maximum)
            if state.metadata.state == "completed":
                raise ValueError("completed runs are immutable")
        observations = _observations(self.root, value)
        consumed = sum(item.telemetry.http_attempts for item in observations)
        if value.http_attempt_budget.consumed != consumed:
            raise ValueError(
                "metadata budget must include every durable prepared identity"
            )
        super().write_metadata(value)
