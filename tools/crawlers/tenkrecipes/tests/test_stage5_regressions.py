# AI-assisted with Codex, 2026-11-14; human review pending.
"""Confirmed stage 5 resume defects: selected artifacts and blocked replacements."""

import pytest

from crawlers.tenkrecipes.tests.stage3_support import FakeResponse
from crawlers.tenkrecipes.tests.stage5_support import scripted_run
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


def test_recovered_blocked_candidate_is_not_its_own_replacement(tmp_path):
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
