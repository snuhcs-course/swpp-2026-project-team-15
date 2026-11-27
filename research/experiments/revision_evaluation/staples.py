# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Freeze effective assumed staples for availability and auditable run artifacts."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from app.dishes.catalog import Catalog, load_staples
from app.dishes.recipe_names import RecipeNames
from app.dishes.schemas import SourceRecipe

from .contract import Observation, ObservationInput, RunMetadata, SourceRecipeSnapshot
from .persistence import RunStore, _redact


@dataclass(frozen=True, init=False)
class StaplesSnapshot:
    """Capture names once and delegate availability to the unchanged production index.

    Ordered inputs retain first occurrence, without trimming, canonicalization or
    implicit additions. Unordered effective sets use sorted serialization because
    production load_staples returns a frozenset with no source-order information.
    None loads production defaults once (including its water policy); [] is empty.
    """

    names: tuple[str, ...]
    index: RecipeNames = field(repr=False, compare=False)

    def __init__(
        self, effective: Iterable[str] | None = None, *, names_path: Path | str | None = None
    ) -> None:
        source = load_staples() if effective is None else effective
        if isinstance(source, (str, bytes)):
            raise ValueError("effective staples must be an iterable of names")
        names = list(source)
        if any(not isinstance(name, str) for name in names):
            raise ValueError("effective staples must contain only string names")
        ordered = sorted(names) if isinstance(source, (set, frozenset)) else names
        frozen = tuple(dict.fromkeys(ordered))
        object.__setattr__(self, "names", frozen)
        # Supplying the captured set prevents RecipeNames from reloading defaults.
        object.__setattr__(self, "index", RecipeNames.load(names_path, staples=frozenset(frozen)))

    def catalog(self, path: Path | str | None = None) -> Catalog:
        """Build the production catalog with this same captured availability policy."""
        return Catalog.load(path, staples=frozenset(self.names), names=self.index)

    def input_snapshot(
        self, recipe: SourceRecipe, dish_name: str, ingredients: list[str]
    ) -> ObservationInput:
        """Copy contract source fields and compute availability with the frozen index."""
        owned = self.index.owned(ingredients)
        return ObservationInput(
            dish_id=recipe.dish_id,
            dish_name=dish_name,
            supplied_ingredients=list(ingredients),
            effective_assumed_staples=list(self.names),
            availability=[self.index.status(row.name, owned) for row in recipe.ingredients],
            original_recipe=SourceRecipeSnapshot.model_validate(
                recipe.model_dump(include=set(SourceRecipeSnapshot.model_fields))
            ),
        )

    def metadata_snapshot(self, metadata: RunMetadata) -> RunMetadata:
        """Return a detached run-metadata copy with the exact captured list."""
        value = metadata.model_dump(by_alias=True)
        value["effective_assumed_staples"] = list(self.names)
        return RunMetadata.model_validate(value)


class StaplesRunStore(RunStore):
    """Bind every observation and metadata write to one immutable run snapshot.

    Existing atomic/evidence-preserving persistence is unchanged. Run assembly
    must use snapshot.index for Reviser and snapshot.input_snapshot for its input;
    resume compatibility and run orchestration remain separate layers.
    """

    def __init__(
        self, parent: Path, run_id: str, *, snapshot: StaplesSnapshot, secrets: tuple[str, ...] = ()
    ) -> None:
        self._bind_snapshot(snapshot, secrets)
        super().__init__(parent, run_id, secrets=secrets)

    def _bind_snapshot(self, snapshot: StaplesSnapshot, secrets: tuple[str, ...]) -> None:
        """Apply the same policy/redaction validation for fresh and reopened stores."""
        self._snapshot = snapshot
        # Redaction must not silently change the policy that the artifacts claim
        # was used. A credential/name collision cannot be represented faithfully.
        if _redact(list(snapshot.names), tuple(secret for secret in secrets if secret)) != list(
            snapshot.names
        ):
            raise ValueError("redaction would change the assumed-staples snapshot")

    @classmethod
    def _open_existing(
        cls,
        root: Path,
        *,
        run_id: str,
        snapshot: StaplesSnapshot,
        secrets: tuple[str, ...] = (),
    ):
        """Initialize captured policy without invoking the exclusive-creation constructor."""
        store = super()._open_existing(root, run_id=run_id, secrets=secrets)
        store._bind_snapshot(snapshot, secrets)
        return store

    @property
    def snapshot(self) -> StaplesSnapshot:
        """Return the run's captured policy, never reconstructed from configuration."""
        return self._snapshot

    def _check_snapshot(self, names: list[str]) -> None:
        """Reject reordered, duplicate or changed policy data before any write."""
        if tuple(names) != self.snapshot.names:
            raise ValueError("assumed staples do not match the run snapshot")

    def write_observation(self, observation: Observation) -> str:
        """Persist only an attempt that names this run's exact effective staples."""
        self._check_snapshot(observation.input.effective_assumed_staples)
        return super().write_observation(observation)

    def write_metadata(self, metadata: RunMetadata) -> None:
        """Keep the run-level snapshot identical across all metadata updates."""
        self._check_snapshot(metadata.effective_assumed_staples)
        super().write_metadata(metadata)
