# Data preparation tools

This directory is a standalone `uv` project for offline data preparation tools. All tools share `tools/pyproject.toml`, `tools/uv.lock`, and `tools/.env`; server dependencies and `server/.env` remain separate. The tools project manages dependencies only and does not build/install the crawler as a package. Tools are not part of the server runtime image.

## Setup

```powershell
cd tools
Copy-Item .env.example .env
uv sync --locked
uv run pytest
```

Paths in `.env` can be absolute or relative to `tools/`. Process environment variables override `.env`. Keep API keys in `.env` or the process environment, never in recipe files or generated pages. The root `.gitignore` excludes `.env` and generated tool data.

## Reviewed ingredient ID mapping

`recipe_ingredients.mapping.build_mapping` validates local selected recipes,
reviewed ingredient decisions and `Ingredient.csv`, and returns an ID plan in
memory. It does not write CSVs, create `_old` backups, normalize recipe copies or
register ingredients in a database. These publication and transformation steps
belong to later tasks. No `.env`, network, collector, dedup tool or server setup
is required.

From `tools/`, after `uv sync --locked`, use the Python API:

```python
from pathlib import Path
from recipe_ingredients.mapping import build_mapping

preparation = Path("../data/tenkrecipes/preparation")
plan = build_mapping(
    preparation / "selected-02/selected-recipes.json",
    preparation / "ingredient-normalization/manual-decisions.json",
    Path("../data/recipes/Ingredient.csv"),
)
print(len(plan["catalog"]), len(plan["mappings"]))
```

The selected JSON contains `recipes`, with each item's string `source_id`
matching `recipe.source.id`, and ordered `recipe.ingredients` rows containing
`group`, positive integer `order`, and nonblank `name_raw`. Original quantities,
notes, source material IDs and recipe data remain unchanged. Repeated ingredients
may share a name; each original group/order identity must remain distinct.

The reviewed JSON contains `decisions` with unique `name_raw` keys. Supported
dispositions are `reuse_existing`, `new_requested`, `split_existing`,
`exclude_non_ingredient`, `exclude_prepared_component`, `excluded_recipe_only`,
`hold`, and `unresolved`. Active rows cannot use the last three dispositions.
Reuse targets require the exact catalog ID and `normalized_name`; new names
require an unassigned ID and a nonblank canonical name. Splits require at least
two distinct valid existing targets. Only explicitly supplied decisions apply;
source material IDs, prose notes and Markdown worksheets cannot supply new rules.
Synchronize manual Markdown edits to reviewed JSON before running the planner.

When present, `counts`, per-decision `active_occurrences`/`active_recipe_count`,
and `active_selection` counts and byte `sha256` must match the selected input.
Inactive historical decisions are kept in the plan without allocating unused
new IDs. A planning error raises `ValueError` without changing any input file.

The returned `catalog` keeps existing rows and appends active new names in Python
string sort order above the maximum existing ID. For example, with existing IDs
7/Salt and 2/Water, new canonical names Apple and Zebra receive 8 and 9, regardless
of decision order; aliases approved as Apple share 8. `mappings` has raw name,
disposition, active counts and zero/one/multiple integer ID/name `targets` in raw
name sort order. An inactive new name or exclusion has no targets. The return
also contains unchanged parsed `selected`/`reviewed` data and `input_hashes`.

For the current supplied inputs, the read-only plan contains 669 catalog entries
(560 existing and 109 new IDs, 561–669), 591 mappings and 589 active raw names.
These are results for this snapshot, not fixed input limits or published IDs.
Existing ingredient names, including 115/닭, are not renamed.

Run the mapping tests from `tools/`:

```powershell
uv run --locked --offline pytest recipe_ingredients/tests -q
uv run --locked --offline pytest -q
uv run --locked --offline ruff check recipe_ingredients
uv run --locked --offline ruff format --check recipe_ingredients
```

The default pytest configuration includes these tests alongside Pixabay tests.

## Pixabay recipe images

The Pixabay workflow searches candidate images, builds a human review sheet, processes selected local images into WebP variants, and writes the mapping and DB-ready `Recipe.csv`.

```powershell
uv run --directory crawlers/pixabay/src python cli.py --help
uv run --directory crawlers/pixabay/src python cli.py search --batch 1
uv run --directory crawlers/pixabay/src python cli.py sheet --batch 1
```

Edit the configured recipe list if search names or terms need changes. Select candidates in the generated sheet and export the CSV into the configured selections directory. The CSV preserves the candidate's temporary `webformatURL` for traceability. Open the Pixabay page and manually save the chosen image as `{recipe_id}.{jpg|jpeg|png|webp}` in the configured downloads directory. Then run:

```powershell
uv run --directory crawlers/pixabay/src python cli.py process
uv run --directory crawlers/pixabay/src python cli.py map-urls
uv run --directory crawlers/pixabay/src python cli.py recipe-csv
```

`process` writes the three app-sized WebP variants and attribution metadata. `map-urls` writes `recipe_id,image_url` rows for processed selections using the configured URL prefix and variant. `recipe-csv` merges those URLs into a copy of the source `Recipe.csv`, setting `main_image_url` while preserving other columns. It writes to a separate output file and does not overwrite the source.

Pixabay search results must be cached for 24 hours. The API's returned image URLs are temporary, and Pixabay disallows systematic mass downloads. This workflow therefore leaves downloading to a person through the selected Pixabay page. The app image directory must be provisioned on each server host.

### Pixabay configuration

All paths are set in `tools/.env`; defaults are relative to `tools/`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `PIXABAY_KEY` | empty | Pixabay API key |
| `PIXABAY_RECIPES_FILE` | `crawlers/pixabay/recipes.json` | Recipe IDs, names, and search terms |
| `PIXABAY_CACHE_DIR` | `crawlers/pixabay/cache` | Cached API results |
| `PIXABAY_SHEETS_DIR` | `crawlers/pixabay/sheets` | Generated review sheets |
| `PIXABAY_SELECTIONS_DIR` | `crawlers/pixabay/selections` | Human-exported selection CSVs |
| `PIXABAY_DOWNLOADS_DIR` | `crawlers/pixabay/downloads` | Manually downloaded originals, named by recipe ID |
| `PIXABAY_IMAGES_DIR` | `../server/static/images/recipes` | Processed WebP images served by the app |
| `PIXABAY_OUTPUT_DIR` | `crawlers/pixabay/output` | Attribution and generated CSVs |
| `PIXABAY_MAPPING_FILE` | `crawlers/pixabay/output/recipe_image_urls.csv` | Recipe ID to app URL mapping |
| `PIXABAY_SOURCE_RECIPE_CSV` | `../data/recipes/Recipe.csv` | Existing recipe rows to preserve |
| `PIXABAY_OUTPUT_RECIPE_CSV` | `crawlers/pixabay/output/Recipe.csv` | Schema-ready CSV for DB import |
| `PIXABAY_IMAGE_URL_PREFIX` | `/recipe-images` | Public URL prefix for `main_image_url` |
| `PIXABAY_IMAGE_VARIANT` | `list` | `thumb`, `list`, or `detail` mapping variant |

The repository CI runs tools lint, formatting, and tests only when `tools/**` or the CI workflow changes.
