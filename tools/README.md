# Data preparation tools

This directory is a standalone `uv` project for offline data preparation and review tools. It has its own `pyproject.toml` and `uv.lock`; server dependencies remain isolated in `server/`.

```powershell
cd tools
uv sync --extra dev --locked
uv run recipe-images --help
uv run pytest
```

The Pixabay image workflow is in `crawlers/pixabay/`. The repository CI runs its lint, formatting, and tests only when `tools/**` or the CI workflow changes. These tools are not part of the server runtime image.
