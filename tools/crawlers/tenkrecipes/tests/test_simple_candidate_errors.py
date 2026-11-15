# AI-assisted with Codex, 2026-11-15; reviewed by Soohyun An
"""Skip terminal candidate errors and keep one small log without replacement links."""

import pytest
import requests

from crawlers.tenkrecipes.tests.support_http import FakeResponse, fixture_response
from crawlers.tenkrecipes.tests.support_images import StreamResponse, png_bytes
from crawlers.tenkrecipes.tests.support_runs import policy_run, scripted_run
from crawlers.tenkrecipes.workflow import CollectionRun


@pytest.mark.parametrize("asset", ["detail", "image"])
@pytest.mark.parametrize("error", ["404", "transport"])
def test_candidate_error_is_logged_and_next_candidate_is_used(tmp_path, asset, error):
    failure = (
        (FakeResponse(404) if asset == "detail" else StreamResponse(status=404))
        if error == "404"
        else requests.RequestException("synthetic transport failure")
    )
    details = [failure] if asset == "detail" else [fixture_response("detail.html")]
    images = [] if asset == "detail" else [failure]
    run, options, html, thumbnails = policy_run(
        tmp_path,
        ["900001", "900002"],
        *details,
        fixture_response("detail.html"),
        images=[*images, StreamResponse(png_bytes())],
    )
    run.resume_pending(include_images=True)
    manifest = run.snapshot()
    assert manifest["candidate_outcomes"]["900001"]["status"] == "failed"
    assert manifest["candidate_outcomes"]["900002"]["status"] == "acquired"
    assert len(manifest["failures"]) == 1
    log = manifest["failures"][0]
    assert log["source_url"].endswith("/900001")
    assert log["reason"] == ("http_error" if error == "404" else "transport_error")
    assert log["status"] == "failed" and log["category_code"] == "52"
    assert manifest["replacements"] == []
    if log["raw_path"]:
        assert run.storage.path(log["raw_path"]).is_file()
    counts = (len(html.calls), len(thumbnails.calls))
    CollectionRun.resume(**options).resume_pending(include_images=True)
    assert run.storage.read_json("manifest.json")["failures"] == manifest["failures"]
    assert counts == (len(html.calls), len(thumbnails.calls))


@pytest.mark.parametrize("recover", [False, True])
def test_pause_then_resume_records_only_terminal_candidate_failure(tmp_path, recover):
    run, options, calls = scripted_run(tmp_path, {("63", 1): ["900001", "900002"]})
    normal = run.client.transport
    paused = True

    def transport(url, **kwargs):
        if url.endswith("/900001"):
            calls.append(url)
            if paused:
                return FakeResponse(429, headers={"Retry-After": "999"}, url=url)
            if not recover:
                return FakeResponse(503, url=url)
        return normal(url, **kwargs)

    run.client.transport = transport
    run.collect_quotas(category_code="63")
    assert run.snapshot()["state"] == "deferred"
    assert run.snapshot()["failures"] == []
    options["client"].sleep(1000)
    paused = False
    resumed = CollectionRun.resume(**options)
    resumed.collect_quotas(category_code="63")
    manifest = resumed.snapshot()
    assert manifest["replacements"] == []
    if recover:
        assert manifest["failures"] == []
    else:
        assert len(manifest["failures"]) == 1
        assert manifest["failures"][0]["reason"] == "retry_exhausted"
        assert manifest["failures"][0]["status"] == "failed"
    before = list(calls)
    assert (
        CollectionRun.resume(**options).collect_quotas(category_code="63")["failures"]
        == manifest["failures"]
    )
    assert calls == before


def test_legacy_pause_row_becomes_terminal_but_historical_links_are_preserved(tmp_path):
    run, options, _ = scripted_run(
        tmp_path, {("63", 1): ["900001", "900002"]}, image_failures=["900001"]
    )
    manifest = run.snapshot()
    manifest["failures"] = [
        dict(
            source_id="900001", category_code="63", status="deferred", reason="wait_budget_exceeded"
        )
    ]
    legacy = dict(failed_source_id="899998", replacement_source_id="899999", category_code="63")
    manifest["replacements"] = [legacy]
    run.storage.write_json("manifest.json", manifest)
    resumed = CollectionRun.resume(**options)
    resumed.collect_quotas(category_code="63")
    final = resumed.snapshot()
    assert len(final["failures"]) == 1
    assert final["failures"][0]["status"] == "failed"
    assert final["failures"][0]["reason"] == "invalid_image"
    assert final["replacements"] == [legacy]


def test_terminal_log_survives_interrupted_checkpoint_once(tmp_path, monkeypatch):
    run, options, calls = scripted_run(
        tmp_path, {("63", 1): ["900001", "900002"]}, image_failures=["900001"]
    )
    commit = run._commit

    def interrupt(manifest):
        if manifest["candidate_outcomes"].get("900001", {}).get("status") == "failed":
            raise OSError("synthetic terminal checkpoint interruption")
        commit(manifest)

    with monkeypatch.context() as patch:
        patch.setattr(run, "_commit", interrupt)
        with pytest.raises(OSError, match="terminal checkpoint"):
            run.collect_quotas(category_code="63")
    resumed = CollectionRun.resume(**options)
    resumed.collect_quotas(category_code="63")
    assert len(resumed.snapshot()["failures"]) == 1
    assert resumed.snapshot()["replacements"] == []
    assert calls.count("https://www.10000recipe.com/recipe/900001") == 1
