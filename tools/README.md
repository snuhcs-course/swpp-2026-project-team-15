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
register ingredients in a database. The transformation API below builds separate
documents; the explicit publication command below handles backups and catalog
replacement. No `.env`, network, collector, dedup tool or server setup is required.

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

### Normalized recipe documents

Use the same three paths with
`recipe_ingredients.normalization.build_documents(selected_path, decisions_path,
catalog_path)`. It returns a dictionary keyed by three intended JSON filenames.
The function validates and builds documents in memory; it creates no files,
backups, catalog changes or database records. For example, after defining the
`preparation` path above:

```python
from recipe_ingredients.normalization import build_documents

documents = build_documents(
    preparation / "selected-02/selected-recipes.json",
    preparation / "ingredient-normalization/manual-decisions.json",
    Path("../data/recipes/Ingredient.csv"),
)
print(documents["validation-report.json"]["output_rows"])
```

- `ingredient-mapping.json` contains the planned `catalog`, `input_hashes`, and
  `mappings`. Each mapping includes the original reviewed decision as `review`,
  preserving reasons, evidence and deferred revision notes without applying them.
- `normalized-recipes.json` preserves selected metadata, recipe order and all
  non-ingredient fields. It adds a `source_occurrences` registry containing each
  source row exactly once as `original`, its `decision`, and its source identity.
  Each retained ingredient keeps all original fields and adds `ingredient_id`,
  `normalized_name`, a one-based `component_index`, and `source`. That reference
  contains `source_id`, original `group`/`order`, and zero-based `occurrence_index`
  into the registry. Repeated rows remain separate even when their IDs match.
- For reviewed splits, each component keeps the original group/order and raw text,
  but its `quantity_text` comes only from the corresponding reviewed target, or
  is null. The combined amount is preserved in the registry's `original` row,
  not assigned to each component. Ordinary missing quantity fields remain absent;
  explicit nulls remain null. No units or amounts are converted or inferred.
- `validation-report.json` records input paths/hashes, catalog counts, source and
  output counts by decision, inactive raw names, split and excluded occurrences,
  missing source quantities and the separate count of split components without
  individual quantities. Missing means absent, null or empty-string source amount.
  Exclusions include their full reviewed evidence. Tool candidates receive no
  service tool ID and do not modify `listed_tools`; made-in-recipe intermediates
  are excluded without modifying their components or steps.

The builder checks that every source occurrence is accounted for, every output
ID/name exists in the planned catalog, and original rows and non-ingredient
metadata are unchanged. Invalid inputs fail before any file is written.
`validation_passed` describes these transformation checks; `catalog_published`
and `service_suitability_assessed` remain false. Backup and publication hashes
are supplied by the publication workflow, not invented by this builder.
Ingredient classification, presentation/allergen metadata, recipe revision,
entity conversion, database import and image deployment remain separate work.
Synthetic tests serialize and reread all three documents to check JSON round trips.

### Preserve CSVs and publish the catalog

From `tools/`, explicitly select all inputs and a **new** output directory:

```powershell
uv run --locked --offline python -m recipe_ingredients.cli --selected ../data/tenkrecipes/preparation/selected-02/selected-recipes.json --decisions ../data/tenkrecipes/preparation/ingredient-normalization/manual-decisions.json --catalog-dir ../data/recipes --output ../data/tenkrecipes/preparation/ingredients-01
```

This command changes local files. Stop other writers to the inputs/catalog while
it runs; input rechecks detect changes but do not lock out concurrent writers.
No `.env` file, API key, server, collector or dedup installation is required.
All four original CSVs must exist in `--catalog-dir`:

| Original | Byte-exact backup | Original after success |
| --- | --- | --- |
| `Ingredient.csv` | `Ingredient_old.csv` | Existing rows plus approved new names |
| `IngredientPresentation.csv` | `IngredientPresentation_old.csv` | Unchanged |
| `IngredientAllergen.csv` | `IngredientAllergen_old.csv` | Unchanged |
| `RecipeIngredient.csv` | `RecipeIngredient_old.csv` | Unchanged |

The command validates inputs and generated references before creating anything.
It refuses existing output paths or any required `_old` destination, including
partial results from an earlier failure. It then writes the mapping/normalized
JSON, rechecks input bytes, creates each backup exclusively, and replaces only
`Ingredient.csv` using a temporary file on the same filesystem. The new catalog
uses UTF-8 BOM, CRLF and the unchanged `ingredient_id,name` header. Existing row
order, IDs and names are retained. Other catalog files are not regenerated.

Only after checking the published catalog, all backups, other originals and JSON
bytes does it finalize `validation-report.json`. A zero exit code and that final
report indicate success. The report adds `catalog_published: true`,
`published_catalog` path/header/SHA256, and `csv_snapshots` keyed by original
filename with original/backup paths and before/backup/after SHA256 values.
`output_hashes` covers the mapping and normalized JSON; the report does not hash
itself. Service suitability remains unassessed. No entity CSV generation,
presentation/allergen inference, Android changes, DB import or image upload runs.

On failure the exit code is nonzero. The error identifies the phase, whether the
catalog changed, and remaining backup/output/temporary paths. Partial outputs
must not be used. A failure after replacement can leave the new catalog in place
without a final report; inspect the stated status and backups before proceeding.
Files already created are deliberately retained for recovery. This is a local
multi-file operation, not a database transaction or resumable job.

To restore the original catalog after inspecting the backups, from `tools/`:

```powershell
Copy-Item -LiteralPath ../data/recipes/Ingredient_old.csv -Destination ../data/recipes/Ingredient.csv
(Get-FileHash -LiteralPath ../data/recipes/Ingredient_old.csv).Hash -eq (Get-FileHash -LiteralPath ../data/recipes/Ingredient.csv).Hash
```

Check the other three originals against their backups too. Preserve the failed
output and backups separately before any retry; changing only `--output` does
not bypass existing `_old` refusal. For a fresh retry, supply a separate catalog
directory containing the four original snapshots under their original filenames,
with no `_old` files, and choose another output directory. There is no force,
automatic backup deletion, rollback or resume option.

Pass the three successful JSON files, updated catalog, four backups, source run
and its referenced images to the next preparation step. Absolute input paths in
the report are audit information, not a substitute for supplying the source files.
Actual data and generated files remain outside Git. Synthetic publication tests
exercise this CLI with disposable catalog files and the same explicit options.

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
