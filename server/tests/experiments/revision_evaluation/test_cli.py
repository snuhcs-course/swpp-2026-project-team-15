# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Prove offline CLI defaults cannot send requests, construct models or publish runs."""

import json
import runpy
import socket
import sys

import httpx
import pytest
from experiments.revision_evaluation import cli
from experiments.revision_evaluation.persistence import RunStore

from app.dishes.http import RETRY_WAITS
from app.dishes.llm import DishLLM
from tests.experiments.revision_evaluation.test_compatibility import compatible_run


@pytest.fixture(autouse=True)
def offline_guard(monkeypatch, tmp_path):
    """Guard real connection entry points without replacing the socket class."""

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "offline command attempted networking, model construction or publication"
        )

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(httpx.Client, "send", forbidden)
    monkeypatch.setattr(httpx.AsyncClient, "send", forbidden)
    monkeypatch.setattr(DishLLM, "__init__", forbidden)
    monkeypatch.setattr(RunStore, "__init__", forbidden)
    monkeypatch.setenv("OPENROUTER_API_KEY", "private-configured-key")
    monkeypatch.chdir(tmp_path)


def test_default_invocation_is_offline_and_prints_single_pass_bounds(capsys, tmp_path):
    assert cli.main([]) == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["mode"] == "dry_run"
    assert data["fixture_observations_validated"] == 9
    assert data["network_requests_sent"] == 0
    assert len(data["plan"]) == 36
    assert data["planned_bounds"]["logical_calls"] == {"minimum": 0, "maximum": 72}
    assert data["planned_bounds"]["http_attempts"] == {
        "minimum": 0,
        "maximum": 72 * (1 + len(RETRY_WAITS)),
    }
    assert not data["planned_bounds"]["enforced_budget"]
    assert "private-configured-key" not in captured.out + captured.err
    assert not list(tmp_path.iterdir())


