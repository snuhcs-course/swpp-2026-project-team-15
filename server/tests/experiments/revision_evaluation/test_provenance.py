# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Real local provenance capture and credential-safe publication, with no live requests."""

import hashlib
import json
import traceback
from datetime import datetime
from pathlib import Path

import httpx
import pytest
from experiments.revision_evaluation import cli, runner
from experiments.revision_evaluation.compatibility import compatibility_fingerprint
from experiments.revision_evaluation.contract import Observation, RunMetadata, RunSummary
from experiments.revision_evaluation.generate_contract import (
    fixture_metadata,
    fixture_observations,
    fixture_summary,
)
from experiments.revision_evaluation.persistence import PersistenceError, RunStore
from experiments.revision_evaluation.provenance import prepare_metadata
from experiments.revision_evaluation.reporting import render_summary

from tests.experiments.revision_evaluation.test_compatibility import _git
from tests.experiments.revision_evaluation.test_runner import answer, artifacts, setup
from tests.experiments.revision_evaluation.test_runner import no_network as no_network

KEY = "runner-private-key"


def local_source(tmp_path, plan, recipes):
    """Commit disposable source inputs; ignored fake configuration is not an input."""
    root = tmp_path / "source"
    root.mkdir()
    manifest, source_recipes = root / "cases.json", root / "recipes.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": 1,
                "cases": [
                    {
                        "id": case,
                        "dish_id": value.dish_id,
                        "ingredients": value.supplied_ingredients,
                    }
                    for case, value in plan.inputs.items()
                ],
            }
        ),
        encoding="utf-8",
    )
    source_recipes.write_text(
        json.dumps(
            {
                "schema": 1,
                "recipes": {
                    value.dish_id: recipes.get(value.dish_id).model_dump()
                    for value in plan.inputs.values()
                },
            }
        ),
        encoding="utf-8",
    )
    (root / ".gitignore").write_text(".env\n", encoding="utf-8")
    (root / ".env").write_text(KEY, encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "config", "core.autocrlf", "false")
    _git(root, "add", ".")
    _git(
        root,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.test",
        "commit",
        "-qm",
        "fixture",
    )
    return dict(manifest_path=manifest, recipes_path=source_recipes, repository_root=root)


def test_real_provenance_is_persisted_and_ignored_config_is_never_read(tmp_path, monkeypatch):
    plan, _, kwargs = setup(repetitions=1)
    paths = local_source(tmp_path, plan, kwargs["recipes"])
    read_bytes, read_text = Path.read_bytes, Path.read_text

    def guarded_bytes(path):
        assert path.name != ".env", "configuration file must not be read"
        return read_bytes(path)

    def guarded_text(path, *args, **kwargs):
        assert path.name != ".env", "configuration file must not be read"
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", guarded_bytes)
    monkeypatch.setattr(Path, "read_text", guarded_text)
    metadata = prepare_metadata("runner-test", plan, kwargs["settings"], secrets=(KEY,), **paths)
    assert not metadata.code_identity.dirty
    assert (
        metadata.code_identity.commit
        == _git(paths["repository_root"], "rev-parse", "HEAD").decode()
    )
    assert (
        metadata.code_identity.tree
        == _git(paths["repository_root"], "rev-parse", "HEAD^{tree}").decode()
    )
    assert metadata.identities.fixture_sha256 == {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in (("manifest", paths["manifest_path"]), ("recipes", paths["recipes_path"]))
    }
    full = metadata.model_copy(deep=True)
    full.plan = list(plan.units)
    assert compatibility_fingerprint(full) == metadata.compatibility_fingerprint
    assert metadata.plan == [] and metadata.resume_history == []
    assert datetime.fromisoformat(metadata.created_at).utcoffset().total_seconds() == 0
    runner.run_new(
        plan,
        metadata,
        parent=tmp_path,
        transport_factory=lambda: httpx.MockTransport(lambda request: answer()),
        **kwargs,
    )
    saved, _, _ = artifacts(tmp_path)
    assert saved.code_identity == metadata.code_identity
    assert saved.identities == metadata.identities
    assert saved.model == metadata.model and saved.pricing == metadata.pricing
    assert KEY not in "".join(
        path.read_text(encoding="utf-8") for path in (tmp_path / "runner-test").rglob("*.json")
    )
    paths["manifest_path"].write_text(
        paths["manifest_path"].read_text(encoding="utf-8") + "\n", encoding="utf-8"
    )
    dirty = prepare_metadata("other", plan, kwargs["settings"], **paths)
    assert dirty.code_identity.dirty and dirty.code_identity.commit == metadata.code_identity.commit
    assert dirty.code_identity.tree != metadata.code_identity.tree
    assert dirty.identities.fixture_sha256 != metadata.identities.fixture_sha256


@pytest.mark.parametrize("location", ["input", "case", "request", "raw", "decoded", "check"])
def test_evidence_collision_is_rejected_before_any_temporary_write(tmp_path, location):
    store = RunStore(tmp_path, "test-run", secrets=(KEY,))
    value = Observation.model_validate(
        fixture_observations()["revised-after-reask-429__r01/attempt-001.json"]
    )
    value.run_id = "test-run"
    if location == "input":
        value.input.original_recipe.ingredients[0].name = KEY
    elif location == "case":
        value.case_id = KEY
    elif location == "request":
        value.model_calls[0].request.user = KEY
    elif location == "raw":
        value.model_calls[0].http_attempts[-1].safe_response_text = json.dumps({"tips": [KEY]})
    elif location == "decoded":
        value.model_calls[0].decoded_answer["tips"] = [KEY]
    else:
        value.checks[0].message = KEY
    with pytest.raises(PersistenceError, match="protected content"):
        store.write_observation(value)
    assert not list(store.root.rglob("*"))


