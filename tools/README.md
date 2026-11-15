# Data preparation tools

This directory is a standalone `uv` project for offline data preparation tools. All tools share `tools/pyproject.toml`, `tools/uv.lock`, and `tools/.env`; server dependencies and `server/.env` remain separate. The tools project manages dependencies only and does not build/install the crawler as a package. Tools are not part of the server runtime image.

## Setup

```powershell
cd tools
Copy-Item .env.example .env
uv sync --locked
uv run pytest
```

For Pixabay, paths in `.env` can be absolute or relative to `tools/`. Process environment variables override `.env`. Keep API keys in `.env` or the process environment, never in recipe files or generated pages. The root `.gitignore` excludes `.env` and generated tool data.

## Recipe title worksheet

The independent `recipe_dedup` tool currently exports a title worksheet only.
It reads a locally supplied collection's `manifest.json` and selected recipe JSON
files, without importing the collector, reading `.env`, or making network calls.
No collector installation or server configuration is required.

From `tools/`, after the shared setup above (copying `.env` is unnecessary for
this command):

```powershell
uv run --locked python -m recipe_dedup.cli titles --source-run ../data/tenkrecipes/runs/pilot-three-per-category-20261114-181617 --output ../data/tenkrecipes/preparation/titles.csv
```

Replace the paths with the supplied run and a new destination outside that run.
The input manifest must list ordered `allocations` with string `source_id` values
and `details[id].record.path` entries pointing to JSON files inside the run. Each
selected record must contain the matching `source.id` and its original `title`.
Unselected files are ignored; the selection does not have to contain 500 records.
Title export does not decode or copy images.

The UTF-8 BOM CSV contains exactly:

```csv
source_id,original_title,normalized_title
```

Edit **only `normalized_title`** manually. Preserve IDs as text and leave original
titles unchanged. Commas, quotes, whitespace and embedded newlines in original
titles are preserved using CSV quoting. The tool does not suggest normalized
titles or remove duplicate names. Keep the completed worksheet separate from the
source collection and pass both to subsequent preparation work.

Existing output files are refused so rerunning cannot erase manual edits; choose
a new output filename if another blank worksheet is needed. Invalid selected
records, duplicate IDs, identity mismatches or escaping record paths fail before
the output directory is created. Failures return a nonzero exit code and identify
the affected source ID when available. The collection files remain unchanged.

Duplicate grouping, decision worksheets and selected-data export are later
stages and are not implemented yet. The tool and tests can be preserved on the
data-preparation branch without merging to main. Actual data and worksheets are
supplied separately and should remain outside Git.

Run the tests from `tools/`:

```powershell
uv run --locked --offline pytest recipe_dedup/tests -q
uv run --locked --offline pytest -q
uv run --locked --offline ruff check recipe_dedup
uv run --locked --offline ruff format --check recipe_dedup
```

The default test command includes both Pixabay and recipe title tests. Title
tests use synthetic runs and block networking and collector/server imports.

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
