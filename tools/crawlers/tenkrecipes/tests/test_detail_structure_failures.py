# AI-assisted with Codex, 2026-11-15; human review pending.
"""Approved detail-structure failure replacement and saved-run compatibility."""

import pytest
from bs4 import BeautifulSoup

from crawlers.tenkrecipes.tests.stage5_support import detail_html, scripted_run
from crawlers.tenkrecipes.workflow import CollectionRun


@pytest.mark.parametrize("selector", [".view2_summary", "#divConfirmedMaterialArea", ".view_step"])
def test_unparseable_detail_is_preserved_and_replaced_in_same_category(tmp_path, selector):
    soup = BeautifulSoup(detail_html(), "html.parser")
    soup.select_one(selector).decompose()
    body = str(soup).encode()
    run, _, calls = scripted_run(
        tmp_path, {("63", 1): ["900001", "900002"]}, details={"900001": body}
    )
    run.fetch_list("63", 1)
    checkpoint = run.snapshot()
    checkpoint["network_failure_streak"] = ["899998", "899999"]
    run.storage.write_json("manifest.json", checkpoint)
    # The candidate policy must neither count nor reset a structural content failure.
    run._manifest = checkpoint
    candidate = run.snapshot()["candidates"][0]
    outcome = run._process_candidate(candidate)
    assert outcome["status"] == "failed" and outcome["reason"] == "structure_mismatch"
    assert run.snapshot()["network_failure_streak"] == ["899998", "899999"]
    run.collect_quotas(category_code="63")
    manifest = run.snapshot()
    assert manifest["allocations"] == [dict(source_id="900002", category_code="63")]
    assert manifest["failures"][0]["source_id"] == "900001"
    assert manifest["failures"][0]["status"] == "failed"
    assert manifest["replacements"] == [
        dict(failed_source_id="900001", replacement_source_id="900002", category_code="63")
    ]
    detail = manifest["details"]["900001"]
    assert run.storage.verify(detail["raw"]) == body
    assert "record" not in detail and "900001" not in manifest["images"]
    assert calls.count("https://www.10000recipe.com/recipe/900001") == 1
    assert not any("cat4=56" in url for url in calls)


def test_old_blocked_detail_becomes_failed_without_refetch_or_losing_replacement(tmp_path):
    """Model the schema-4 checkpoint saved by the earlier stop-on-detail policy."""
    run, options, calls = scripted_run(
        tmp_path,
        {("63", 1): ["900001", "900002"]},
        details={"900001": detail_html("structure")},
    )
    run.fetch_list("63", 1)
    run.fetch_detail("900001")
    manifest = run.snapshot()
    manifest.update(state="blocked", reason="structure_mismatch")
    manifest["details"]["900001"]["state"] = "blocked"
    manifest["candidates"][0]["state"] = "blocked"
    raw = manifest["details"]["900001"]["raw"]
    manifest["failures"] = [
        dict(
            source_id="900001",
            category_code="63",
            status="blocked",
            reason="structure_mismatch",
            source_url=manifest["candidates"][0]["source_url"],
            raw_path=raw["path"],
            record_path=None,
            image_path=None,
            page=1,
            position=1,
        )
    ]
    run.storage.write_json("manifest.json", manifest)
    original = run.storage.verify(raw)
    calls.clear()
    resumed = CollectionRun.resume(**options)
    resumed.collect_quotas(category_code="63")
    saved = resumed.snapshot()
    assert saved["details"]["900001"]["state"] == "failed"
    assert len(saved["failures"]) == 1 and saved["failures"][0]["status"] == "failed"
    assert saved["replacements"] == [
        dict(failed_source_id="900001", replacement_source_id="900002", category_code="63")
    ]
    assert resumed.storage.verify(raw) == original
    assert "https://www.10000recipe.com/recipe/900001" not in calls
    assert "https://recipe1.ezmember.co.kr/900001.png" not in calls
    before = list(calls)
    CollectionRun.resume(**options).collect_quotas(category_code="63")
    assert calls == before
