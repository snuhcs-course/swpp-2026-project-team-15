# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Ensure stored staples are the policy used, not reconstructed configuration."""

from dataclasses import FrozenInstanceError

import pytest
from experiments.revision_evaluation import staples
from experiments.revision_evaluation.contract import Observation, PlanUnit, RunMetadata
from experiments.revision_evaluation.generate_contract import fixture_metadata, fixture_observations
from experiments.revision_evaluation.staples import StaplesRunStore, StaplesSnapshot

from app.dishes import catalog as catalog_module
from app.dishes import recipe_names
from app.dishes.recipe_names import RecipeNames
from app.dishes.revision import Reviser
from app.dishes.schemas import SourceRecipe


def artifacts(snapshot):
    """Create matching run/attempt artifacts without changing committed fixtures."""
    observations = fixture_observations()
    value = Observation.model_validate(observations["unchanged__r01/attempt-001.json"])
    recipe = SourceRecipe.model_validate(value.input.original_recipe.model_dump())
    value.input = snapshot.input_snapshot(recipe, "Fixture Rice", ["밥", "대파"])
    metadata = snapshot.metadata_snapshot(
        RunMetadata.model_validate(fixture_metadata(observations))
    )
    metadata.plan = []
    return value, metadata


def test_ordered_effective_names_are_deduplicated_without_rewriting_them():
    original = ["소금", "물", "소금", "간 장", "진간장"]
    snapshot = StaplesSnapshot(original)
    assert snapshot.names == ("소금", "물", "간 장", "진간장")
    assert original == ["소금", "물", "소금", "간 장", "진간장"]
    with pytest.raises(FrozenInstanceError):
        snapshot.names = ("대파",)


@pytest.mark.parametrize("source", [{"소금", "물", "간장"}, frozenset({"간장", "소금", "물"})])
def test_unordered_effective_sets_have_a_deterministic_serialization(source):
    assert StaplesSnapshot(source).names == tuple(sorted(source))


def test_explicit_empty_policy_does_not_load_defaults_or_add_water(monkeypatch):
    def unexpected_load():
        raise AssertionError("must not reload default staples")

    monkeypatch.setattr(staples, "load_staples", unexpected_load)
    snapshot = StaplesSnapshot([])
    assert snapshot.names == ()
    assert snapshot.index.status("물", set()) == "unavailable"
    assert snapshot.catalog().staples == frozenset()


def test_defaults_are_loaded_once_with_production_water_policy(monkeypatch):
    calls = []
    production_effective = catalog_module.load_staples()

    def load():
        calls.append(True)
        return production_effective

    monkeypatch.setattr(staples, "load_staples", load)
    snapshot = StaplesSnapshot()
    assert calls == [True]
    assert snapshot.names == tuple(sorted(production_effective))
    assert "물" in snapshot.names
    assert snapshot.catalog().staples == production_effective
    assert calls == [True]


@pytest.mark.parametrize("source", ["소금", b"salt", ["소금", None], ["소금", 1]])
def test_invalid_policy_input_is_not_silently_coerced(source):
    with pytest.raises(ValueError, match="effective staples"):
        StaplesSnapshot(source)


