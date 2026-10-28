# Recipe image review CLI

Python 3.11+ workflow for searching Pixabay candidates, generating a local review sheet, and converting originals downloaded manually by a person. It deliberately does not download Pixabay image files.

```powershell
cd recipe-images
py -m pip install -e ".[dev]"
$env:PIXABAY_KEY = "your-key"
recipe-images search --batch 1
recipe-images sheet --batch 1
```

Edit `recipes.json` with recipe IDs, Korean names, and English queries. Open `sheets/sheet_01.html`, select candidates, and export the CSV into `selections/`. Open each selected Pixabay page and manually save its original to `downloads/{recipe_id}.{jpg|jpeg|png|webp}`. Then run `recipe-images process` and `recipe-images status`.

The query cache is valid for 24 hours. `search --force` asks before refreshing recent cache entries. API keys are read only from `PIXABAY_KEY`; never put them in recipe files or generated pages.
