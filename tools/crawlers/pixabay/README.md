# Recipe image review CLI

Python 3.11+ workflow for searching Pixabay candidates, generating a local review sheet, and converting reviewed images into app assets. The tool reads its own `tools/.env`; copy `tools/.env.example` there and fill in the credential and paths. It does not read `server/.env`.

```powershell
cd tools
Copy-Item .env.example .env
uv sync --extra dev
$env:PIXABAY_KEY = "your-key"
uv run --directory crawlers/pixabay/src python cli.py search --batch 1
uv run --directory crawlers/pixabay/src python cli.py sheet --batch 1
```

Edit the configured recipes file with recipe IDs, Korean names, and search queries. Open the generated sheet, select candidates, and export the CSV into the configured selections directory. The selection CSV records the candidate's temporary `webformatURL` for traceability; open the linked Pixabay page and manually save the selected image as `{recipe_id}.{jpg|jpeg|png|webp}` in the configured downloads directory. Then run:

```powershell
uv run --directory crawlers/pixabay/src python cli.py process
uv run --directory crawlers/pixabay/src python cli.py map-urls
uv run --directory crawlers/pixabay/src python cli.py recipe-csv
```

`map-urls` writes `recipe_id,image_url` rows for processed files, using `PIXABAY_IMAGE_URL_PREFIX` and the configured variant. `recipe-csv` merges that mapping into a copy of the configured source `Recipe.csv`, setting `main_image_url` to the app URL while preserving the other recipe fields. The default output CSV is under the crawler output directory; change `PIXABAY_OUTPUT_RECIPE_CSV` if the importer should read another path. The tool does not overwrite the source CSV.

The query and language cache is valid for 24 hours. A cache from a different query or language is ignored. `search --force` asks before refreshing recent cache entries. API keys are read from `PIXABAY_KEY` in the process environment or `tools/.env`; never put them in recipe files or generated pages. Process environment values take precedence over `tools/.env`.

Pixabay's API requires caching search results for 24 hours, forbids systematic mass downloads, and says its image URLs are temporary. This workflow uses the API URLs only in the review sheet and leaves the selected image download to a person through the Pixabay page. It stores processed assets locally and uses those local paths in `Recipe.csv`.


## Local app images

The processing command writes variants directly to `PIXABAY_IMAGES_DIR` (default `server/recipe_images/images/`); FastAPI serves that runtime directory at `/recipe-images/{filename}`. The generated mapping uses the configured `PIXABAY_IMAGE_VARIANT` (`list` by default). The server image directory is ignored by Git and must be provisioned on each runtime host.

## Path configuration

All paths in `tools/.env` may be absolute or relative to `tools/`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `PIXABAY_RECIPES_FILE` | `crawlers/pixabay/recipes.json` | Recipe IDs, names, and search terms |
| `PIXABAY_CACHE_DIR` | `crawlers/pixabay/cache` | Cached API results |
| `PIXABAY_SHEETS_DIR` | `crawlers/pixabay/sheets` | Generated review sheets |
| `PIXABAY_SELECTIONS_DIR` | `crawlers/pixabay/selections` | Human-exported selection CSVs |
| `PIXABAY_DOWNLOADS_DIR` | `crawlers/pixabay/downloads` | Manually downloaded originals named by recipe ID |
| `PIXABAY_IMAGES_DIR` | `../server/recipe_images/images` | Processed WebP images served by the app |
| `PIXABAY_OUTPUT_DIR` | `crawlers/pixabay/output` | Attribution, placeholders, and generated CSVs |
| `PIXABAY_MAPPING_FILE` | `crawlers/pixabay/output/recipe_image_urls.csv` | Recipe ID to app URL mapping |
| `PIXABAY_SOURCE_RECIPE_CSV` | `../data/recipes/Recipe.csv` | Existing recipe rows to preserve |
| `PIXABAY_OUTPUT_RECIPE_CSV` | `crawlers/pixabay/output/Recipe.csv` | Schema-ready CSV for DB import |
| `PIXABAY_IMAGE_URL_PREFIX` | `/recipe-images` | Public route prefix stored in `main_image_url` |
| `PIXABAY_IMAGE_VARIANT` | `list` | One of `thumb`, `list`, or `detail` for mapping |
