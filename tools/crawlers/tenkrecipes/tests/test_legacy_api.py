# AI-assisted with Codex, 2026-11-15; reviewed by Soohyun An
"""Low-level compatibility APIs, distinct from terminal-candidate collection policy."""

import importlib
from pathlib import Path

from crawlers.tenkrecipes.tests.support_http import (
    DETAIL_URL,
    LIST_URL,
    FakeResponse,
    fixture_response,
)
from crawlers.tenkrecipes.tests.support_images import StreamResponse, make_image_run, png_bytes
from crawlers.tenkrecipes.tests.support_runs import make_run


def test_legacy_detail_only_resume_stops_on_http_error(tmp_path):
    """The legacy detail-only API stops on errors; CLI collection uses candidate policy."""
    _, run, _, transport, _ = make_run(
        tmp_path,
        fixture_response("list.html"),
        FakeResponse(404),
        fixture_response("detail.html"),
    )
    run.fetch_list("52", 1)
    run.resume_pending()
    assert run.snapshot()["state"] == "failed"
    assert run.snapshot()["reason"] == "http_error"
    assert [call["url"] for call in transport.calls] == [LIST_URL, DETAIL_URL]


def test_direct_thumbnail_api_can_retry_an_exhausted_transfer(tmp_path):
    body = png_bytes()
    _, run, options, images, html = make_image_run(
        tmp_path, *(StreamResponse(body, interrupted=True) for _ in range(3))
    )
    assert run.fetch_thumbnail("900001")["status"] == "failed"
    assert not any(Path(options["plan"]["output_dir"]).glob("images/*.*"))
    images.outcomes.append(StreamResponse(body))
    workflow = importlib.import_module("crawlers.tenkrecipes.workflow")
    resumed = workflow.CollectionRun.resume(**options)
    assert resumed.fetch_thumbnail("900001")["status"] == "image_validated"
    assert len(images.calls) == 4
    assert len(html.calls) == 2
