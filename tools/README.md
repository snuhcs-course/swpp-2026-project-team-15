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

## Recipe entity role review

`recipe_entities` is a standalone offline tool for reviewing normalized ingredient
occurrences before entity conversion. It uses the Python standard library without
loading the collector, normalization tools, server runtime or `.env`.

From `tools/`, after installing the shared dependencies:

```powershell
uv run --locked --offline python -m recipe_entities.cli review --normalized-recipes ../data/tenkrecipes/preparation/ingredients-02/normalized-recipes.json --ingredient-catalog ../data/recipes/Ingredient.csv --output ../data/tenkrecipes/preparation/entity-role-review-new
```

Choose a **new directory**. Existing directories are refused. The command validates
recipe/source identities, catalog IDs and names, preserved source references, split
components and excluded rows before creating output. It writes:

- `ingredient-roles.csv`: UTF-8 BOM worksheet, with initially blank role codes.
- `review-context.json`: input byte hashes, worksheet headers and occurrence keys.

Each row is identified by `(recipe_id, source_occurrence_index, component_index)`.
Repeated ingredient IDs and split ingredients stay separate. Edit only
`ingredient_type_code` and `review_note`; preserve all other fields and context.
The codes are `3060001` (주재료), `3060002` (부재료), and `3060003` (양념).
Different occurrences of the same ingredient may receive different roles.
Recipe group names and existing ingredient roles never approve a classification.

Validate a completed worksheet with:

```powershell
uv run --locked --offline python -m recipe_entities.cli check-review --normalized-recipes ../data/tenkrecipes/preparation/ingredients-02/normalized-recipes.json --ingredient-catalog ../data/recipes/Ingredient.csv --review-dir ../data/tenkrecipes/preparation/entity-role-review-new
```

Every occurrence must have a valid role. Missing, duplicate, extra, edited-context,
unclassified and unknown-code rows fail. A byte change to either input invalidates
the review even if parsed values appear identical. Validation does not rewrite
inputs or decisions. Row order may change; returned decisions follow source order.
An I/O failure can leave partial output: use only a successful result, preserve the
failed directory for inspection and choose a new directory when retrying.

The earlier local HTML review includes additional suggestion columns and a
different context format. Keep that completed worksheet: this command does not
overwrite it or migrate its decisions. Existing human decisions must be explicitly
connected by occurrence identity before a later entity export; no repeat human
review or inferred role is implied by a fresh blank worksheet.

The CLI currently provides `review` and `check-review`. The Python append API
below produces CSVs and provenance; the build CLI and final local DB validation
remain subsequent implementation tasks. Previously generated local datasets are
separate from this reusable tool.

```powershell
uv run --locked --offline pytest recipe_entities/tests -q
uv run --locked --offline ruff check recipe_entities
uv run --locked --offline ruff format --check recipe_entities
```

The default tools test command discovers both Pixabay and entity preparation tests.
Tests use synthetic local inputs.

### Append reviewed entity CSVs (Python API)

After completing a worksheet in the new review format, call from `tools/`:

```python
from pathlib import Path
from recipe_entities.entities import write_entities

summary = write_entities(
    Path("../data/tenkrecipes/preparation/ingredients-02/normalized-recipes.json"),
    Path("../data/recipes/Ingredient.csv"),
    Path("../data/tenkrecipes/preparation/entity-role-review-completed"),
    Path("../data/tenkrecipes/preparation/entities-01/original-csv"),
    Path("../data/tenkrecipes/preparation/entities-new"),
)
```

Replace the worksheet and destination with explicit completed inputs and a new
output. The existing CSV input must be the **pre-append baseline**: the current
`data/recipes` already includes these recipes and will fail with ID collisions.
Do not regenerate or infer the user's prior decisions to bypass validation.

The output has `csv/` with all eight importer inputs and `entity-provenance.json`.
Existing recipe, ingredient relation and step values/IDs remain unchanged. New
recipes keep their source IDs. New recipes are processed in numeric ID order;
relation and step IDs start above the corresponding existing maxima without
reusing gaps. Reordering worksheet rows does not affect output IDs.

Recipe title, description, servings, cooking time and difficulty retain supplied
text. Absent category, cuisine, calories and unpublished image URLs remain NULL.
Legacy Recipe.csv without `main_image_url` receives the column with NULL for old
rows. Relations retain repeated IDs, raw names, quantities and each reviewed role.
Split component quantities remain NULL rather than duplicating the combined amount.
Step order/instructions are preserved; ordered tips are joined with newlines.
Invalid types, ID collisions, catalog identity changes, duplicate step orders and
overlength values fail before creating the output directory; values are not truncated.

The explicit current catalog is copied after checking old ID/name identities.
CookingTool, Allergen, RecipeCookingTool and IngredientAllergen CSVs are copied
byte-for-byte with no inferred rows. Provenance preserves source records, URLs,
thumbnail paths, raw occurrence registry (including excluded rows and split totals),
ingredient notes, step image references, original tips, human decisions and service
ID links. Excluded tool/intermediate rows remain outside required ingredients.

This API **does not create a DB or claim a completed, DB-validated bundle**. An
existing output or output nested inside a CSV/review input is refused. An I/O
failure may leave a partial new directory for inspection. Preserve it and use a
new destination. Inputs and existing results stay unchanged. The subsequent build
stage will run the existing importer and record successful final verification.

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

| Variable                    | Default                                         | Purpose                                           |
| --------------------------- | ----------------------------------------------- | ------------------------------------------------- |
| `PIXABAY_KEY`               | empty                                           | Pixabay API key                                   |
| `PIXABAY_RECIPES_FILE`      | `crawlers/pixabay/recipes.json`                 | Recipe IDs, names, and search terms               |
| `PIXABAY_CACHE_DIR`         | `crawlers/pixabay/cache`                        | Cached API results                                |
| `PIXABAY_SHEETS_DIR`        | `crawlers/pixabay/sheets`                       | Generated review sheets                           |
| `PIXABAY_SELECTIONS_DIR`    | `crawlers/pixabay/selections`                   | Human-exported selection CSVs                     |
| `PIXABAY_DOWNLOADS_DIR`     | `crawlers/pixabay/downloads`                    | Manually downloaded originals, named by recipe ID |
| `PIXABAY_IMAGES_DIR`        | `../server/static/images/recipes`               | Processed WebP images served by the app           |
| `PIXABAY_OUTPUT_DIR`        | `crawlers/pixabay/output`                       | Attribution and generated CSVs                    |
| `PIXABAY_MAPPING_FILE`      | `crawlers/pixabay/output/recipe_image_urls.csv` | Recipe ID to app URL mapping                      |
| `PIXABAY_SOURCE_RECIPE_CSV` | `../data/recipes/Recipe.csv`                    | Existing recipe rows to preserve                  |
| `PIXABAY_OUTPUT_RECIPE_CSV` | `crawlers/pixabay/output/Recipe.csv`            | Schema-ready CSV for DB import                    |
| `PIXABAY_IMAGE_URL_PREFIX`  | `/recipe-images`                                | Public URL prefix for `main_image_url`            |
| `PIXABAY_IMAGE_VARIANT`     | `list`                                          | `thumb`, `list`, or `detail` mapping variant      |

The repository CI runs tools lint, formatting, and tests only when `tools/**` or the CI workflow changes.
