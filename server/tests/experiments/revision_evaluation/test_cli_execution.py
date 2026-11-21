# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Exercise CLI dispatch through real persistence and Revision, with mock HTTP only."""

import json
import socket

import httpx
import pytest
from experiments.revision_evaluation import cli, compatibility, provenance, runner
from experiments.revision_evaluation.contract import Observation, RunMetadata, RunSummary

from tests.experiments.revision_evaluation.test_provenance import KEY, local_source
from tests.experiments.revision_evaluation.test_runner import answer, setup
from tests.experiments.revision_evaluation.test_runner import no_network as no_network


@pytest.fixture
def command(tmp_path, monkeypatch):
    """Keep real CLI/runner policy; substitute only source location and HTTP transport."""
    plan, _, kwargs = setup()
    paths = local_source(tmp_path, plan, kwargs["recipes"])
    capture = compatibility.capture_code_identity
    monkeypatch.setattr(
        provenance, "capture_code_identity", lambda root: capture(paths["repository_root"])
    )
    monkeypatch.setattr(cli, "capture_code_identity", lambda: capture(paths["repository_root"]))
    monkeypatch.setattr(cli, "StaplesSnapshot", lambda: kwargs["snapshot"])

    def forbidden(*args, **kwargs):
        raise AssertionError("real DNS/network access is forbidden")

    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    sends = []
    replies = [answer, answer, answer]

    def handle(request):
        sends.append(request)
        return replies.pop(0)()

    for name in ("run_new", "run_resume"):
        execute = getattr(runner, name)

        def dispatch(*args, _execute=execute, **kw):
            return _execute(*args, transport_factory=lambda: httpx.MockTransport(handle), **kw)

        monkeypatch.setattr(cli, name, dispatch)
    source = ["--manifest", str(paths["manifest_path"]), "--recipes", str(paths["recipes_path"])]
    root = tmp_path / "runs" / "cli-run"
    start = [
        *source,
        "--allow-live-api",
        "--max-http-attempts",
        "20",
        "--model",
        "fixture/model",
        "--run-id",
        root.name,
        "--output-parent",
        str(root.parent),
        "--cases",
        "runner-case",
        "--repetitions",
        "3",
        "--input-per-million-usd",
        "0.1",
        "--output-per-million-usd",
        "0.4",
    ]
    resume = [*source, "--resume", str(root)]
    return root, start, resume, sends, replies, paths


def saved(root):
    """Validate every published artifact before inspecting execution behavior."""
    metadata = RunMetadata.model_validate_json((root / "metadata.json").read_text(encoding="utf-8"))
    summary = RunSummary.model_validate_json((root / "summary.json").read_text(encoding="utf-8"))
    observations = [
        Observation.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(root.glob("observations/*/*.json"))
    ]
    assert all(KEY not in path.read_text(encoding="utf-8") for path in root.rglob("*.json"))
    return metadata, summary, observations


def test_live_start_publishes_real_artifacts_and_never_overwrites_a_run(command, capsys):
    root, start, _, sends, _, _ = command
    assert cli.main(start) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["mode"] == "live_start" and output["complete"]
    assert output["http_attempts_cumulative"] == 3 and len(sends) == 3
    assert "network_requests_sent" not in output
    metadata, summary, observations = saved(root)
    assert metadata.state == "completed" and summary.complete
    assert len(observations) == 3 and summary.totals.completed_repetitions == 3
    assert metadata.model["id"] == "fixture/model"
    assert metadata.pricing["input_per_million_usd"] == 0.1
    before = {path: path.read_bytes() for path in root.rglob("*.json")}
    assert cli.main(start) == 2
    assert capsys.readouterr().err == "evaluation execution failed\n"
    assert len(sends) == 3 and before == {path: path.read_bytes() for path in before}


def test_interruption_readonly_check_and_live_resume_preserve_old_attempts(command, capsys):
    root, start, resume, sends, replies, _ = command

    def interrupt():
        raise KeyboardInterrupt

    replies[-1] = interrupt
    assert cli.main(start) == 130
    assert capsys.readouterr().err == "evaluation execution interrupted\n"
    metadata, summary, observations = saved(root)
    assert metadata.state == "interrupted" and not summary.complete
    assert len(observations) == 3 and summary.totals.completed_repetitions == 2
    assert observations[-1].model_calls[0].http_attempts[0].state == "request_prepared"
    before = {path: path.read_bytes() for path in root.rglob("*.json")}
    assert cli.main(resume) == 0
    assert json.loads(capsys.readouterr().out)["execution_resumed"] is False
    assert len(sends) == 3 and before == {path: path.read_bytes() for path in before}

    replies.append(answer)
    assert cli.main([*resume, "--allow-live-api"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["mode"] == "live_resume" and output["http_attempts_cumulative"] == 4
    assert len(sends) == 4
    metadata, summary, observations = saved(root)
    assert metadata.state == "completed" and summary.complete
    assert len(metadata.resume_history) == 1 and len(observations) == 4
    assert observations[-1].execution_attempt == 2
    assert summary.totals.cost_usd.value is None
    assert summary.totals.cost_usd.confirmed_subtotal == pytest.approx(0.03)
    assert all(
        path.read_bytes() == value for path, value in before.items() if "observations" in path.parts
    )


def test_exhausted_budget_blocks_retry_and_cannot_be_reset_on_resume(command, capsys):
    root, start, resume, sends, replies, _ = command
    start[start.index("--max-http-attempts") + 1] = "1"
    replies[0] = lambda: httpx.Response(429)
    assert cli.main(start) == 2
    assert capsys.readouterr().err == "evaluation execution failed\n"
    metadata, summary, _ = saved(root)
    assert len(sends) == 1 and metadata.http_attempt_budget.consumed == 1
    assert summary.totals.http_429_responses == 1 and summary.totals.http_429_retries == 0
    before = {path: path.read_bytes() for path in root.rglob("*.json")}
    for extra in ([], ["--max-http-attempts", "2"]):
        assert cli.main([*resume, "--allow-live-api", *extra]) == 2
        assert capsys.readouterr().err == "live configuration or budget validation failed\n"
    assert len(sends) == 1 and before == {path: path.read_bytes() for path in before}


def test_changed_source_rejects_resume_without_any_request_or_write(command, capsys):
    root, start, resume, sends, replies, paths = command

    def interrupt():
        raise KeyboardInterrupt

    replies[0] = interrupt
    assert cli.main(start) == 130
    capsys.readouterr()
    before = {path: path.read_bytes() for path in root.rglob("*.json")}
    manifest = paths["manifest_path"]
    manifest.write_text(manifest.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert cli.main([*resume, "--allow-live-api"]) == 2
    assert capsys.readouterr().err == "resume compatibility check failed\n"
    assert len(sends) == 1 and before == {path: path.read_bytes() for path in before}
