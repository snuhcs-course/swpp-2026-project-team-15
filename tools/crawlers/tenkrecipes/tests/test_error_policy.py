# AI-assisted with Codex, 2026-11-14; human review pending.
"""Approved candidate-failure and operator-stop policies, exercised without live I/O."""

import pytest
from bs4 import BeautifulSoup

from crawlers.tenkrecipes.tests.stage3_support import fixture_response
from crawlers.tenkrecipes.tests.test_stage3_storage_resume import make_run


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