def test_snapshot_survives_configuration_changes_and_is_stored_at_both_levels(
    tmp_path, monkeypatch
):
    configuration = ["소금", "물", "소금"]
    snapshot = StaplesSnapshot(configuration)
    value, metadata = artifacts(snapshot)
    store = StaplesRunStore(tmp_path, value.run_id, snapshot=snapshot)
    reference = store.write_observation(value)
    metadata.plan = [
        PlanUnit.model_validate(
            {
                "case_id": value.case_id,
                "repetition": value.repetition,
                "state": "completed",
                "observation_refs": [reference],
                "selected_completed_attempt": 1,
                "cumulative_telemetry": value.telemetry.model_dump(),
            }
        )
    ]
    metadata = RunMetadata.model_validate(metadata.model_dump(by_alias=True))
    store.write_metadata(metadata)
    observation_bytes = (store.root / reference).read_bytes()
    original_metadata = metadata.model_dump(by_alias=True)

    configuration[:] = ["대파", "달걀"]

    def unexpected_load(*args, **kwargs):
        raise AssertionError("stored snapshots must not consult current staples")

    monkeypatch.setattr(staples, "load_staples", unexpected_load)
    monkeypatch.setattr(catalog_module, "load_staples", unexpected_load)
    monkeypatch.setattr(recipe_names, "load_staples", unexpected_load)
    assert snapshot.catalog().staples == frozenset({"소금", "물"})
    assert snapshot.index.status("소금", set()) == "assumed"
    assert snapshot.index.status("대파", set()) == "unavailable"
    updated = snapshot.metadata_snapshot(metadata)
    store.write_metadata(updated)
    saved = RunMetadata.model_validate_json(
        (store.root / "metadata.json").read_text(encoding="utf-8")
    )
    assert (
        saved.effective_assumed_staples == value.input.effective_assumed_staples == ["소금", "물"]
    )
    assert metadata.model_dump(by_alias=True) == original_metadata
    assert (store.root / reference).read_bytes() == observation_bytes


@pytest.mark.parametrize("replacement", [["물", "소금"], ["소금"], ["소금", "물", "물"], ["대파"]])
def test_snapshot_mismatch_cannot_change_run_or_attempt_files(tmp_path, replacement):
    snapshot = StaplesSnapshot(["소금", "물"])
    value, metadata = artifacts(snapshot)
    store = StaplesRunStore(tmp_path, value.run_id, snapshot=snapshot)
    reference = store.write_observation(value)
    store.write_metadata(metadata)
    observation_bytes = (store.root / reference).read_bytes()
    metadata_bytes = (store.root / "metadata.json").read_bytes()
    value.input.effective_assumed_staples = replacement
    value.execution_attempt = 2
    with pytest.raises(ValueError, match="run snapshot"):
        store.write_observation(value)
    metadata.effective_assumed_staples = replacement
    with pytest.raises(ValueError, match="run snapshot"):
        store.write_metadata(metadata)
    assert (store.root / reference).read_bytes() == observation_bytes
    assert (store.root / "metadata.json").read_bytes() == metadata_bytes
    assert len(list(store.root.rglob("attempt-*.json"))) == 1


def test_input_snapshot_uses_the_same_production_availability_as_reviser():
    snapshot = StaplesSnapshot(["소금", "물"])
    production = RecipeNames.load(staples=frozenset(snapshot.names))
    value, _ = artifacts(snapshot)
    recipe = SourceRecipe.model_validate(value.input.original_recipe.model_dump())
    supplied = ["밥", "소금"]
    actual = snapshot.input_snapshot(recipe, "Fixture Rice", supplied)
    reviser = Reviser(snapshot.catalog(), snapshot.index, None, None)
    assert actual.availability == reviser.availability(recipe, supplied)
    assert actual.availability == [
        production.status(row.name, production.owned(supplied)) for row in recipe.ingredients
    ]
    # Preserve production's owned-before-assumed rule, including explicit staples.
    assert actual.availability == ["owned", "unavailable", "owned"]
    supplied.clear()
    recipe.ingredients[0].name = "changed after capture"
    assert actual.supplied_ingredients == ["밥", "소금"]
    assert actual.original_recipe.ingredients[0].name == "밥"


def test_redaction_cannot_silently_rewrite_the_effective_policy(tmp_path):
    snapshot = StaplesSnapshot(["소금", "물"])
    with pytest.raises(ValueError, match="redaction would change"):
        StaplesRunStore(tmp_path, "test-run", snapshot=snapshot, secrets=("소금",))
    assert list(tmp_path.iterdir()) == []


def test_empty_secrets_retain_the_existing_store_redaction_behavior(tmp_path):
    snapshot = StaplesSnapshot(["소금", "물"])
    store = StaplesRunStore(tmp_path, "test-run", snapshot=snapshot, secrets=("",))
    assert store.snapshot.names == ("소금", "물")
