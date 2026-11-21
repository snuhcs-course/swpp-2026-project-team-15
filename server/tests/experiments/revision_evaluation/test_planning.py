# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Offline explicit-plan tests using the unchanged frozen 36-case manifest."""

import json
from copy import deepcopy

import pytest
from experiments.revision_evaluation.contract import RunMetadata
from experiments.revision_evaluation.generate_contract import fixture_metadata, fixture_observations
from experiments.revision_evaluation.planning import (
    FROZEN_MANIFEST,
    build_plan,
    load_manifest,
    publish_plan,
)
from experiments.revision_evaluation.staples import StaplesRunStore, StaplesSnapshot

from app.dishes.llm import DishLLM
from app.dishes.recipes import RecipeStore


@pytest.fixture
def context(monkeypatch):
    """Use real local fixtures while making any model construction a test failure."""

    def forbidden(*args, **kwargs):
        raise AssertionError("planning must not construct a model")

    monkeypatch.setattr(DishLLM, "__init__", forbidden)
    snapshot = StaplesSnapshot(["소금", "물", "소금"])
    return {
        "manifest": load_manifest(),
        "snapshot": snapshot,
        "catalog": snapshot.catalog(),
        "recipes": RecipeStore.load(FROZEN_MANIFEST.with_name("fixtures.json")),
    }


def fresh_metadata():
    """Use fixture identities only in tests; planning does not fabricate identities."""
    value = fixture_metadata(fixture_observations())
    value.update(plan=[], state="running", resume_history=[])
    value["http_attempt_budget"].update(
        consumed=0, remaining=value["http_attempt_budget"]["maximum"]
    )
    return RunMetadata.model_validate(value)


def test_frozen_cases_labels_and_selection_order_are_preserved(context):
    manifest = context.pop("manifest")
    raw = json.loads(FROZEN_MANIFEST.read_text(encoding="utf-8"))
    assert len(manifest) == 36
    assert [case.model_dump() for case in manifest] == raw["cases"]
    before = deepcopy(manifest)
    selected = [manifest[-1].id, manifest[0].id]
    plan = build_plan(manifest, selected, 3, **context)
    assert [(unit.case_id, unit.repetition) for unit in plan.units] == [
        (case_id, repetition) for case_id in selected for repetition in (1, 2, 3)
    ]
    assert list(plan.inputs) == selected
    assert all(
        unit.state == "not_started" and unit.cumulative_telemetry is None for unit in plan.units
    )
    assert manifest == before
    assert plan.effective_assumed_staples == ("소금", "물")
    source = context["recipes"].get(manifest[0].dish_id)
    assert (
        plan.inputs[manifest[0].id].original_recipe.ingredients[0].name
        == source.ingredients[0].name
    )
    plan.inputs[manifest[0].id].supplied_ingredients.append("detached")
    assert manifest == before


def test_every_frozen_case_is_planned_without_filtering(context):
    manifest = context.pop("manifest")
    plan = build_plan(manifest, [case.id for case in manifest], 2, **context)
    assert len(plan.units) == 72
    assert len(plan.inputs) == 36
    assert {unit.case_id for unit in plan.units} == {case.id for case in manifest}


@pytest.mark.parametrize("selection", [[], ["unknown"], ["R01a", "R01a"], "R01a", [1]])
def test_bad_selection_fails_before_input_resolution(context, selection):
    manifest = context.pop("manifest")

    class ForbiddenInputs:
        def get(self, dish_id):
            raise AssertionError("invalid selection must fail before input lookup")

    context["recipes"] = context["catalog"] = ForbiddenInputs()
    with pytest.raises(ValueError):
        build_plan(manifest, selection, 1, **context)


@pytest.mark.parametrize("repetitions", [0, -1, True, 1.5, "2"])
def test_invalid_repetition_count_is_not_coerced(context, repetitions):
    manifest = context.pop("manifest")
    with pytest.raises(ValueError, match="positive integer"):
        build_plan(manifest, [manifest[0].id], repetitions, **context)


@pytest.mark.parametrize(
    "invalid",
    [
        {},
        {"schema": 2, "cases": []},
        {"schema": True, "cases": []},
        {"schema": 1, "cases": []},
        {"schema": 1, "cases": [None]},
        {"schema": 1, "cases": [{"id": "x", "dish_id": "dish", "ingredients": [1]}]},
        {"schema": 1, "cases": [{"id": "x", "dish_id": "dish", "ingredients": []}] * 2},
    ],
)
def test_invalid_manifest_is_rejected_without_echoing_content(tmp_path, invalid):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(invalid), encoding="utf-8")
    with pytest.raises(ValueError, match="^manifest must contain unique valid schema-1 cases$"):
        load_manifest(path)


def test_empty_fridge_and_annotations_are_not_relabelled(context):
    manifest = context.pop("manifest")
    manifest[0].ingredients = []
    manifest[0].expect = "original-label"
    plan = build_plan(manifest, [manifest[0].id], 1, **context)
    assert plan.inputs[manifest[0].id].supplied_ingredients == []
    assert manifest[0].expect == "original-label"


def test_missing_recipe_or_catalog_entry_is_not_silently_skipped(context):
    manifest = context.pop("manifest")
    manifest[0].dish_id = "unknown-dish"
    with pytest.raises(ValueError, match="source recipe or catalog"):
        build_plan(manifest, [manifest[0].id], 1, **context)


def test_initial_plan_and_exact_staples_are_persisted_without_mutating_inputs(tmp_path, context):
    manifest = context.pop("manifest")
    plan = build_plan(manifest, [manifest[0].id], 2, **context)
    metadata = fresh_metadata()
    before = metadata.model_dump()
    store = StaplesRunStore(tmp_path, metadata.run_id, snapshot=context["snapshot"])
    published = publish_plan(plan, store, metadata)
    saved = RunMetadata.model_validate_json(
        (store.root / "metadata.json").read_text(encoding="utf-8")
    )
    assert saved == published
    assert len(saved.plan) == 2
    assert saved.effective_assumed_staples == ["소금", "물"]
    assert metadata.model_dump() == before
    assert published.plan[0] is not plan.units[0]
    before_bytes = (store.root / "metadata.json").read_bytes()
    with pytest.raises(ValueError, match="fresh unstarted"):
        publish_plan(plan, store, published)
    # Even the caller's unchanged, empty template cannot reset an existing run.
    with pytest.raises(ValueError, match="fresh unstarted"):
        publish_plan(plan, store, metadata)
    assert (store.root / "metadata.json").read_bytes() == before_bytes


@pytest.mark.parametrize("content", [None, "{invalid JSON", "[]"])
def test_unreadable_or_malformed_manifest_uses_fixed_error(tmp_path, content):
    path = tmp_path / "cases.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="^manifest must contain unique valid schema-1 cases$"):
        load_manifest(path)


def test_plan_cannot_be_published_under_another_staples_policy(tmp_path, context):
    manifest = context.pop("manifest")
    plan = build_plan(manifest, [manifest[0].id], 1, **context)
    metadata = fresh_metadata()
    store = StaplesRunStore(tmp_path, metadata.run_id, snapshot=StaplesSnapshot([]))
    with pytest.raises(ValueError, match="effective staples snapshot"):
        publish_plan(plan, store, metadata)
    assert not (store.root / "metadata.json").exists()
