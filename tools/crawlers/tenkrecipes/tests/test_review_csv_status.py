# AI-assisted with Codex, 2026-11-15; reviewed by Soohyun An
# Test reorganization assisted by Codex, 2026-11-15; reviewed by Soohyun An
"""Review exports retain the acquisition status recorded in JSON."""

import csv

import pytest

from crawlers.tenkrecipes.reporting import write_report
from crawlers.tenkrecipes.tests.support_http import FakeResponse
from crawlers.tenkrecipes.tests.support_runs import scripted_run


@pytest.mark.parametrize("status", ["blocked", "deferred", "failed"])
def test_review_csv_preserves_legacy_failure_status(tmp_path, status):
    run, _, _ = scripted_run(tmp_path, {("63", 1): FakeResponse(403)})
    run.collect_quotas(category_code="63")
    manifest = run.snapshot()
    manifest["failures"] = [dict(source_id="900001", status=status, reason="synthetic")]
    run.storage.write_json("manifest.json", manifest)
    report = write_report(run.storage.root)
    with run.storage.path("review.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["status"] == report["failures"][0]["status"] == status
    assert rows[0]["code"] == "acquisition_failed"
