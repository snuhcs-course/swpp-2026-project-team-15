# AI-assisted with Codex, 2026-11-15; reviewed by Soohyun An
# Test reorganization assisted by Codex, 2026-11-15; reviewed by Soohyun An
"""Exhausted rate limits remain resumable after their server deadline."""

import pytest

from crawlers.tenkrecipes.tests.support_http import FakeResponse, fixture_response
from crawlers.tenkrecipes.tests.support_images import StreamResponse, png_bytes
from crawlers.tenkrecipes.tests.support_runs import policy_run
from crawlers.tenkrecipes.workflow import CollectionRun


@pytest.mark.parametrize("asset", ["detail", "image"])
def test_exhausted_429_resumes_only_after_deadline(tmp_path, asset):
    limits = [FakeResponse(429, headers={"Retry-After": "2"}) for _ in range(3)]
    images = [StreamResponse(png_bytes())]
    details = limits if asset == "detail" else [fixture_response("detail.html")]
    if asset == "image":
        images = [StreamResponse(status=429, headers={"Retry-After": "2"}) for _ in range(3)]
    run, options, html, thumbnails = policy_run(tmp_path, ["900001"], *details, images=images)
    run.resume_pending(include_images=True)
    before = run.snapshot()
    assert before["reason"] == "retry_exhausted"
    assert before["network_failure_streak"] == []
    counts = (len(html.calls), len(thumbnails.calls))
    resumed = CollectionRun.resume(**options)
    assert resumed.resume_pending(include_images=True)[0]["status"] == "deferred"
    assert counts == (len(html.calls), len(thumbnails.calls))

    html.outcomes.append(fixture_response("detail.html"))
    if asset == "image":
        thumbnails.outcomes.append(StreamResponse(png_bytes()))
    options["client"].sleep(3)
    resumed = CollectionRun.resume(**options)
    resumed.resume_pending(include_images=True)
    after = resumed.snapshot()
    assert after["candidate_outcomes"]["900001"]["status"] == "acquired"
    assert after["network_failure_streak"] == []
    assert len(after["attempts"]) == len(before["attempts"]) + (2 if asset == "detail" else 1)
    for response in before["responses"]:
        assert resumed.storage.verify(response)
