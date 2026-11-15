# AI-assisted with Codex, 2026-11-14; reviewed by Soohyun An
# Test reorganization assisted by Codex, 2026-11-15; reviewed by Soohyun An
"""Allocation resume regressions and historical selected artifacts."""

import pytest

from crawlers.tenkrecipes.config import CATEGORIES, build_plan
from crawlers.tenkrecipes.tests.support_http import FakeResponse, client_for
from crawlers.tenkrecipes.tests.support_runs import saved_collection, scripted_run
from crawlers.tenkrecipes.workflow import CollectionRun


@pytest.mark.parametrize("missing", ["record", "image"])
def test_quota_resume_repairs_selected_artifacts_before_skipping_finished_category(
    tmp_path, missing
):
    run, options, calls = scripted_run(tmp_path, {("63", 1): ["900001"]})
    run.collect_quotas()
    snapshot = run.snapshot()
    entry = (
        snapshot["details"]["900001"]["record"]
        if missing == "record"
        else snapshot["images"]["900001"]
    )
    path = run.storage.path(entry["path"])
    path.unlink()
    calls.clear()
    resumed = CollectionRun.resume(**options)
    resumed.collect_quotas()
    assert path.exists()
    assert resumed.snapshot()["allocations"] == snapshot["allocations"]
    assert calls == ([] if missing == "record" else ["https://recipe1.ezmember.co.kr/900001.png"])


def test_denied_candidate_can_be_acquired_after_site_recovers(tmp_path):
    run, options, _ = scripted_run(tmp_path, {("63", 1): ["900001"]})
    normal_transport = run.client.transport
    denied = True

    def transport(url, **kwargs):
        if url.endswith("/900001") and denied:
            return FakeResponse(403, url=url)
        return normal_transport(url, **kwargs)

    run.client.transport = transport
    assert run.collect_quotas()["status"] == "blocked"
    denied = False
    resumed = CollectionRun.resume(**options)
    resumed.collect_quotas()
    assert resumed.snapshot()["allocations"] == [dict(source_id="900001", category_code="63")]
    assert resumed.snapshot()["replacements"] == []


def test_resuming_completed_quotas_preserves_last_page_checkpoints(tmp_path):
    """An offline rerun must not replace recorded final pages with page zero."""
    storage, manifest = saved_collection(tmp_path)
    manifest["category_outcomes"] = [
        dict(category_code=code, reason="quota_reached", page=1, selected=quota, deficit=0)
        for _, code, quota in CATEGORIES
    ]
    storage.write_json("manifest.json", manifest)
    _, client, transport, _ = client_for(run_budget=100000)
    metadata = storage.read_json("run.json")
    run = CollectionRun.resume(
        plan=build_plan(storage.root),
        client=client,
        parser_version=metadata["parser_version"],
        schema_version=metadata["schema_version"],
    )
    result = run.collect_quotas()
    assert result["acquisition_complete"] is True
    assert run.snapshot()["category_outcomes"] == manifest["category_outcomes"]
    assert transport.calls == []
