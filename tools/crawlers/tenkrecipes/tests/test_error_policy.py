# AI-assisted with Codex, 2026-11-14; human review pending.
"""Approved candidate-failure and operator-stop policies, exercised without live I/O."""

import json

import pytest
from bs4 import BeautifulSoup
from typer.testing import CliRunner

from crawlers.tenkrecipes.cli import app
from crawlers.tenkrecipes.tests.stage3_support import FakeResponse, FakeTransport, fixture_response
from crawlers.tenkrecipes.tests.stage5_support import list_html
from crawlers.tenkrecipes.tests.test_stage3_storage_resume import make_run
from crawlers.tenkrecipes.tests.test_stage4_images import StreamResponse
from crawlers.tenkrecipes.workflow import CollectionRun


@pytest.mark.parametrize("title", ["", "  \n\t "])
def test_blank_title_is_a_preserved_candidate_failure(tmp_path, title):
    response = fixture_response("stage2_detail.html")
    soup = BeautifulSoup(response.content, "html.parser")
    soup.select_one(".view2_summary h3").string = title
    response.content = str(soup).encode()
    _, run, _, transport, _ = make_run(tmp_path, response)
    result = run.fetch_detail("900001")
    assert result["status"] == "failed" and result["reason"] == "missing_title"
    detail = run.snapshot()["details"]["900001"]
    assert run.storage.verify(detail["raw"]) == response.content
    assert "record" not in detail
    assert len(transport.calls) == 1


@pytest.mark.parametrize("selector", [".view2_summary h3", "#divConfirmedMaterialArea"])
def test_missing_structural_element_still_blocks_collection(tmp_path, selector):
    response = fixture_response("stage2_detail.html")
    soup = BeautifulSoup(response.content, "html.parser")
    soup.select_one(selector).decompose()
    response.content = str(soup).encode()
    _, run, _, _, _ = make_run(tmp_path, response)
    result = run.fetch_detail("900001")
    assert (result["status"], result["reason"]) == ("blocked", "structure_mismatch")
    assert run.storage.verify(run.snapshot()["details"]["900001"]["raw"]) == response.content


def policy_run(tmp_path, ids, *details, images=()):
    """Use the real workflow with scripted HTML and independently queued images."""
    _, run, options, html, clock = make_run(
        tmp_path, FakeResponse(body=list_html("52", ids)), *details
    )
    image_transport = FakeTransport(clock, *images)
    run.image_downloader.transport = image_transport
    options["image_downloader"] = run.image_downloader
    run.fetch_list("52", 1)
    return run, options, html, image_transport


@pytest.mark.parametrize("violation", ["host", "redirect"])
def test_image_policy_violation_requires_operator_review_before_resume(tmp_path, violation):
    url = "https://recipe1.ezmember.co.kr/900001.png"
    if violation == "host":
        response = StreamResponse(
            status=302, headers={"Location": "https://outside.invalid/image.png"}
        )
    else:
        response = StreamResponse(status=302, headers={"Location": url})
    run, options, html, images = policy_run(
        tmp_path,
        ["900001", "900002"],
        fixture_response("stage2_detail.html"),
        images=[response for _ in range(4)],
    )
    run.resume_pending(include_images=True)
    snapshot = run.snapshot()
    assert snapshot["state"] == "blocked"
    assert snapshot["operator_review_required"] is True
    assert snapshot["operator_notice"]["source_id"] == "900001"
    assert snapshot["operator_notice"]["asset_url"] == url
    assert "operator" in snapshot["operator_notice"]["message"].lower()
    assert len(html.calls) == 2
    assert len(images.calls) == (1 if violation == "host" else 4)
    resumed = CollectionRun.resume(**options)
    assert resumed.resume_pending(include_images=True)[0]["status"] == "blocked"
    assert len(html.calls) == 2
    assert len(images.calls) == (1 if violation == "host" else 4)
    resumed.acknowledge_stop()
    assert resumed.snapshot()["operator_review_required"] is False


def test_cli_reports_operator_required_stop_without_silent_resume(tmp_path, monkeypatch):
    run, _, html, _ = policy_run(
        tmp_path,
        ["900001"],
        fixture_response("stage2_detail.html"),
        images=[
            StreamResponse(status=302, headers={"Location": "https://outside.invalid/image.png"})
        ],
    )
    run.resume_pending(include_images=True)
    monkeypatch.setattr(CollectionRun, "resume", classmethod(lambda cls, **kwargs: run))
    result = CliRunner().invoke(app, ["resume", "--output-dir", str(run.storage.root), "--live"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["operator_review_required"] is True
    assert "operator" in payload["operator_notice"]["message"].lower()
    assert len(html.calls) == 2
