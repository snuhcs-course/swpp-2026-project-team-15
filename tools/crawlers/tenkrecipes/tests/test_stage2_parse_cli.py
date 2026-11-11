# AI-assisted with Codex, 2026-11-11; reviewed by Soohyun An
"""Execute the future offline parse command against disposable raw source files."""

import hashlib
import json
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures/stage2_detail.html"
SOURCE_URL = "https://www.10000recipe.com/recipe/900001"


def test_parse_command_converts_raw_html_without_modifying_it_or_fetching_images(
    run_tool, tmp_path
):
    source = tmp_path / "source.html"
    source.write_bytes(FIXTURE.read_bytes())
    original = hashlib.sha256(source.read_bytes()).hexdigest()
    result = run_tool("parse", "--input", str(source), "--source-url", SOURCE_URL)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "FORBIDDEN_IO" not in result.stderr
    record = json.loads(result.stdout)
    assert record["source"]["id"] == "900001"
    assert record["source"]["url"] == SOURCE_URL
    assert [row["quantity_text"] for row in record["ingredients"]] == ["1/2개", "1줌", "약간", None]
    assert record["steps"][0]["tips"] == ["두께는 일정하게 유지한다."]
    assert any(finding["code"] == "missing_quantity" for finding in record["findings"])
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original
    assert list((tmp_path / "workspace").iterdir()) == []
    assert sorted(path.name for path in tmp_path.iterdir()) == ["source.html", "workspace"]


def test_parse_command_missing_file_is_an_input_error_not_unknown_command(run_tool, tmp_path):
    source = tmp_path / "missing-source.html"
    result = run_tool("parse", "--input", str(source), "--source-url", SOURCE_URL)
    assert result.returncode != 0
    assert source.name in result.stdout + result.stderr
    assert "FORBIDDEN_IO" not in result.stderr
    assert not source.exists()


@pytest.mark.parametrize("html", ["", "<html><body>not a recipe</body></html>"])
def test_parse_command_reports_invalid_content_and_preserves_the_input(run_tool, tmp_path, html):
    source = tmp_path / "invalid-source.html"
    source.write_text(html, encoding="utf-8")
    result = run_tool("parse", "--input", str(source), "--source-url", SOURCE_URL)
    assert result.returncode != 0
    assert "parse" in (result.stdout + result.stderr).lower()
    assert "No such command" not in result.stdout + result.stderr
    assert source.read_text(encoding="utf-8") == html
    assert "FORBIDDEN_IO" not in result.stderr
