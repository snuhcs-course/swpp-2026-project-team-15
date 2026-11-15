# AI-assisted with Codex, 2026-11-14; reviewed by Soohyun An
# Test reorganization assisted by Codex, 2026-11-15; reviewed by Soohyun An
"""Approved category-at-a-time contracts, written before implementation."""

import json

import pytest
from typer.testing import CliRunner

from crawlers.tenkrecipes import fetching, workflow
from crawlers.tenkrecipes.cli import app
from crawlers.tenkrecipes.tests.support_http import FakeResponse
from crawlers.tenkrecipes.tests.support_runs import scripted_run
from crawlers.tenkrecipes.workflow import CollectionRun


def test_cli_accumulates_100_then_90_in_one_run_without_crossing_scope(tmp_path, monkeypatch):
    first = [str(950000 + i) for i in range(100)]
    second = [str(960000 + i) for i in range(90)]
    run, options, calls = scripted_run(
        tmp_path,
        {("63", 1): first[:60], ("63", 2): first[60:], ("56", 1): [first[0], *second]},
    )
    monkeypatch.setattr(fetching, "HttpClient", lambda **kwargs: options["client"])
    monkeypatch.setattr(workflow, "ImageDownloader", lambda client: options["image_downloader"])
    runner = CliRunner()
    base = ["resume", "--output-dir", str(run.storage.root), "--live"]
    identity = run.storage.path("run.json").read_bytes()
    result = runner.invoke(app, [*base, "--only-category", "63"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["requested_category"] == "63" and payload["category_complete"] is True
    assert payload["acquisition_complete"] is False and payload["selected_count"] == 100
    assert not any("cat4=56" in url for url in calls)
    first_manifest = run.storage.read_json("manifest.json")
    assert first_manifest["quota_category"] == "63"
    old_files = {
        row["path"]: run.storage.path(row["path"]).read_bytes()
        for row in first_manifest["images"].values()
    }
    calls_before = list(calls)
    again = runner.invoke(app, base)
    assert again.exit_code == 0, again.output
    assert json.loads(again.stdout)["requested_category"] == "63"
    assert calls == calls_before

    result = runner.invoke(app, [*base, "--only-category", "56"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["requested_category"] == "56" and payload["category_complete"] is True
    assert payload["selected_count"] == 190 and payload["acquisition_complete"] is False
    assert not any("cat4=54" in url for url in calls)
    assert run.storage.path("run.json").read_bytes() == identity
    manifest = run.storage.read_json("manifest.json")
    assert [row["source_id"] for row in manifest["allocations"]] == [*first, *second]
    assert len({row["source_id"] for row in manifest["allocations"]}) == 190
    assert all(run.storage.path(path).read_bytes() == body for path, body in old_files.items())
    assert calls.count(f"https://www.10000recipe.com/recipe/{first[0]}") == 1
    assert calls.count(f"https://recipe1.ezmember.co.kr/{first[0]}.png") == 1
    assert len([row for row in manifest["candidates"] if row["source_id"] == first[0]]) == 2


@pytest.mark.parametrize("code", ["unknown", "56"])
def test_api_rejects_invalid_scope_or_unfinished_predecessor_without_mutation(tmp_path, code):
    run, _, calls = scripted_run(tmp_path, {})
    before = run.storage.path("manifest.json").read_bytes()
    with pytest.raises(ValueError):
        run.collect_quotas(category_code=code)
    assert calls == []
    assert run.storage.path("manifest.json").read_bytes() == before


@pytest.mark.parametrize(
    "command,extra",
    [
        ("collect", ["--full", "--only-category", "63"]),
        ("resume", ["--full", "--only-category", "63"]),
        ("collect", ["--only-category", "unknown"]),
        ("resume", ["--only-category", "unknown"]),
        ("collect", ["--only-category", "63", "--page", "2"]),
        ("collect", ["--only-category", "63", "--category", "56"]),
        ("collect", ["--only-category", "56"]),
    ],
)
def test_cli_rejects_bad_scope_before_network_or_directory_creation(
    run_tool, tmp_path, command, extra
):
    output = tmp_path / "invalid-run"
    result = run_tool(command, "--output-dir", str(output), "--live", *extra)
    assert result.returncode != 0
    assert "No such option" not in result.stderr
    assert "FORBIDDEN_IO" not in result.stderr
    assert not output.exists()


@pytest.mark.parametrize("stop", ["exhausted", "blocked", "deferred"])
def test_scoped_shortfall_or_stop_remains_nonzero_without_next_category(
    tmp_path, monkeypatch, stop
):
    page = (
        []
        if stop == "exhausted"
        else FakeResponse(403 if stop == "blocked" else 429, headers={"Retry-After": "999999"})
    )
    run, options, calls = scripted_run(tmp_path, {("63", 1): page})
    monkeypatch.setattr(fetching, "HttpClient", lambda **kwargs: options["client"])
    result = CliRunner().invoke(
        app, ["resume", "--output-dir", str(run.storage.root), "--live", "--only-category", "63"]
    )
    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    assert payload["requested_category"] == "63" and payload["category_complete"] is False
    assert payload["acquisition_complete"] is False
    assert len(calls) == 1 and "cat4=63" in calls[0]
    assert run.storage.read_json("manifest.json")["quota_category"] == "63"


def test_exhausted_predecessor_allows_next_scope_and_full_explicitly_clears_scope(tmp_path):
    run, options, calls = scripted_run(tmp_path, {("56", 1): ["970001"]})
    result = run.collect_quotas(category_code="63")
    assert result["category_complete"] is False
    resumed = CollectionRun.resume(**options)
    result = resumed.collect_quotas(category_code="56")
    assert result["requested_category"] == "56"
    assert resumed.snapshot()["allocations"] == [dict(source_id="970001", category_code="56")]
    assert not any("cat4=54" in url for url in calls)
    result = resumed.collect_quotas()
    assert any("cat4=54" in url for url in calls)
    assert not resumed.snapshot().get("quota_category")


def test_category_execution_does_not_repair_another_category_asset(tmp_path):
    run, _, calls = scripted_run(tmp_path, {("63", 1): ["980001"]})
    run.collect_quotas(category_code="63")
    image = run.storage.path(run.snapshot()["images"]["980001"]["path"])
    image.unlink()
    calls.clear()
    result = run.collect_quotas(category_code="56")
    assert result["requested_category"] == "56"
    assert not image.exists()
    assert not any(url.endswith("980001.png") for url in calls)


def test_collect_category_mode_and_plain_resume_keep_scope(tmp_path, monkeypatch):
    run, options, calls = scripted_run(tmp_path / "transport", {})
    monkeypatch.setattr(fetching, "HttpClient", lambda **kwargs: options["client"])
    output = tmp_path / "new-run"
    runner = CliRunner()
    result = runner.invoke(
        app, ["collect", "--output-dir", str(output), "--live", "--only-category", "63"]
    )
    assert result.exit_code == 1, result.output
    assert json.loads(result.stdout)["requested_category"] == "63"
    calls_before = list(calls)
    result = runner.invoke(app, ["resume", "--output-dir", str(output), "--live"])
    assert result.exit_code == 1, result.output
    assert json.loads(result.stdout)["requested_category"] == "63"
    assert calls == calls_before
    assert run.snapshot()["allocations"] == []


def test_rejected_category_does_not_publish_a_pending_failure_checkpoint(tmp_path, monkeypatch):
    """An invalid scope must be rejected before resume performs recovery writes."""
    run, options, calls = scripted_run(tmp_path, {})
    before = run.storage.path("manifest.json").read_bytes()
    pending = run.snapshot()
    pending.update(state="failed", reason="synthetic interrupted checkpoint")
    run.storage.write_json("failure.pending.json", pending)
    monkeypatch.setattr(fetching, "HttpClient", lambda **kwargs: options["client"])
    result = CliRunner().invoke(
        app, ["resume", "--output-dir", str(run.storage.root), "--live", "--only-category", "56"]
    )
    assert result.exit_code == 1, result.output
    assert calls == []
    assert run.storage.path("manifest.json").read_bytes() == before
    assert run.storage.path("failure.pending.json").exists()
