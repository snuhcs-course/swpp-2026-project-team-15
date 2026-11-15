# AI-assisted with Codex, 2026-11-14; reviewed by Soohyun An
# Test reorganization assisted by Codex, 2026-11-15; reviewed by Soohyun An
"""Exercise the approved full pipeline using only synthetic transport responses."""

import csv
import json
from collections import Counter

import pytest
from typer.testing import CliRunner

from crawlers.tenkrecipes.cli import app
from crawlers.tenkrecipes.config import CATEGORIES
from crawlers.tenkrecipes.storage import digest
from crawlers.tenkrecipes.tests.support_runs import detail_html, scripted_run
from crawlers.tenkrecipes.workflow import CollectionRun


def test_full_pipeline_preserves_work_across_interruption_and_reports_quotas(tmp_path):
    """Collect real parser/storage outputs, resume an interrupted asset, then audit offline.

    Unlike the saved_collection report fixture, this input contains no prepared
    records or allocations. Production code must traverse all nine categories,
    reject an empty title, retain duplicate observations, and produce the report.
    The source deliberately gives every ID identical recipe/image content.
    """
    pages, expected, offset = {}, {}, 0
    for _, code, quota in CATEGORIES:
        ids = [str(940000 + i) for i in range(offset, offset + quota)]
        offset += quota
        expected[code] = ids
        candidates = ["939999", *ids] if code == "63" else ["940000", *ids]
        for start in range(0, len(candidates), 40):
            # Repeated observations must not consume quota or cause re-downloads.
            duplicate = [candidates[start - 1]] if start else []
            pages[(code, start // 40 + 1)] = duplicate + candidates[start : start + 40]

    run, options, calls = scripted_run(tmp_path, pages, details={"939999": detail_html("title")})
    runner = CliRunner()
    plan_result = runner.invoke(app, ["plan", "--output-dir", str(run.storage.root)])
    assert plan_result.exit_code == 0, plan_result.output
    plan = json.loads(plan_result.stdout)
    assert plan["total"] == 500
    assert [(row["cat4"], row["quota"]) for row in plan["categories"]] == [
        (code, quota) for _, code, quota in CATEGORIES
    ]

    downloader = options["image_downloader"]
    transport = downloader.transport
    interrupted_url = "https://recipe1.ezmember.co.kr/940205.png"
    interrupted = False

    def interrupt_once(url, **kwargs):
        """Model Ctrl-C at an unfinished asset without replacing collection logic."""
        nonlocal interrupted
        if url == interrupted_url and not interrupted:
            interrupted = True
            raise KeyboardInterrupt("synthetic operator interruption")
        return transport(url, **kwargs)

    downloader.transport = interrupt_once
    with pytest.raises(KeyboardInterrupt, match="synthetic operator interruption"):
        run.collect_quotas()
    checkpoint = run.snapshot()
    assert interrupted and len(checkpoint["allocations"]) == 205
    assert "940205" not in checkpoint["images"]
    assert checkpoint["details"]["940205"]["state"] == "parsed"
    assert checkpoint["collection_mode"] == "quota"
    preserved = {
        path.relative_to(run.storage.root): digest(path.read_bytes())
        for folder in ("lists", "details", "recipes", "images")
        for path in run.storage.path(folder).rglob("*")
        if path.is_file()
    }
    earlier_calls = Counter(calls)

    resumed = CollectionRun.resume(**options)
    result = resumed.collect_quotas()
    expected_total = 500
    assert result["acquisition_complete"] is True
    assert result["status"] == "complete"
    assert result["unique_success_count"] == expected_total
    manifest = resumed.snapshot()
    assert len(manifest["allocations"]) == expected_total
    for code, ids in expected.items():
        assert [
            row["source_id"] for row in manifest["allocations"] if row["category_code"] == code
        ] == ids
    assert len({row["source_id"] for row in manifest["allocations"]}) == expected_total
    assert len(manifest["failures"]) == 1
    assert manifest["failures"][0]["source_id"] == "939999"
    assert manifest["replacements"] == []
    assert len([row for row in manifest["candidates"] if row["source_id"] == "940000"]) == 9
    assert all(Counter(calls)[url] == count for url, count in earlier_calls.items())
    assert all(count == 1 for count in Counter(calls).values())
    assert all(
        digest((run.storage.root / path).read_bytes()) == sha for path, sha in preserved.items()
    )
    assert len(list(run.storage.path("images").glob("*.png"))) == expected_total
    assert not list(run.storage.root.rglob("*.tmp"))

    for command in ("validate", "report"):
        invocation = runner.invoke(app, [command, "--output-dir", str(run.storage.root)])
        assert invocation.exit_code == 0, invocation.output
        report = json.loads(invocation.stdout)
        assert report["unique_success_count"] == expected_total
        assert report["acquisition_complete"] is True
        assert report["semantic_duplicate_review"] == dict(
            status="pending", required_before_production=True
        )
        assert report["semantic_uniqueness_guaranteed"] is False
        assert report["categories"][-1]["deficit"] == 0
        assert all(row["deficit"] == 0 for row in report["categories"][:-1])
    assert json.loads(run.storage.path("report.json").read_text(encoding="utf-8")) == report
    with run.storage.path("review.csv").open(encoding="utf-8-sig", newline="") as stream:
        review_rows = list(csv.DictReader(stream))
    assert any(row["source_id"] == "940205" for row in review_rows)
    assert any(row["code"] == "acquisition_failed" for row in review_rows)

    # Completed and exhausted categories must remain stable on another resume.
    calls_before = list(calls)
    again = CollectionRun.resume(**options)
    assert again.collect_quotas() == result
    assert calls == calls_before
    assert again.snapshot()["allocations"] == manifest["allocations"]


def test_exhausted_category_reports_shortfall_and_resume_makes_no_requests(tmp_path):
    """Exercise real source exhaustion cheaply; reporting tests cover exactly 499 IDs."""
    run, options, calls = scripted_run(tmp_path, {("63", 1): ["950001", "950002", "950003"]})
    result = run.collect_quotas(category_code="63")
    assert result["acquisition_complete"] is False
    assert result["unique_success_count"] == 3
    assert result["categories"][0]["deficit"] == 97
    assert run.snapshot()["category_outcomes"] == [
        dict(category_code="63", reason="exhausted", page=2, selected=3, deficit=97)
    ]
    assert not any("cat4=56" in url or "page=3" in url for url in calls)
    runner = CliRunner()
    for command in ("validate", "report"):
        invocation = runner.invoke(app, [command, "--output-dir", str(run.storage.root)])
        assert invocation.exit_code == 1, invocation.output
        report = json.loads(invocation.stdout)
        assert report["unique_success_count"] == 3
        assert report["categories"][0]["deficit"] == 97
        assert report["category_outcomes"][0]["reason"] == "exhausted"
    before_calls = list(calls)
    before = {path: path.read_bytes() for path in run.storage.root.rglob("*") if path.is_file()}
    again = CollectionRun.resume(**options)
    assert again.collect_quotas(category_code="63") == result
    assert calls == before_calls
    assert all(path.read_bytes() == body for path, body in before.items())
