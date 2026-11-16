# Server

FastAPI serves ingredient recognition and dish suggestions. There is no recipe database: dishes come from one self-authored file, `app/dishes/dishes.json` (dish names, categories, key ingredients, equivalent and substitute names; no recipe text). Other versions of the app live on other branches/commits (for example the recipe-database version on `main`).

## Run locally

```bash
cd server
uv sync --locked
cp .env.example .env            # VISION_PROVIDER=mock needs no key and makes no network call
uv run --env-file .env uvicorn app.main:create_app_from_env --factory --port 8000
```

Interactive OpenAPI documentation is at `/docs`. `GET /health` is liveness; `GET /ready` checks that the dish list is loaded.

## Endpoints

| Endpoint | Purpose |
| --- | --- |
| `POST /analyze` | One photo (`image`) or 2–15 views of one fridge (`images`) → ingredient candidates (OpenRouter, Gemini or recorded fixtures) |
| `GET /dishes` | The baseline dish list |
| `POST /dishes/suggest` | `{ "ingredients": ["김치", "쌀"] }` → every fitting dish (best first, no fixed count; `limit` is deprecated and ignored), each with `have`, `missing`, a short `reason`, cached `videos` and a YouTube `search_url` |
| `POST /dishes/adapt` | `{ "dish_id": "...", "ingredients": [...] }` → substitutes or skips for the missing ingredients |
| `GET /recipes/ingredients` | `{ "names": [...] }` for entry completion (names from the dish data; the path is kept for the app) |
| `POST /recipes/ingredient-suggestions` | `{ "ingredients": [...] }` → ingredients that would complete the most dishes |

- **suggest**: an LLM chooses dishes from the closed list (ids only from the list); `have` and `missing` are recomputed from the key ingredients, never taken from the model. `source` is `llm`, or `rules` when no model key is set or the call fails (overlap ranking). Equivalent names (계란/달걀, 쌀/밥, …) and the assumed seasonings in `app/dishes/staples.json` do not count as missing.
- **adapt**: a substitution is accepted only if the pair (missing → ingredients used) is in the table of `dishes.json` and the user owns what it uses; optional ingredients may be skipped; anything else is dropped, and an empty answer says so (`냉장고 재료로는 마땅한 대체를 찾지 못했어요.`). 422 for an unknown dish, 502 when the model call fails; without a model key a rules table answers. No quantities or cooking steps are ever produced.
- **Videos**: `videos` come from a cache file (up to three per dish, embeddable, relevant titles first, then views). Without a cache the server returns the search link only.

## Settings

| Variable | Effect |
| --- | --- |
| `VISION_PROVIDER` | `mock` (default), `gemini` (`GEMINI_API_KEY`, `GEMINI_MODEL`) or `openrouter` (`OPENROUTER_API_KEY`, `OPENROUTER_VISION_MODEL`) |
| `OPENROUTER_API_KEY` / `DISH_LLM_API_KEY` | Key of the dish model; without any key the rules-only ranking answers |
| `DISH_LLM_MODEL` | Default `google/gemini-2.5-flash-lite` |
| `DISH_VIDEO_CACHE` | Path of the video cache file; re-read when it changes |
| `DISH_DATA_FILE`, `DISH_STAPLES_FILE` | Another dish list / staples list |

## Videos from YouTube

`python -m app.dishes.prefetch --cache data/dish-videos.json --max-requests 120` prints the plan (a dry run); `--live` calls the YouTube Data API with `YOUTUBE_API_KEY` (or `~/.config/mylittlechef/youtube.env`). A search costs 100 quota units and a video lookup 1, against a default of 10,000 units a day, so 130 dishes take two days. On the Compose host use `deploy/dish-cache.sh` ([deploy README](../deploy/README.md)). The cache holds YouTube API data: check the YouTube API terms (storage time, attribution, player rules) before deploying it; entries older than 30 days are ignored.

## Tests

From `server/`: `uv run pytest` (offline: fake model and YouTube transports, no network). `tests/experiments` holds the tests of the research tools; those that target the recipe-database version skip here.

## Runtime archive

`python3 scripts/package_server.py` at the repository root builds a runtime-only archive from committed source (no tests, credentials or evaluation tools). Extract it, run `uv sync --locked --no-dev` in `server/`, set the variables above and start `uv run --locked --no-dev uvicorn app.main:create_app_from_env --factory --host 0.0.0.0 --port 8000`.
