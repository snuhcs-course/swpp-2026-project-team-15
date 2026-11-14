# AI-assisted with Codex, 2026-11-14; human review pending.
"""Approved candidate-failure and operator-stop policies, exercised without live I/O."""

import json
import os
from pathlib import Path

import pytest
import requests
from bs4 import BeautifulSoup
from typer.testing import CliRunner

from crawlers.tenkrecipes.cli import app
from crawlers.tenkrecipes.tests.stage3_support import FakeResponse, FakeTransport, fixture_response
from crawlers.tenkrecipes.tests.stage5_support import detail_html, list_html
from crawlers.tenkrecipes.tests.test_stage3_storage_resume import make_run
from crawlers.tenkrecipes.tests.test_stage4_images import StreamResponse, png_bytes
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
def test_missing_detail_structure_is_a_preserved_candidate_failure(tmp_path, selector):
    response = fixture_response("stage2_detail.html")
    soup = BeautifulSoup(response.content, "html.parser")
    soup.select_one(selector).decompose()
    response.content = str(soup).encode()
    _, run, _, _, _ = make_run(tmp_path, response)
    result = run.fetch_detail("900001")
    assert (result["status"], result["reason"]) == ("failed", "structure_mismatch")
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


def exhausted(kind="http"):
    """Supply exactly one recipe's three allowed transient failure attempts."""
    if kind == "connection":
        return [requests.ConnectionError("synthetic connection failure") for _ in range(3)]
    return [FakeResponse(503, body=b"synthetic unavailable") for _ in range(3)]


@pytest.mark.parametrize("kind", ["http", "connection"])
def test_exhausted_recipe_moves_to_next_candidate_and_success_resets_streak(tmp_path, kind):
    run, _, html, images = policy_run(
        tmp_path,
        ["900001", "900002"],
        *exhausted(kind),
        fixture_response("stage2_detail.html"),
        images=[StreamResponse(png_bytes())],
    )
    run.resume_pending(include_images=True)
    snapshot = run.snapshot()
    assert snapshot["candidate_outcomes"]["900001"]["reason"] == "retry_exhausted"
    assert snapshot["candidate_outcomes"]["900002"]["status"] == "acquired"
    assert snapshot["network_failure_streak"] == []
    assert snapshot["operator_review_required"] is False
    assert len(html.calls) == 5 and len(images.calls) == 1


