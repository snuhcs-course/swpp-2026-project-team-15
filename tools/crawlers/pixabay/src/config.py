"""Load Pixabay tool credentials and paths from tools/.env and the process environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

TOOLS_ROOT = Path(__file__).resolve().parents[3]


def _path(values: dict[str, str], key: str, default: str) -> Path:
    value = values.get(key, "").strip() or default
    path = Path(value).expanduser()
    return path if path.is_absolute() else (TOOLS_ROOT / path).resolve()


@dataclass(frozen=True)
class Config:
    pixabay_key: str | None
    recipes_file: Path
    cache_dir: Path
    sheets_dir: Path
    selections_dir: Path
    downloads_dir: Path
    images_dir: Path
    output_dir: Path
    mapping_file: Path
    source_recipe_csv: Path
    output_recipe_csv: Path
    image_url_prefix: str
    image_variant: str


def load_config() -> Config:
    """Read tools/.env first; process environment values take precedence."""
    values = {
        key: value
        for key, value in dotenv_values(TOOLS_ROOT / ".env", encoding="utf-8").items()
        if value is not None
    }
    values.update(os.environ)
    variant = values.get("PIXABAY_IMAGE_VARIANT", "list").strip()
    if variant not in {"thumb", "list", "detail"}:
        raise ValueError("PIXABAY_IMAGE_VARIANT must be thumb, list or detail")
    return Config(
        pixabay_key=values.get("PIXABAY_KEY") or None,
        recipes_file=_path(values, "PIXABAY_RECIPES_FILE", "crawlers/pixabay/recipes.json"),
        cache_dir=_path(values, "PIXABAY_CACHE_DIR", "crawlers/pixabay/cache"),
        sheets_dir=_path(values, "PIXABAY_SHEETS_DIR", "crawlers/pixabay/sheets"),
        selections_dir=_path(values, "PIXABAY_SELECTIONS_DIR", "crawlers/pixabay/selections"),
        downloads_dir=_path(values, "PIXABAY_DOWNLOADS_DIR", "crawlers/pixabay/downloads"),
        images_dir=_path(values, "PIXABAY_IMAGES_DIR", "../server/recipe_images/images"),
        output_dir=_path(values, "PIXABAY_OUTPUT_DIR", "crawlers/pixabay/output"),
        mapping_file=_path(
            values, "PIXABAY_MAPPING_FILE", "crawlers/pixabay/output/recipe_image_urls.csv"
        ),
        source_recipe_csv=_path(values, "PIXABAY_SOURCE_RECIPE_CSV", "../data/recipes/Recipe.csv"),
        output_recipe_csv=_path(
            values, "PIXABAY_OUTPUT_RECIPE_CSV", "crawlers/pixabay/output/Recipe.csv"
        ),
        image_url_prefix=values.get("PIXABAY_IMAGE_URL_PREFIX", "/recipe-images").rstrip("/"),
        image_variant=variant,
    )
