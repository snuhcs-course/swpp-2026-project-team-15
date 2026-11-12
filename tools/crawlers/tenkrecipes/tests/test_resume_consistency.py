# AI-assisted with Codex, 2026-11-12; human review pending.
"""Regressions for interrupted checkpoints and inconsistent resumed state."""

import os
from pathlib import Path

import pytest
import requests

from crawlers.tenkrecipes.tests.stage3_support import FakeResponse, fixture_response
from crawlers.tenkrecipes.tests.test_stage3_storage_resume import make_run


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