def test_error_text_is_masked_without_modifying_the_caller_observation(tmp_path):
    store = RunStore(tmp_path, "test-run", secrets=(KEY,))
    value = Observation.model_validate(fixture_observations()["api-error__r01/attempt-001.json"])
    value.run_id = "test-run"
    value.execution.sanitized_error = f"error {KEY}"
    ref = store.write_observation(value)
    text = (store.root / ref).read_text(encoding="utf-8")
    assert KEY not in text and "[REDACTED]" in text
    assert value.execution.sanitized_error == f"error {KEY}"


def test_summary_json_and_markdown_guard_preserves_prior_files(tmp_path):
    store = RunStore(tmp_path, "test-run", secrets=(KEY,))
    summary = RunSummary.model_validate(fixture_summary(fixture_observations()))
    summary.run_id = "test-run"
    store.write_summary(summary, markdown=True)
    assert (store.root / "summary.md").read_text(encoding="utf-8") == render_summary(summary)
    before = {path: path.read_bytes() for path in store.root.iterdir()}
    summary.cases[0].case_id = KEY
    with pytest.raises(PersistenceError, match="protected content"):
        store.write_summary(summary, markdown=True)
    assert {path: path.read_bytes() for path in store.root.iterdir()} == before
    assert not list(store.root.rglob("*.tmp"))


def test_metadata_identity_and_run_name_are_not_silently_redacted(tmp_path):
    with pytest.raises(PersistenceError):
        RunStore(tmp_path, KEY, secrets=(KEY,))
    assert not list(tmp_path.iterdir())
    store = RunStore(tmp_path, "test-run", secrets=(KEY,))
    raw = fixture_metadata(fixture_observations())
    raw.update(run_id="test-run", plan=[])
    raw["identities"]["input_sha256"] = {KEY: "a" * 64}
    with pytest.raises(PersistenceError):
        store.write_metadata(RunMetadata.model_validate(raw))
    assert not list(store.root.iterdir())


def test_redaction_cannot_invalidate_a_real_metadata_fingerprint(tmp_path):
    store = RunStore(tmp_path, "test-run", secrets=(KEY,))
    raw = fixture_metadata(fixture_observations())
    raw.update(run_id="test-run", plan=[])
    value = RunMetadata.model_validate(raw)
    value.model["note"] = KEY
    value.compatibility_fingerprint = compatibility_fingerprint(value)
    with pytest.raises(PersistenceError):
        store.write_metadata(value)
    assert not list(store.root.iterdir())


def test_model_echoed_secret_stops_before_later_billing_and_leaves_no_private_artifact(tmp_path):
    from experiments.revision_evaluation.transport import CheckpointError

    from tests.dishes.test_revision import GOOD

    plan, metadata, kwargs = setup()
    sends = []

    def handle(request):
        sends.append(request)
        return answer({**GOOD, "tips": [KEY]})

    with pytest.raises(CheckpointError):
        runner.run_new(
            plan,
            metadata,
            parent=tmp_path,
            transport_factory=lambda: httpx.MockTransport(handle),
            **kwargs,
        )
    saved, summary, observations = artifacts(tmp_path)
    assert len(sends) == 1 and saved.state == "interrupted"
    assert summary.totals.completed_repetitions == 0
    assert observations[0].model_calls[0].http_attempts[0].state == "request_prepared"
    assert all(
        KEY not in path.read_text(encoding="utf-8")
        for path in (tmp_path / "runner-test").rglob("*.json")
    )


def test_runner_suppresses_secret_bearing_exception_but_keeps_ordinary_errors(tmp_path):
    plan, metadata, kwargs = setup(repetitions=1)

    def private_failure():
        raise RuntimeError(KEY)

    with pytest.raises(RuntimeError, match="evaluation execution failed") as captured:
        runner.run_new(plan, metadata, parent=tmp_path, transport_factory=private_failure, **kwargs)
    assert KEY not in "".join(traceback.format_exception(captured.value))
    assert captured.value.__suppress_context__
    assert all(
        KEY not in path.read_text(encoding="utf-8")
        for path in (tmp_path / "runner-test").rglob("*.json")
    )


def test_cli_unexpected_exception_uses_fixed_diagnostic(monkeypatch, capsys):
    def private_failure(*args, **kwargs):
        raise RuntimeError(KEY)

    monkeypatch.setattr(cli, "validate_fixture_bundle", private_failure)
    assert cli.main([]) == 2
    output = capsys.readouterr()
    assert output.out == "" and output.err == "evaluation command failed\n"


def test_prepare_rejects_identity_collision_before_source_reads(tmp_path, monkeypatch):
    plan, _, kwargs = setup()
    plan.inputs["runner-case"].supplied_ingredients.append(KEY)

    def forbidden(*args, **kwargs):
        raise AssertionError("unsafe identity reached capture")

    monkeypatch.setattr(
        "experiments.revision_evaluation.provenance.capture_input_identities", forbidden
    )
    with pytest.raises(PersistenceError):
        prepare_metadata("safe", plan, kwargs["settings"], secrets=(KEY,))
