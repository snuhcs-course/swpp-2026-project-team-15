# AI-assisted with Codex, 2026-11-12; human review pending.
"""Stage 5 source-order allocation and explicit shortfall acceptance contracts."""

import importlib
from urllib.parse import parse_qs, urlsplit

import pytest

from crawlers.tenkrecipes.tests.stage3_support import FakeResponse
from crawlers.tenkrecipes.tests.stage5_support import detail_html, scripted_run
from crawlers.tenkrecipes.workflow import CollectionRun


def test_ordered_first_success_allocation_keeps_variants_and_every_observation(tmp_path):
    first = [str(910000 + i) for i in range(101)]
    run, _, calls = scripted_run(
        tmp_path,
        {
            ("63", 1): first[:60],
            ("63", 2): [first[0], *first[60:]],
            ("56", 1): [first[0], first[100], "920000"],
        },
    )
    run.collect_quotas()
    manifest = run.snapshot()
    selected = manifest["allocations"]
    assert [r["source_id"] for r in selected if r["category_code"] == "63"] == first[:100]
    assert [r["source_id"] for r in selected if r["category_code"] == "56"] == [
        first[100],
        "920000",
    ]
    assert len(selected) == len({r["source_id"] for r in selected}) == 102
    observed = [r for r in manifest["candidates"] if r["source_id"] == first[0]]
    assert [(r["category_code"], r["page"], r["position"]) for r in observed] == [
        ("63", 1, 1),
        ("63", 2, 1),
        ("56", 1, 1),
    ]
    assert calls.count(f"https://www.10000recipe.com/recipe/{first[0]}") == 1
    assert calls.count(f"https://recipe1.ezmember.co.kr/{first[0]}.png") == 1


@pytest.mark.parametrize(
    "missing", ["title", "ingredients", "ingredient_names", "steps", "instructions", "image"]
)
def test_invalid_essentials_preserve_failure_and_use_next_same_category(tmp_path, missing):
    run, _, _ = scripted_run(
        tmp_path,
        {("63", 1): ["900001", "900002"]},
        details={"900001": detail_html(missing)},
        image_failures=("900001",) if missing == "image" else (),
    )
    run.collect_quotas()
    manifest = run.snapshot()
    assert manifest["allocations"] == [dict(source_id="900002", category_code="63")]
    failure = next(r for r in manifest["failures"] if r["source_id"] == "900001")
    assert failure["category_code"] == "63" and failure["reason"]
    assert manifest["replacements"] == []
    assert run.storage.path("details/900001.html").exists()
    if missing != "title":
        assert run.storage.path("recipes/900001.json").exists()
    report = importlib.import_module("crawlers.tenkrecipes.reporting").validate_run(
        run.storage.root
    )
    assert report["acquisition_complete"] is False
    assert failure in report["failures"]
    assert report["replacements"] == manifest["replacements"]
    assert next(r for r in report["categories"] if r["category_code"] == "63")["deficit"] == 99


def test_exhaustion_does_not_transfer_quota_or_broaden_filters(tmp_path):
    run, _, calls = scripted_run(tmp_path, {("56", 1): [str(930000 + i) for i in range(95)]})
    result = run.collect_quotas()
    assert result["status"] == "incomplete" and result["acquisition_complete"] is False
    assert len(run.snapshot()["allocations"]) == 90
    outcome = next(r for r in run.snapshot()["category_outcomes"] if r["category_code"] == "63")
    assert outcome["reason"] == "exhausted" and outcome["deficit"] == 100
    for url in calls:
        if "list.html" in url:
            query = parse_qs(urlsplit(url).query)
            assert query["cat2"] == ["18"] and query["order"] == ["reco"]


def test_repeated_page_without_new_ids_stops_with_anomaly(tmp_path):
    run, _, calls = scripted_run(tmp_path, {("63", 1): ["900001"], ("63", 2): ["900001"]})
    result = run.collect_quotas()
    assert result["acquisition_complete"] is False
    outcome = next(r for r in run.snapshot()["category_outcomes"] if r["category_code"] == "63")
    assert outcome["reason"] == "repeated_page" and outcome["deficit"] == 99
    assert not any("cat4=63" in url and "page=3" in url for url in calls)


@pytest.mark.parametrize("failure", ["list_structure", "denial", "deferred"])
def test_global_stop_is_not_replaced_by_a_later_candidate(tmp_path, failure):
    pages = {("63", 1): ["900001", "900002"]}
    if failure == "list_structure":
        pages[("63", 1)] = FakeResponse(body=b"<html>unrecognized list structure</html>")
    elif failure == "denial":
        pages[("63", 1)] = FakeResponse(403)
    elif failure == "deferred":
        pages[("63", 1)] = FakeResponse(429, headers={"Retry-After": "999999"})
    run, _, calls = scripted_run(tmp_path, pages)
    result = run.collect_quotas()
    assert result["status"] == ("deferred" if failure == "deferred" else "blocked")
    assert result["acquisition_complete"] is False
    assert not any(url.endswith("/900002") or "cat4=56" in url for url in calls)
    assert run.snapshot()["allocations"] == []


def test_resume_reuses_saved_work_before_unseen_pages_and_keeps_allocations(tmp_path):
    run, options, calls = scripted_run(tmp_path, {("63", 1): ["900001"]})
    run.fetch_list("63", 1)
    run.fetch_detail("900001")
    run.fetch_thumbnail("900001")
    calls.clear()
    resumed = CollectionRun.resume(**options)
    resumed.collect_quotas()
    assert resumed.snapshot()["allocations"] == [dict(source_id="900001", category_code="63")]
    assert "list.html" in calls[0] and "page=2" in calls[0]
    assert not any(url.endswith("/900001") or url.endswith("/900001.png") for url in calls)
    allocations = resumed.snapshot()["allocations"]
    again = CollectionRun.resume(**options)
    again.collect_quotas()
    assert again.snapshot()["allocations"] == allocations
