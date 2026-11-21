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
        ["--allow-live-api"],
        ["--resume", "private-value"],
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