def test_three_distinct_exhausted_recipes_stop_before_the_fourth_and_notify(tmp_path, monkeypatch):
    run, options, html, _ = policy_run(
        tmp_path,
        ["900001", "900001", "900002", "900003", "900004"],
        *exhausted(),
        *exhausted(),
        *exhausted(),
    )
    run.resume_pending(include_images=True)
    snapshot = run.snapshot()
    assert snapshot["state"] == "blocked" and snapshot["reason"] == "consecutive_network_failures"
    assert snapshot["network_failure_streak"] == ["900001", "900002", "900003"]
    assert snapshot["operator_notice"]["source_ids"] == snapshot["network_failure_streak"]
    assert snapshot["operator_review_required"] is True
    assert len(html.calls) == 10
    resumed = CollectionRun.resume(**options)
    assert resumed.resume_pending(include_images=True)[0]["status"] == "blocked"
    assert len(html.calls) == 10
    # The real CLI must display the count and resume only after explicit acknowledgement.
    monkeypatch.setattr(CollectionRun, "resume", classmethod(lambda cls, **kwargs: resumed))
    result = CliRunner().invoke(app, ["resume", "--output-dir", str(run.storage.root), "--live"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["network_failure_streak"] == snapshot["network_failure_streak"]
    html.outcomes.append(fixture_response("stage2_detail.html"))
    resumed.image_downloader.transport.outcomes.append(StreamResponse(png_bytes()))
    result = CliRunner().invoke(
        app, ["resume", "--output-dir", str(run.storage.root), "--live", "--acknowledge-stop"]
    )
    assert result.exit_code == 1  # Preserved failed candidates still make the pilot incomplete.
    assert resumed.snapshot()["operator_review_required"] is False
    assert resumed.snapshot()["candidate_outcomes"]["900004"]["status"] == "acquired"
    assert len(html.calls) == 11


def test_success_breaks_a_sequence_of_network_failures(tmp_path):
    run, _, _, _ = policy_run(
        tmp_path,
        [str(900001 + i) for i in range(6)],
        *exhausted(),
        *exhausted(),
        fixture_response("stage2_detail.html"),
        *exhausted(),
        *exhausted(),
        fixture_response("stage2_detail.html"),
        images=[StreamResponse(png_bytes()), StreamResponse(png_bytes())],
    )
    run.resume_pending(include_images=True)
    assert run.snapshot()["operator_review_required"] is False
    assert run.snapshot()["network_failure_streak"] == []
    assert len(run.snapshot()["candidate_outcomes"]) == 6


def test_failure_streak_survives_restart_without_recounting_saved_failures(tmp_path):
    run, options, html, _ = policy_run(tmp_path, ["900001"], *exhausted())
    run.resume_pending(include_images=True)
    resumed = CollectionRun.resume(**options)
    html.outcomes.extend(
        [
            FakeResponse(body=list_html("52", ["900002", "900003", "900004"])),
            *exhausted(),
            *exhausted(),
        ]
    )
    resumed.fetch_list("52", 2)
    resumed.resume_pending(include_images=True)
    assert resumed.snapshot()["network_failure_streak"] == ["900001", "900002", "900003"]
    assert resumed.snapshot()["operator_review_required"] is True
    assert len(html.calls) == 11


@pytest.mark.parametrize(
    "missing", ["title", "ingredients", "ingredient_names", "steps", "instructions"]
)
def test_content_failure_is_preserved_and_replaced_without_network_failure_count(tmp_path, missing):
    run, _, _, images = policy_run(
        tmp_path,
        ["900001", "900002"],
        FakeResponse(body=detail_html(missing)),
        fixture_response("stage2_detail.html"),
        images=[StreamResponse(png_bytes())],
    )
    run.resume_pending(include_images=True)
    snapshot = run.snapshot()
    assert snapshot["candidate_outcomes"]["900001"]["status"] == "failed"
    assert snapshot["candidate_outcomes"]["900002"]["status"] == "acquired"
    assert snapshot["network_failure_streak"] == []
    assert len(images.calls) == 1
    assert run.storage.verify(snapshot["details"]["900001"]["raw"])


def test_content_failure_does_not_reset_existing_network_failures(tmp_path):
    run, _, _, _ = policy_run(
        tmp_path,
        ["900001", "900002", "900003", "900004"],
        *exhausted(),
        FakeResponse(body=detail_html("title")),
        *exhausted(),
        *exhausted(),
    )
    run.resume_pending(include_images=True)
    assert run.snapshot()["network_failure_streak"] == ["900001", "900003", "900004"]
    assert run.snapshot()["operator_review_required"] is True


def test_rate_limit_stops_without_counting_a_recipe_network_failure(tmp_path):
    run, _, html, _ = policy_run(
        tmp_path,
        ["900001", "900002"],
        FakeResponse(429, headers={"Retry-After": "999"}),
    )
    run.resume_pending(include_images=True)
    assert run.snapshot()["state"] == "deferred"
    assert run.snapshot()["retry_not_before"]
    assert run.snapshot()["network_failure_streak"] == []
    assert len(html.calls) == 2


def test_image_connection_retry_exhaustion_counts_one_recipe_and_continues(tmp_path):
    run, _, _, images = policy_run(
        tmp_path,
        ["900001", "900002"],
        fixture_response("stage2_detail.html"),
        fixture_response("stage2_detail.html"),
        images=[
            *(StreamResponse(png_bytes(), interrupted=True) for _ in range(3)),
            StreamResponse(png_bytes()),
        ],
    )
    run.resume_pending(include_images=True)
    assert run.snapshot()["candidate_outcomes"]["900001"]["reason"] == "retry_exhausted"
    assert run.snapshot()["candidate_outcomes"]["900002"]["status"] == "acquired"
    assert run.snapshot()["network_failure_streak"] == []
    assert len(images.calls) == 4


def test_network_failure_count_survives_interrupted_outcome_checkpoint(tmp_path, monkeypatch):
    run, options, html, _ = policy_run(
        tmp_path,
        ["900001", "900002"],
        *exhausted(),
        fixture_response("stage2_detail.html"),
        images=[StreamResponse(png_bytes())],
    )
    replace = os.replace

    def interrupt(source, destination):
        if Path(destination) == run.storage.path("manifest.json"):
            saved = json.loads(Path(source).read_text(encoding="utf-8"))
            if "900001" in saved.get("candidate_outcomes", {}):
                raise OSError("synthetic outcome checkpoint interruption")
        return replace(source, destination)

    with monkeypatch.context() as patch:
        patch.setattr(os, "replace", interrupt)
        with pytest.raises(OSError):
            run.resume_pending(include_images=True)
    resumed = CollectionRun.resume(**options)
    assert resumed.snapshot()["network_failure_streak"] == ["900001"]
    resumed.resume_pending(include_images=True)
    assert resumed.snapshot()["network_failure_streak"] == []
    assert len(html.calls) == 5


@pytest.mark.parametrize("missing", ["record", "image"])
def test_acquired_candidate_repairs_missing_files_without_replaying_old_success(tmp_path, missing):
    run, options, _, images = policy_run(
        tmp_path,
        ["900001", "900002"],
        fixture_response("stage2_detail.html"),
        *exhausted(),
        images=[StreamResponse(png_bytes())],
    )
    run.resume_pending(include_images=True)
    snapshot = run.snapshot()
    if missing == "record":
        entry = snapshot["details"]["900001"]["record"]
    else:
        entry = snapshot["images"]["900001"]
        images.outcomes.append(StreamResponse(png_bytes()))
    path = run.storage.path(entry["path"])
    path.unlink()
    resumed = CollectionRun.resume(**options)
    resumed.resume_pending(include_images=True)
    assert path.exists()
    assert resumed.snapshot()["network_failure_streak"] == ["900002"]
