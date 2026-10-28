# Recipe image review CLI

Python 3.11+ workflow for searching Pixabay candidates, generating a local review sheet, and converting originals downloaded manually by a person. It deliberately does not download Pixabay image files.

```powershell
cd recipe-images
py -m pip install -e ".[dev]"
$env:PIXABAY_KEY = "your-key"
recipe-images search --batch 1
recipe-images sheet --batch 1
```

Edit `recipes.json` with recipe IDs, Korean names, and Korean search queries. The current dataset uses each Korean recipe name as its query, and Pixabay searches use `lang=ko`. Open `sheets/sheet_01.html`, select candidates, and export the CSV into `selections/`. Open each selected Pixabay page and manually save its original to `downloads/{recipe_id}.{jpg|jpeg|png|webp}`. Then run `recipe-images process` and `recipe-images status`.

The query and language cache is valid for 24 hours. A cache from a different query or language is ignored. `search --force` asks before refreshing recent cache entries. API keys are read only from `PIXABAY_KEY`; never put them in recipe files or generated pages.

When run from this repository, the CLI also reads `server/.env` if `PIXABAY_KEY` is not already set in the process environment. A process environment value takes precedence. The key is never printed or written to the search cache or generated HTML.
