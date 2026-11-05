# Data preparation tools

This directory is a standalone `uv` project for offline data preparation and review tools. It has its own `pyproject.toml` and `uv.lock`; server dependencies remain isolated in `server/`.

```powershell
cd tools
Copy-Item .env.example .env
uv sync --extra dev --locked
uv run --directory crawlers/pixabay/src python cli.py --help
uv run pytest
```

The Pixabay image workflow is in `crawlers/pixabay/`. Set its API key and paths in `tools/.env`; this is separate from `server/.env`. The tools project manages dependencies only; the crawler is run directly from its source directory without building or installing a package. The repository CI runs its lint, formatting, and tests only when `tools/**` or the CI workflow changes. These tools are not part of the server runtime image.
