import json
from datetime import UTC, datetime, timedelta

import pytest

from recipe_images.models import Recipe, load_recipes
from recipe_images.search import _pixabay_key, read_cache
from recipe_images.sheet import build_sheet


def test_cache_is_valid_until_24_hour_boundary(tmp_path):
    now = datetime.now(UTC)
    path = tmp_path / "1.json"
    path.write_text(json.dumps({"fetched_at": (now - timedelta(hours=24)).isoformat(),
                               "query": "soup", "lang": "ko", "hits": []}))
    assert read_cache(path, "soup", now) is None
    path.write_text(json.dumps({"fetched_at": (now - timedelta(hours=23, minutes=59)).isoformat(),
                               "query": "soup", "lang": "ko", "hits": []}))
    assert read_cache(path, "soup", now) == []
    assert read_cache(path, "soup", now, lang="en") is None


def test_pixabay_key_uses_environment_then_dotenv(tmp_path, monkeypatch):
    env_file = tmp_path / "server" / ".env"
    env_file.parent.mkdir()
    env_file.write_text('OTHER=value\nPIXABAY_KEY="from-file"\n', encoding="utf-8")
    # Exercise the dotenv parsing without reading the developer's real secret file.
    from recipe_images import search

    monkeypatch.setattr(search, "__file__", str(tmp_path / "server" / "recipe_images" / "src" / "recipe_images" / "search.py"))
    monkeypatch.delenv("PIXABAY_KEY", raising=False)
    assert _pixabay_key() == "from-file"
    monkeypatch.setenv("PIXABAY_KEY", "from-process")
    assert _pixabay_key() == "from-process"


def test_recipe_validation_rejects_duplicate_and_long_queries(tmp_path):
    path = tmp_path / "recipes.json"
    path.write_text(json.dumps([{"id": 1, "name_ko": "A", "query": "a"},
                                {"id": 1, "name_ko": "B", "query": "b"}]))
    with pytest.raises(ValueError, match="duplicate"):
        load_recipes(path)
    path.write_text(json.dumps([{"id": 1, "name_ko": "A", "query": "x" * 101}]))
    with pytest.raises(ValueError, match="100"):
        load_recipes(path)


def test_sheet_has_export_and_does_not_contain_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("PIXABAY_KEY", "secret-test-key")
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "1.json").write_text(json.dumps({"fetched_at": datetime.now(UTC).isoformat(),
        "query": "soup", "lang": "ko", "hits": [{"id": 3, "pageURL": "https://pixabay.com/",
        "webformatURL": "https://example.test/a.jpg", "tags": "food", "user": "A", "user_id": 2,
        "imageWidth": 800, "imageHeight": 600}]}))
    output = tmp_path / "sheet.html"
    build_sheet(1, [Recipe(1, "Soup", "soup")], cache, output)
    page = output.read_text(encoding="utf-8")
    assert "Export CSV" in page and "localStorage" in page
    assert "secret-test-key" not in page
