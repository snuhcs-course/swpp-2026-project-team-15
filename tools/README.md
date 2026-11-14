# Data preparation tools

This directory is a standalone `uv` project for offline data preparation tools. All tools share `tools/pyproject.toml`, `tools/uv.lock`, and `tools/.env`; server dependencies and `server/.env` remain separate. The tools project manages dependencies only and does not build/install the crawler as a package. Tools are not part of the server runtime image.

## Setup

```powershell
cd tools
Copy-Item .env.example .env
uv sync --locked
uv run pytest
```

The Pixabay configuration reads paths from `.env` relative to `tools/`; process environment variables override `.env`. Keep API keys in `.env` or the process environment, never in recipe files or generated pages. The root `.gitignore` excludes `.env` and generated tool data.

## 만개의레시피 quick-recipe plans

The [tenkrecipes tool](crawlers/tenkrecipes/README.md) provides planning, collection,
and offline validation/reporting for 500 source recipes across nine approved
quick-recipe categories, plus offline parsing of saved list/detail HTML.
Offline commands do not contact the site; plan/parse do not write collection files.
Its explicit relative output paths use the caller's current working directory.

```powershell
uv run --locked python -m crawlers.tenkrecipes.cli plan
```

The detail `parse --input source.html --source-url URL` command emits JSON without
changing the input or fetching images. See the tool's schema documentation.
The collector provides explicit `collect --live` (one-page pilot) and
`collect --full --live` (the complete quota plan), including details and validated
thumbnails. `resume --full --live` promotes a compatible pilot; subsequent
`resume --live` remembers full mode. Offline `validate` and `report` check the
saved artifacts and produce a review handoff. See the [run guide](crawlers/tenkrecipes/RUNS.md)
before operator execution. Semantic duplicate review remains required before
production adoption; service import and production integration are outside this tool.
The default tools test command discovers both the Pixabay and tenkrecipes suites.

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