def test_selected_case_order_repetitions_and_bounds(capsys):
    assert cli.main(["--cases", "R02a", "R01a", "--repetitions", "3"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["plan"] == [
        {"case_id": case_id, "repetition": repetition}
        for case_id in ("R02a", "R01a")
        for repetition in (1, 2, 3)
    ]
    assert data["planned_bounds"]["logical_calls"]["maximum"] == 12
    assert data["planned_bounds"]["http_attempts"]["maximum"] == 12 * (1 + len(RETRY_WAITS))


def test_validation_only_does_not_load_plan_configuration(monkeypatch, capsys):
    def unexpected(*args, **kwargs):
        raise AssertionError("fixture-only validation must not build a plan")

    monkeypatch.setattr(cli, "load_manifest", unexpected)
    monkeypatch.setattr(cli, "StaplesSnapshot", unexpected)
    assert cli.main(["--validate-fixtures"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["mode"] == "fixture_validation"
    assert data["fixture_observations_validated"] == 9
    assert "plan" not in data


@pytest.mark.parametrize(
    "args",
    [
        ["--cases", "unknown"],
        ["--cases", "R01a", "R01a"],
        ["--cases", ""],
        ["--repetitions", "0"],
        ["--repetitions", "-1"],
        ["--manifest", "missing.json"],
        ["--recipes", "missing.json"],
    ],
)
def test_invalid_plan_returns_fixed_diagnostic_without_writes(args, capsys, tmp_path):
    assert cli.main(args) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == "offline plan validation failed\n"
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "args",
    [
        ["--cases"],
        ["--repetitions", "private-value"],
        ["--allow-live-api", "--validate-fixtures"],
        ["--resume", "private-value", "--validate-fixtures"],
    ],
)
def test_invalid_or_unimplemented_options_fail_closed(args, capsys):
    with pytest.raises(SystemExit) as exit_info:
        cli.main(args)
    assert exit_info.value.code == 2
    output = capsys.readouterr()
    assert output.err == "invalid command-line arguments; use --help\n"
    assert output.out == ""


def test_bad_fixture_fails_before_any_plan_loading(monkeypatch, capsys):
    def unexpected(*args, **kwargs):
        raise AssertionError("plan should not load after fixture failure")

    monkeypatch.setattr(cli, "load_manifest", unexpected)
    assert cli.main(["--fixture-root", "missing-fixture"]) == 2
    assert capsys.readouterr().err == "contract fixture validation failed\n"


def test_model_or_config_exceptions_do_not_leak(monkeypatch, capsys):
    def fail(*args, **kwargs):
        raise ValueError("private-configured-key private-file-content")

    monkeypatch.setattr(cli, "load_manifest", fail)
    assert cli.main([]) == 2
    output = capsys.readouterr()
    assert output.err == "offline plan validation failed\n"


def test_module_entry_point_is_offline(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["revision_evaluation", "--validate-fixtures"])
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_module("experiments.revision_evaluation", run_name="__main__")
    assert exit_info.value.code == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "fixture_validation"


def test_help_requires_no_fixture_or_plan_load(monkeypatch, capsys):
    def unexpected(*args, **kwargs):
        raise AssertionError("help must not load any artifacts")

    monkeypatch.setattr(cli, "validate_fixture_bundle", unexpected)
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--help"])
    assert exit_info.value.code == 0
    assert "--validate-fixtures" in capsys.readouterr().out


@pytest.mark.parametrize(
    "change",
    [
        None,
        "plan_order",
        "repetitions",
        "model",
        "pricing",
        "code",
        "prompt",
        "completed",
        "schema",
    ],
)
def test_resume_cli_checks_compatibility_without_mutating_existing_run(
    tmp_path, monkeypatch, capsys, change
):
    metadata, _, identities, code = compatible_run()
    root = tmp_path / "existing-run"
    root.mkdir()
    if change == "model":
        metadata.model["id"] = "changed model"
    elif change == "pricing":
        metadata.pricing["input_per_million_usd"] = 99
    elif change == "completed":
        metadata.state = "completed"
    elif change == "schema":
        metadata.artifact_schema = "unsupported/v2"
    (root / "metadata.json").write_text(metadata.model_dump_json(), encoding="utf-8")
    (root / "earlier-attempt.json").write_bytes(b"earlier evidence must remain untouched")
    before = {path: path.read_bytes() for path in root.iterdir()}
    if change == "code":
        code.tree = "c" * 40
    if change == "prompt":
        identities.prompt_sha256 = "0" * 64
        monkeypatch.setattr(cli, "capture_input_identities", lambda *args: identities)
    monkeypatch.setattr(cli, "capture_code_identity", lambda: code)
    args = ["--resume", str(root)]
    if change == "plan_order":
        args += ["--cases", "R01a", "R02a"]
    elif change == "repetitions":
        args += ["--repetitions", "3"]
    status = cli.main(args)
    output = capsys.readouterr()
    if change is None:
        assert status == 0
        data = json.loads(output.out)
        assert data["mode"] == "resume_compatibility_check"
        assert data["compatible"] and not data["execution_resumed"]
        assert len(data["plan"]) == 4
    else:
        assert status == 2
        assert output.out == ""
        assert output.err == "resume compatibility check failed\n"
    assert {path: path.read_bytes() for path in root.iterdir()} == before


def test_missing_resume_run_does_not_create_a_directory(tmp_path, capsys):
    root = tmp_path / "does-not-exist"
    assert cli.main(["--resume", str(root)]) == 2
    assert capsys.readouterr().err == "resume compatibility check failed\n"
    assert not root.exists()


def test_live_start_dispatches_only_after_explicit_authorization(monkeypatch, capsys, tmp_path):
    from experiments.revision_evaluation.contract import RunSummary
    from experiments.revision_evaluation.generate_contract import (
        fixture_observations,
        fixture_summary,
    )

    summary = RunSummary.model_validate(fixture_summary(fixture_observations()))
    summary.run_id = "dispatch-run"
    calls = []

    def prepare(run_id, plan, settings, **kwargs):
        assert run_id == "dispatch-run" and settings.maximum == 2
        assert settings.model_id == "fixture/model"
        assert settings.pricing_metadata() == {
            "input_per_million_usd": 0.1,
            "output_per_million_usd": 0.4,
        }
        return summary  # Opaque sentinel: dispatch must forward it unchanged.

    def execute(plan, metadata, **kwargs):
        assert metadata is summary and kwargs["allow_live_api"] is True
        assert kwargs["parent"] == tmp_path
        calls.append(plan)
        return summary

    monkeypatch.setattr(cli, "prepare_metadata", prepare)
    monkeypatch.setattr(cli, "run_new", execute)
    assert (
        cli.main(
            [
                "--allow-live-api",
                "--run-id",
                "dispatch-run",
                "--output-parent",
                str(tmp_path),
                "--max-http-attempts",
                "2",
                "--model",
                "fixture/model",
                "--input-per-million-usd",
                "0.1",
                "--output-per-million-usd",
                "0.4",
            ]
        )
        == 0
    )
    output = capsys.readouterr()
    data = json.loads(output.out)
    assert data["mode"] == "live_start" and len(calls) == 1
    assert data["http_attempts_cumulative"] == summary.totals.http_attempts
    assert data["output_directory"] == str((tmp_path / "dispatch-run").resolve())
    assert "network_requests_sent" not in data
    assert "private-configured-key" not in output.out + output.err
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "options",
    [
        [],
        ["--max-http-attempts", "0"],
        ["--max-http-attempts", "-1"],
        ["--max-http-attempts", "1", "--input-per-million-usd", "1"],
        [
            "--max-http-attempts",
            "1",
            "--input-per-million-usd",
            "nan",
            "--output-per-million-usd",
            "0",
        ],
    ],
)
def test_live_preflight_rejects_invalid_settings_without_writes(options, capsys, tmp_path):
    assert cli.main(["--allow-live-api", *options]) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == "live configuration or budget validation failed\n"
    assert not list(tmp_path.iterdir())


def test_live_preflight_requires_configured_key(monkeypatch, capsys):
    monkeypatch.delenv("OPENROUTER_API_KEY")
    assert cli.main(["--allow-live-api", "--max-http-attempts", "1"]) == 2
    assert capsys.readouterr().err == "live configuration or budget validation failed\n"


@pytest.mark.parametrize("override", [None, "same", "changed", "exhausted"])
def test_live_resume_preserves_cap_and_delegates_exhaustion_to_runner(
    tmp_path, monkeypatch, capsys, override
):
    from experiments.revision_evaluation.compatibility import compatibility_fingerprint
    from experiments.revision_evaluation.contract import RunSummary
    from experiments.revision_evaluation.generate_contract import (
        fixture_observations,
        fixture_summary,
    )

    metadata, _, _, code = compatible_run()
    if override == "exhausted":
        metadata.http_attempt_budget.maximum = 1
        metadata.http_attempt_budget.remaining = 1
        metadata.compatibility_fingerprint = compatibility_fingerprint(metadata)
    root = tmp_path / "existing"
    root.mkdir()
    (root / "metadata.json").write_text(metadata.model_dump_json(), encoding="utf-8")
    # The durable intent may precede the next metadata publication after a crash.
    raw = fixture_observations()["resumed__r03/attempt-001.json"]
    raw.update(run_id=metadata.run_id, case_id="R02a", repetition=1)
    directory = root / "observations" / "R02a__r01"
    directory.mkdir(parents=True)
    (directory / "attempt-001.json").write_text(json.dumps(raw), encoding="utf-8")
    before = {path: path.read_bytes() for path in root.rglob("*.json")}
    monkeypatch.setattr(cli, "capture_code_identity", lambda: code)
    calls = []
    summary = RunSummary.model_validate(fixture_summary(fixture_observations()))

    def resume(directory, plan, identities, current_code, **kwargs):
        from experiments.revision_evaluation.budgeting import BudgetExceeded

        assert directory == root and current_code == code
        assert kwargs["allow_live_api"] is True
        calls.append(plan)
        if override == "exhausted":
            assert kwargs["settings"].maximum == 1
            raise BudgetExceeded("HTTP-attempt budget exhausted")
        assert kwargs["settings"].maximum == 20
        return summary

    monkeypatch.setattr(cli, "run_resume", resume)
    args = ["--resume", str(root), "--allow-live-api"]
    if override in ("same", "changed"):
        args += ["--max-http-attempts", "20" if override == "same" else "21"]
    status = cli.main(args)
    output = capsys.readouterr()
    if override in ("changed", "exhausted"):
        assert status == 2 and output.out == ""
        assert output.err == "live configuration or budget validation failed\n"
        assert len(calls) == (1 if override == "exhausted" else 0)
    else:
        assert status == 0
        data = json.loads(output.out)
        assert data["mode"] == "live_resume" and len(calls) == 1
        assert data["http_attempts_cumulative"] == summary.totals.http_attempts
    assert {path: path.read_bytes() for path in root.rglob("*.json")} == before


@pytest.mark.parametrize(
    "args",
    [
        ["--run-id", "private-value"],
        ["--output-parent", "private-path"],
        ["--resume", "existing", "--allow-live-api", "--run-id", "another"],
    ],
)
def test_new_output_settings_cannot_enable_execution_or_redirect_resume(args, capsys, tmp_path):
    with pytest.raises(SystemExit) as captured:
        cli.main(args)
    assert captured.value.code == 2
    assert capsys.readouterr().err == "invalid command-line arguments; use --help\n"
    assert not list(tmp_path.iterdir())
