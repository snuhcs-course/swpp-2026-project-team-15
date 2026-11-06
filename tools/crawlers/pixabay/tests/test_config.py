# AI-generated initial implementation with Codex (GPT-6), 2026-11-06; reviewed by Ahyoon Choi.

"""Tests for dotenv/process environment precedence and Pixabay path configuration."""

import config
import pytest
import search

CONFIG_KEYS = (
    "PIXABAY_KEY",
    "PIXABAY_RECIPES_FILE",
    "PIXABAY_CACHE_DIR",
    "PIXABAY_SHEETS_DIR",
    "PIXABAY_SELECTIONS_DIR",
    "PIXABAY_DOWNLOADS_DIR",
    "PIXABAY_IMAGES_DIR",
    "PIXABAY_OUTPUT_DIR",
    "PIXABAY_MAPPING_FILE",
    "PIXABAY_SOURCE_RECIPE_CSV",
    "PIXABAY_OUTPUT_RECIPE_CSV",
    "PIXABAY_IMAGE_URL_PREFIX",
    "PIXABAY_IMAGE_VARIANT",
)


def _isolated_tools_root(tmp_path, monkeypatch):
    """Use a temporary tools/.env and clear inherited variables that could affect config results."""
    tools_root = tmp_path / "tools"
    tools_root.mkdir()
    monkeypatch.setattr(config, "TOOLS_ROOT", tools_root)
    for key in CONFIG_KEYS:
        monkeypatch.delenv(key, raising=False)
    return tools_root


def test_config_uses_default_recipe_images_directory(tmp_path, monkeypatch):
    """Ensure generated images default under server/static/images/recipes.

    The resolved default is outside the tools tree and keeps the public image URL prefix unchanged.
    """
    tools_root = _isolated_tools_root(tmp_path, monkeypatch)

    loaded = config.load_config()

    assert loaded.images_dir == (tools_root / "../server/static/images/recipes").resolve()
    assert loaded.image_url_prefix == "/recipe-images"
    assert loaded.image_variant == "list"


def test_dotenv_values_load_and_process_environment_takes_precedence(tmp_path, monkeypatch):
    """Load values from tools/.env, then confirm process values override both secret and path."""
    tools_root = _isolated_tools_root(tmp_path, monkeypatch)
    (tools_root / ".env").write_text(
        'PIXABAY_KEY="from-file"\nPIXABAY_IMAGES_DIR=images-from-file\n', encoding="utf-8"
    )
    monkeypatch.setenv("PIXABAY_IMAGES_DIR", "images-from-process")
    monkeypatch.setenv("PIXABAY_KEY", "from-process")

    loaded = config.load_config()

    assert loaded.pixabay_key == "from-process"
    assert loaded.images_dir == (tools_root / "images-from-process").resolve()
    assert search._pixabay_key() == "from-process"


def test_relative_and_absolute_paths_resolve_as_expected(tmp_path, monkeypatch):
    """Resolve relative overrides from tools root and preserve absolute path overrides."""
    tools_root = _isolated_tools_root(tmp_path, monkeypatch)
    absolute_path = tmp_path / "outside" / "recipe-images"
    monkeypatch.setenv("PIXABAY_CACHE_DIR", "local-cache")
    monkeypatch.setenv("PIXABAY_IMAGES_DIR", str(absolute_path))

    loaded = config.load_config()

    assert loaded.cache_dir == (tools_root / "local-cache").resolve()
    assert loaded.images_dir == absolute_path


def test_invalid_image_variant_fails_during_configuration_load(tmp_path, monkeypatch):
    """Reject unsupported URL variants before the tool can produce inconsistent asset mappings."""
    _isolated_tools_root(tmp_path, monkeypatch)
    monkeypatch.setenv("PIXABAY_IMAGE_VARIANT", "original")

    with pytest.raises(ValueError, match="thumb, list or detail"):
        config.load_config()
