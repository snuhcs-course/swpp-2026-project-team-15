# AI-generated initial implementation with Codex (GPT-6), 2026-11-06; reviewed by Ahyoon Choi.

"""Tests for generated review HTML, saved candidates, and escaping of untrusted text."""

import json
from datetime import UTC, datetime, timedelta

from models import Recipe
from sheet import build_sheet


def _write_cache(path, hits, *, fetched_at=None):
    """Write a query-matched cache fixture so sheet behavior is independent of the Pixabay API."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "fetched_at": (fetched_at or datetime.now(UTC)).isoformat(),
                "query": "soup",
                "lang": "ko",
                "hits": hits,
            }
        ),
        encoding="utf-8",
    )


def test_sheet_escapes_recipe_and_pixabay_text(tmp_path):
    """Escape names, tags, and URLs before inserting them into HTML text and attribute contexts."""
    cache_dir = tmp_path / "cache"
    _write_cache(
        cache_dir / "1.json",
        [
            {
                "id": 3,
                "pageURL": 'https://pixabay.test/item?x=" onmouseover="alert(1)',
                "webformatURL": "https://images.test/a.jpg?x=1&y=2",
                "tags": "<script>alert('x')</script>",
                "user": "Artist <One>",
                "user_id": 2,
                "imageWidth": 800,
                "imageHeight": 600,
            }
        ],
    )
    output = tmp_path / "html" / "review.html"

    build_sheet(1, [Recipe(1, '<script>alert("recipe")</script>', "soup")], cache_dir, output)
    page = output.read_text(encoding="utf-8")

    assert '<script>alert("recipe")</script>' not in page
    assert "&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;" in page
    assert "Artist &lt;One&gt;" in page
    assert "?x=1&amp;y=2" in page
    assert '" onmouseover="alert(1)' not in page


def test_sheet_contains_export_and_restores_selection_by_batch(tmp_path, monkeypatch):
    """Include CSV export, stable batch localStorage state, filename, and the select-none option."""
    monkeypatch.setenv("PIXABAY_KEY", "secret-test-key")
    cache_dir = tmp_path / "cache"
    _write_cache(cache_dir / "4.json", [])
    output = tmp_path / "sheet.html"

    build_sheet(4, [Recipe(4, "Soup", "soup")], cache_dir, output)
    page = output.read_text(encoding="utf-8")

    assert "Export CSV" in page
    assert "localStorage.getItem(key)" in page
    assert "recipe-images-batch-04" in page
    assert "selected_04.csv" in page
    assert 'value="" data-recipe="4"' in page
    assert "if(x.value)rows.push" in page
    assert "secret-test-key" not in page


def test_sheet_marks_empty_and_expired_candidate_caches(tmp_path):
    """Show the no-candidates message for empty or expired results.

    An expired cache must not render candidates even if its stored JSON still contains hits.
    """
    cache_dir = tmp_path / "cache"
    _write_cache(cache_dir / "1.json", [])
    _write_cache(
        cache_dir / "2.json",
        [{"id": 99}],
        fetched_at=datetime.now(UTC) - timedelta(hours=25),
    )
    output = tmp_path / "sheet.html"

    build_sheet(1, [Recipe(1, "Empty", "soup"), Recipe(2, "Expired", "soup")], cache_dir, output)
    page = output.read_text(encoding="utf-8")

    assert page.count("No candidates found.") == 2
