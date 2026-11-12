# AI-assisted with Codex, 2026-11-12; human review pending.
"""Regressions for interrupted checkpoints and inconsistent resumed state."""

import os
from pathlib import Path

import pytest
import requests

from crawlers.tenkrecipes.tests.stage3_support import FakeResponse, fixture_response
from crawlers.tenkrecipes.tests.test_stage3_storage_resume import make_run
from crawlers.tenkrecipes.tests.test_stage4_images import StreamResponse, make_image_run, png_bytes
from crawlers.tenkrecipes.workflow import CollectionRun


def interrupt_checkpoint(monkeypatch, run, action):
    """Interrupt only manifest replacement after other artifacts have been saved."""
    checkpoint = run.storage.path("manifest.json")
    original = checkpoint.read_bytes()
    replace = os.replace

    def interrupt(source, destination):
        if Path(destination).resolve() == checkpoint:
            raise OSError("synthetic checkpoint interruption")
        return replace(source, destination)

    with monkeypatch.context() as patch:
        patch.setattr(os, "replace", interrupt)
        with pytest.raises(OSError, match="checkpoint interruption"):
            action()
    assert checkpoint.read_bytes() == original


@pytest.mark.parametrize("failure", ["rate_limit", "denied", "transport"])
def test_failure_checkpoint_interruption_preserves_outcome_and_pending_work(
    tmp_path, monkeypatch, failure
):
    response = {
        "rate_limit": FakeResponse(429, headers={"Retry-After": "999"}),
        "denied": FakeResponse(403),
        "transport": requests.RequestException("synthetic transport error"),
    }[failure]
    module, run, options, transport, _ = make_run(
        tmp_path,
        fixture_response("stage2_list.html"),
        response,
    )
    run.fetch_list("52", 1)
    interrupt_checkpoint(monkeypatch, run, lambda: run.fetch_list("52", 2))
    resumed = module.CollectionRun.resume(**options)
    snapshot = resumed.snapshot()
    expected = {
        "rate_limit": ("deferred", "wait_budget_exceeded"),
        "denied": ("blocked", "access_denied"),
        "transport": ("failed", "transport_error"),
    }[failure]
    assert (snapshot["state"], snapshot["reason"]) == expected
    assert snapshot["pending_lists"] == [dict(category_code="52", page=2)]
    assert len(snapshot["attempts"]) == 2
    assert len(transport.calls) == 2
    if failure == "rate_limit":
        assert snapshot["retry_not_before"]
        assert resumed.fetch_list("52", 2)["status"] == "deferred"
        assert len(transport.calls) == 2
    # Successful recovery must also survive another restart.
    assert module.CollectionRun.resume(**options).snapshot() == snapshot


@pytest.mark.parametrize("pending", ["list", "detail"])
def test_cached_reparse_preserves_another_requests_retry_deadline(tmp_path, pending):
    """Rebuilding derived JSON must not allow an unrelated request to run early."""
    module, run, options, transport, _ = make_run(
        tmp_path,
        fixture_response("stage2_list.html"),
        fixture_response("stage2_detail.html"),
        FakeResponse(429, headers={"Retry-After": "999"}),
    )
    run.fetch_list("52", 1)
    run.fetch_detail("900001")
    if pending == "list":
        assert run.fetch_list("52", 2)["status"] == "deferred"
    else:
        assert run.fetch_detail("900002")["status"] == "deferred"
    before = run.snapshot()
    run.storage.path("recipes/900001.json").unlink()
    resumed = module.CollectionRun.resume(**options)
    assert resumed.fetch_detail("900001")["status"] == "parsed"
    after = resumed.snapshot()
    assert after["retry_not_before"] == before["retry_not_before"]
    assert (after["state"], after["reason"]) == (before["state"], before["reason"])
    if pending == "list":
        assert resumed.fetch_list("52", 2)["status"] == "deferred"
    else:
        assert resumed.fetch_detail("900002")["status"] == "deferred"
    assert len(transport.calls) == 3


@pytest.mark.parametrize("category,page", [("52", 2), ("63", 1)])
def test_new_observation_reuses_validated_source_state(tmp_path, category, page):
    """Repeated observations must agree with the already validated shared asset."""
    _, run, options, images, html = make_image_run(tmp_path, StreamResponse(png_bytes()))
    run.fetch_thumbnail("900001")
    response = fixture_response("stage2_list.html")
    response.content = response.content.replace(
        b'name="cat4" value="52"', f'name="cat4" value="{category}"'.encode()
    )
    html.outcomes = [response]
    assert run.fetch_list(category, page)["status"] == "ok"
    resumed = CollectionRun.resume(**options)
    manifest = resumed.snapshot()
    observations = [row for row in manifest["candidates"] if row["source_id"] == "900001"]
    assert [(row["category_code"], row["page"]) for row in observations] == [
        ("52", 1),
        (category, page),
    ]
    assert all(row["state"] == "image_validated" for row in observations)
    assert manifest["images"]["900001"]["state"] == "image_validated"
    assert len(images.calls) == 1 and len(html.calls) == 3


@pytest.mark.parametrize("response_file", ["intact", "corrupt", "missing"])
def test_orphan_detail_restores_and_verifies_every_retry_response(
    tmp_path, monkeypatch, response_file
):
    """Recover intermediate retry bodies as well as the final successful response."""
    module, run, options, transport, _ = make_run(
        tmp_path,
        fixture_response("stage2_list.html"),
        FakeResponse(503, body=b"synthetic temporary failure"),
        fixture_response("stage2_detail.html"),
    )
    run.fetch_list("52", 1)
    interrupt_checkpoint(monkeypatch, run, lambda: run.fetch_detail("900001"))
    provenance = run.storage.read_json("details/900001.html.meta.json")
    attempt = next(row for row in provenance["attempts"] if row.get("status_code") == 503)
    relative = f"attempts/{attempt['attempt_id']}.html"
    path = run.storage.path(relative)
    if response_file == "corrupt":
        path.write_bytes(b"corrupt retry response")
    elif response_file == "missing":
        path.unlink()
    resumed = module.CollectionRun.resume(**options)
    if response_file != "intact":
        before = run.storage.path("manifest.json").read_bytes()
        with pytest.raises(module.IntegrityError):
            resumed.fetch_detail("900001")
        assert run.storage.path("manifest.json").read_bytes() == before
        if response_file == "corrupt":
            assert path.read_bytes() == b"corrupt retry response"
    else:
        assert resumed.fetch_detail("900001")["status"] == "parsed"
        responses = resumed.snapshot()["responses"]
        assert any(
            row["path"] == relative and row["sha256"] == attempt["sha256"] for row in responses
        )
        assert {row["status_code"] for row in responses} == {200, 503}
        # A second restart verifies the recovered response reference too.
        assert module.CollectionRun.resume(**options).snapshot() == resumed.snapshot()
    assert len(transport.calls) == 3
