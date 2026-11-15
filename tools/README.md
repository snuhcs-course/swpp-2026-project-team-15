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

The independent `recipe_dedup` tool exports title worksheets, duplicate-review
candidates, and separately selected recipe copies after human review.
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

### Duplicate review

After editing the titles, generate review files in a **new directory** outside the
source run, from `tools/`:

```powershell
uv run --locked python -m recipe_dedup.cli groups --source-run ../data/tenkrecipes/runs/pilot-three-per-category-20261114-181617 --titles ../data/tenkrecipes/preparation/titles.csv --output ../data/tenkrecipes/preparation/review-01
```

The command validates selected IDs and original titles before creating output.
Original-title comparison ignores all whitespace (spaces, tabs, and line breaks,
including LF/CRLF); other character differences fail. This tolerance applies only
to original-title validation. Stored values are not rewritten.

- `groups.json`: groups of two or more recipes whose **normalized titles match
  exactly**, across categories. Each recipe includes its source ID, unchanged
  source original title, normalized title, source URL, ingredients and quantities,
  ordered steps and tips, and a thumbnail path relative to the source run.
- `unfinished_ids` and `title_normalization_complete` in that JSON describe title
  completion only. Blank or whitespace-only titles are unfinished and are not
  placed in groups. Spacing, punctuation and Unicode differences in completed
  normalized titles remain distinct.
- `decisions.csv`: one row per selected ID in source order, initially `pending`:

```csv
source_id,decision,duplicate_of,reason
0001,keep,,Different preparation variant retained
2002,keep,,Data quality still needs separate review
3003,exclude,0001,Same dish under a different title
4004,pending,,Ingredient identity needs manual review
```

These IDs are synthetic examples. Edit the generated rows, keeping every source
ID. `keep` retains a recipe **for duplicate review**; it does not approve data
quality or service suitability. Record quality concerns in the reason or a separate
handoff note. `pending` is unresolved review, including recipes needing manual
inspection. Names alone never imply exclusion: two variants with the same title
may both be kept, and different titles may be explicitly marked duplicates.

Each `exclude` needs a nonblank reason and another selected ID marked `keep` as
its direct representative. Self-references, unknown IDs, chains, cycles, missing
rows and references to pending recipes are errors. Keep and pending rows must
leave `duplicate_of` empty. The stage-two Python validator accepts drafts containing
pending decisions and returns validated rows in source order without changing files:

```python
from pathlib import Path
from recipe_dedup.review import read_decisions
from recipe_dedup.titles import read_title_rows

source_run = Path("../data/tenkrecipes/runs/pilot-three-per-category-20261114-181617")
source_ids = [row["source_id"] for row in read_title_rows(source_run)]
decisions = read_decisions(Path("../data/tenkrecipes/preparation/review-01/decisions.csv"), source_ids)
```

The `groups` command always creates an all-pending template; it does not read or
reset existing decisions. After title edits, choose another output directory and
keep the prior decision worksheet separately. Existing output directories are
refused, including partially written output from an I/O failure. A failed command
returns nonzero; only use results from a successful invocation. Images and source
records are never copied or modified, so supply the source run alongside review files.

### Final selection and handoff

The sequence is `titles` → user writes normalized titles → `groups` → user writes
duplicate decisions → `select`. Complete every normalized title and resolve every
pending decision before final export, including titles on excluded rows. Do not
mark pending rows keep merely to make export succeed. Use the retained
`review-notes.md`, if supplied, when making decisions; the tool does not infer
decisions from prose notes.

From `tools/`, export the completed worksheets to a **new directory**:

```powershell
uv run --locked python -m recipe_dedup.cli select --source-run ../data/tenkrecipes/runs/pilot-three-per-category-20261114-181617 --titles ../data/tenkrecipes/preparation/titles.csv --decisions ../data/tenkrecipes/preparation/review-01/decisions.csv --output ../data/tenkrecipes/preparation/selected-01
```

If any title is blank, any decision is pending, or a mapping/decision is invalid,
the command exits nonzero before creating the output directory and reports the
unresolved IDs. Existing outputs are refused. After changing titles or decisions,
choose a new destination such as `selected-02`; previous results remain unchanged.
The same validated inputs produce the same semantic result without recollection.

Successful output contains exactly two UTF-8 JSON files:

- `selected-recipes.json`: `source_run_id` and `recipes` containing only keep IDs
  in original source order. Each item has `source_id`, the source `original_title`,
  `thumbnail_path` relative to the source run, and a `recipe` copy. Only that copy's
  `title` changes to the exact user-authored normalized title. Source identity/URL,
  ingredient IDs, quantities, steps, tips and other recipe fields remain unchanged.
- `selection-report.json`: source run ID, input/kept/excluded counts and IDs, and
  every reviewed CSV row with its decision, representative and reason. Completion
  flags describe title and duplicate review only. `service_suitability_assessed`
  is false; quality concerns recorded on keep rows remain in the report.

Pass both files, the source run (including its local images), and any separate
quality-review notes to the next preparation step. The tool references images; it
does not copy or deploy them. Raw records and excluded recipes remain in the
source run. No automatic quality filter, ingredient normalization, entity/service
CSV generation, image upload or database import runs here. These remain separate
follow-up work even after duplicate review is complete.

The implementation tests use synthetic decisions. Actual recipe selection must
wait for the user's completed titles and decisions; code completion does not mean
the 500 collected recipes have been reviewed. The tool and tests can be preserved
on the data-preparation branch without merging to main. Actual data and worksheets
are supplied separately and should remain outside Git.

Run the tests from `tools/`:

```powershell
uv run --locked --offline pytest recipe_dedup/tests -q
uv run --locked --offline pytest -q
uv run --locked --offline ruff check recipe_dedup
uv run --locked --offline ruff format --check recipe_dedup
```

The default test command includes both Pixabay and recipe preparation tests.
Preparation tests use synthetic runs; CLI checks block networking and collector/server imports.

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
