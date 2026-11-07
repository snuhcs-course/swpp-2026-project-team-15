# AI-generated initial implementation with Codex (GPT-6), 2026-11-06; reviewed by Ahyoon Choi.

"""Tests for Pixabay recipe input validation and API hit normalization."""

import json

import pytest
from models import hit_fields, load_recipes


def test_load_recipes_trims_valid_names_and_queries(tmp_path):
    """Accept valid recipe rows and strip accidental whitespace from names and search terms."""
    recipes_file = tmp_path / "recipes.json"
    recipes_file.write_text(
        json.dumps([{"id": 7, "name_ko": "  Soup  ", "query": "  tomato soup  "}]),
        encoding="utf-8",
    )

    recipes = load_recipes(recipes_file)

    assert [(recipe.id, recipe.name_ko, recipe.query) for recipe in recipes] == [
        (7, "Soup", "tomato soup")
    ]


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"id": 1}, "JSON array"),
        (["not an object"], "JSON object"),
        ([{"id": True, "name_ko": "Soup", "query": "soup"}], "id must be an integer"),
        (
            [
                {"id": 1, "name_ko": "A", "query": "a"},
                {"id": 1, "name_ko": "B", "query": "b"},
            ],
            "duplicate",
        ),
        ([{"id": 1, "name_ko": "  ", "query": "soup"}], "name_ko"),
        ([{"id": 1, "name_ko": "Soup", "query": "  "}], "query is required"),
        ([{"id": 1, "name_ko": "Soup", "query": "x" * 101}], "100 characters"),
    ],
)
def test_load_recipes_rejects_invalid_rows(tmp_path, payload, message):
    """Reject malformed collections and invalid row fields with a useful validation error."""
    recipes_file = tmp_path / "recipes.json"
    recipes_file.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_recipes(recipes_file)


def test_load_recipes_reports_missing_and_invalid_json_files(tmp_path):
    """Translate file-system and JSON parse errors into the loader's public ValueError contract."""
    with pytest.raises(ValueError, match="Unable to read recipes file"):
        load_recipes(tmp_path / "missing.json")

    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="Unable to read recipes file"):
        load_recipes(invalid_file)


def test_hit_fields_keeps_known_pixabay_fields_and_fills_missing_values():
    """Keep only fields consumed by review/export.

    Missing API fields should be represented by empty text so later renderers can use them safely.
    """
    hit = {"id": 3, "pageURL": "https://pixabay.test/3", "extra": "discard"}

    normalized = hit_fields(hit)

    assert normalized["id"] == 3
    assert normalized["pageURL"] == "https://pixabay.test/3"
    assert normalized["tags"] == ""
    assert "extra" not in normalized
