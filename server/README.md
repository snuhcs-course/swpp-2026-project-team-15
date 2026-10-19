# Recipe Server

FastAPI serves recipe recommendations and ingredient recognition. Recipe data is read from the existing local SQLite database; see [DB setup](db/README.md). The legacy `POST /recipes/recommend` name-based API remains available for compatibility; the integrated Android app uses the ID-based API below.

## Run locally

From the repository root (Bash), install the declared server dependencies and use Mock Revision:

```bash
cd server
uv sync
cp .env.example .env
uv run --env-file .env uvicorn app.main:create_app_from_env --factory
```

`REVISION_PROVIDER=mock` is the default and needs no API key. It returns labeled canned refusals to exercise the integration; these are not AI feasibility judgments. Vision has its own `VISION_PROVIDER` configuration. Keep `mock` for both when running offline. Existing shell environment variables and the launcher's environment-file loading configure the server.

Live Revision requires explicit `REVISION_PROVIDER=live` plus `REVISION_LLM_ENDPOINT`, `REVISION_LLM_MODEL` and `REVISION_LLM_API_KEY` in the server environment. The endpoint must support HTTPS Chat Completions with Structured Outputs. Each selected recipe has one attempt with a 60-second transport timeout, no retry. Keep credentials out of Git and client requests.

## Integrated recommendations

`POST /recipes/recommendations` uses registered normalized ingredient IDs:

```bash
curl -X POST http://127.0.0.1:8000/recipes/recommendations \
  -H 'Content-Type: application/json' \
  -d '{"ingredient_ids":[70,223,32,284,282,313,554,345,9,147],"revision_limit":3}'
```

- `ingredient_ids` is required; duplicates count once, an empty list is valid, and unknown IDs are rejected. IDs must be positive integers. Names and preparation forms are not automatically equated.
- `revision_limit` defaults to 3 and accepts integers 1–5. It limits selected AI attempts, not the returned recipe count. Refusals/failures do not add replacement candidates beyond that selection.
- The response includes **every filtered recipe**, with `recipe_id`, full `original`, `filtering` counts, and `revision`. `assumed_ingredient_ids` contains water (204) only. All other ingredients, including seasonings, must be submitted.
- `revision.status` is `revised`, `refused`, `failed` or `not_attempted`. Revised/refused preserve the parsed `result` (decision, reason, changes and revised recipe). Failed entries have `error`. Unattempted entries have `not_attempted_reason`: `outside_revision_limit` or `shared_failure`.
- `revision_summary` reports `limit`, `selected_count`, `attempted_count` and nullable `stopped_error`. Configuration failures before provider construction produce zero attempts and a shared stopped error.
- Invalid requests return 422; unavailable/incomplete source data returns sanitized 503 before AI calls. Once filtering succeeds, partial or entirely failed AI results still return 200 with the complete list.

The server chooses revision priority by missing count ascending, matched count descending, then recipe ID ascending. The response array has no display-order guarantee; sorting is the client's responsibility. Original quantities/servings and source row IDs are preserved. Generated content is not safety-verified; allergy checks are not included.

## Policy and failures

[`app/recipes/policy.py`](app/recipes/policy.py) holds the injectable initial policy: rule C (`general matches >= 2 OR main matches >= 1`), configurable C thresholds, count exclusions, water ID and revision limits. Other supported experimental rules can be selected through policy injection. This is an initial service policy, not a finalized semantic classification.

Matching uses distinct ingredient IDs per recipe. Source type codes map to main/secondary/seasoning; conflicting rows use main > secondary > seasoning. Resolved seasonings and water are excluded from both matched and missing priority counts. Unknown types remain in total counts but do not satisfy general/main conditions. No global seasoning category is inferred from another recipe. Counting exclusions do not remove original rows or user-owned seasonings from AI inputs.

Errors expose only `code`, `stage`, sanitized `message`, nullable `http_status` and `scope`:

| Scope | Codes | Effect |
| --- | --- | --- |
| Shared | `authentication`, `permission`, `configuration`, `rate_limit`, `quota_exceeded`, `provider_unavailable` | Preserve previous outcomes and stop remaining selected calls in this request |
| Individual | `timeout`, `connection`, `response_format`, `api_error`, `internal` | Mark this recipe failed and continue within the selection |

Stages distinguish `configuration`, `api_request`, `provider_response`, `response_parsing` and `revision`. HTTP 401/403/429/5xx identify shared failures; quota/configuration subtypes use recognized provider codes. An ambiguous 429 is `rate_limit`. Raw provider errors, raw model text, prompts and secrets are not returned in error diagnostics. The independent experiment CLI retains its existing stop-on-first-error policy.

## Offline tests

From `server/`, run `uv run pytest`. Tests inject temporary DBs, Mock LLMs and fake HTTP transports. Interactive OpenAPI documentation is available at `/docs`; The integrated Android app uses the new endpoint through its dedicated RecipeSource adapter.
