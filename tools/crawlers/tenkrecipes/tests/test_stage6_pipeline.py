# AI-assisted with Codex, 2026-11-14; human review pending.
"""Exercise the approved full pipeline using only synthetic transport responses."""

import csv
import json
from collections import Counter

import pytest
from typer.testing import CliRunner

from crawlers.tenkrecipes.cli import app
from crawlers.tenkrecipes.config import CATEGORIES
from crawlers.tenkrecipes.storage import digest
from crawlers.tenkrecipes.tests.stage5_support import detail_html, scripted_run
from crawlers.tenkrecipes.workflow import CollectionRun


@pytest.mark.parametrize("shortfall", [False, True], ids=["complete-500", "shortfall-499"])
def test_full_pipeline_preserves_work_across_interruption_and_reports_quotas(tmp_path, shortfall):
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
        if shortfall and code == CATEGORIES[-1][1]:
            ids.pop()
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
    expected_total = 499 if shortfall else 500
    assert result["acquisition_complete"] is (not shortfall)
    assert result["status"] == ("incomplete" if shortfall else "complete")
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
    assert manifest["replacements"] == [
        dict(failed_source_id="939999", replacement_source_id="940000", category_code="63")
    ]
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
        assert invocation.exit_code == (1 if shortfall else 0), invocation.output
        report = json.loads(invocation.stdout)
        assert report["unique_success_count"] == expected_total
        assert report["acquisition_complete"] is (not shortfall)
        assert report["semantic_duplicate_review"] == dict(
            status="pending", required_before_production=True
        )
        assert report["semantic_uniqueness_guaranteed"] is False
        assert report["categories"][-1]["deficit"] == int(shortfall)
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
