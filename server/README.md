# Server

FastAPI serves ingredient recognition and dish suggestions. There is no recipe database: dishes come from one self-authored file, `app/dishes/dishes.json` (dish names and categories; no recipe text). The suggestion path uses only the names; the other fields are listed below. Other versions of the app live on other branches/commits (for example the recipe-database version on `main`).

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
| `POST /dishes/suggest` | `{ "ingredients": ["김치", "쌀"] }` → every dish the model finds cookable (best first, no fixed count, possibly none), each with `have`, `missing`, cached `videos` and a YouTube `search_url` |
| `POST /dishes/adapt` | `{ "dish_id": "...", "ingredients": [...], "missing": [...] }` → for each missing ingredient a substitute from the user's own ingredients, when the model finds one |
| `GET /recipes/ingredients` | `{ "names": [...] }` for entry completion (names from the dish data; the path is kept for the app) |
| `POST /dishes/recipe` | `{ "dish_id", "ingredients" }` → the stored recipe with `owned` / `assumed` / `unavailable` per ingredient (404 without a stored recipe); `GET /dishes/{id}/recipe` returns the recipe alone |
| `POST /dishes/revise` | `{ "dish_id", "ingredients" }` → `status` `revised` (with `revised` and `changes`, each with a reason and the source rows and steps it touches), `refused` (with a reason) or `failed` (the server check rejected the model's answer); one model call, none when nothing is missing |
| `POST /dishes/videos` | `{ "dish_id" }` → embeddable YouTube videos for the dish (`video_id`, `title`, `channel`, `thumbnail_url`), a search link and `source` (`stored` or `discovered`) |
| `POST /recipes/ingredient-suggestions` | `{ "ingredients": [...] }` → ingredients that would complete the most dishes |

- **suggest**: the naive design. The model gets the dish names and the user's ingredients and answers `{dishes:[{name, have, missing}]}`. The server only drops names that are not in the list and repeated names, keeps the order and returns `have`/`missing` as written (trimmed). `source` is always `llm`. 502 when the model call fails or no key is set: there is no rules fallback. If the answer is cut at the 4096-token limit (the model may list many dishes), the complete dishes before the cut are kept, since the list is best first; a cut before the first complete dish is a 502. A 429 from the model service is retried twice (after 3 s and 8 s). Its quality is measured in `research/experiments/dish_naive/`.
- **adapt**: the model names, for each missing ingredient, a substitute taken from the user's ingredients or none; the server checks only the JSON shape and that the substitute is one of them. 422 for an unknown dish, 502 when the model call fails. An empty answer says so (`냉장고 재료로는 마땅한 대체를 찾지 못했어요.`).
- **Fields of `dishes.json`**: `name` and `category` feed the model and `GET /dishes`. `key_ingredients`, `optional`, `aliases`, `equivalents` and `substitutes` (and `staples.json`) are no longer used by suggest/adapt; they remain only for the ingredient endpoints below (`/recipes/ingredients`, `/recipes/ingredient-suggestions`) and for the reference set of the naive study.
- **videos**: found when the user opens a dish. One call to a web-search model (`google/gemini-2.5-flash-lite:online`) asks for videos to follow along and cook the dish (wording D0 of [round 3](../research/experiments/dish_pipeline/README.md)); one batched YouTube `videos.list` call keeps those that exist, are public and can be embedded, in the model's order. No title filter, no ranking by views, no count limit; an empty list is possible and the app then shows the search link. Results are kept in memory for 24 hours. 502 when the model or YouTube call fails, or a key is missing.

## Settings

| Variable | Effect |
| --- | --- |
| `VISION_PROVIDER` | `mock` (default), `gemini` (`GEMINI_API_KEY`, `GEMINI_MODEL`) or `openrouter` (`OPENROUTER_API_KEY`, `OPENROUTER_VISION_MODEL`) |
| `OPENROUTER_API_KEY` / `DISH_LLM_API_KEY` | Key of the dish model; without a key suggest/adapt answer 502 |
| `DISH_LLM_MODEL` | Default `google/gemini-2.5-flash-lite` |
| `DISH_RECIPES` | Path of the recipe file `{"schema": 1, "recipes": {dish_id: recipe}}`; without it no dish has a recipe (`has_recipe` is false and the app hides the recipe button) |
| `DISH_VIDEOS` | Path of a video snapshot `{"schema": 1, "dishes": {dish_id: {"fetched_at": ISO time, "videos": [{"id": ...}]}}}` (written by `research/experiments/dish_recipes/collect_videos.py`); optional, an unreadable or invalid file stops the server at startup |
| `YOUTUBE_API_KEY` | YouTube Data API v3 key for `/dishes/videos` (`videos.list`, about 1 quota unit per call); without it the endpoint answers 502 |

## Videos from YouTube

A dish with a stored entry younger than 30 days (the API terms do not allow keeping API data longer) is served from it, after one batched `videos.list` call has confirmed that each video still exists, is public and can be embedded; the rest are dropped, the stored order is kept, and titles and thumbnails come from that fresh response. When the entry is missing, too old or nothing is left, the model proposes videos as described above. The server sends only IDs, titles, channel names and thumbnail URLs that the YouTube API returned, and keeps them in memory for 24 hours (API data may be stored for a limited time only; check the current YouTube API terms). The app shows "Videos provided by YouTube" with links to the YouTube Terms of Service and the Google Privacy Policy and plays videos with the embedded player.

## Tests

From `server/`: `uv run pytest` (offline: fake model and YouTube transports, no network). `tests/experiments` holds the tests of the research tools; those that target the recipe-database version skip here.

## Runtime archive

`python3 scripts/package_server.py` at the repository root builds a runtime-only archive from committed source (no tests, credentials or evaluation tools). Extract it, run `uv sync --locked --no-dev` in `server/`, set the variables above and start `uv run --locked --no-dev uvicorn app.main:create_app_from_env --factory --host 0.0.0.0 --port 8000`.
