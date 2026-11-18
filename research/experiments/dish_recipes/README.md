# Dish recipe data tools

Question: can the dish list be backed by a structured recipe per dish, restructured from the captions of the videos the app already shows? This directory holds the data tools only: a snapshot of the video lookup per dish, the caption fetch, the target schema and a validator. It makes no recipe and runs no restructuring model.

| Path | Content |
| --- | --- |
| `collect_videos.py` | Stage A: one on-demand video lookup per dish (the server's `VideoFinder`: model proposal, then one batched YouTube lookup keeping existing, public, embeddable videos in the model's order), plus running time and view count of the kept videos |
| `collect_captions.py`, `captions.py` | Stage B: caption text of the first usable video per dish (up to four tried), through an unofficial route |
| `schema.json`, `validate_recipe.py` | Stage C: target structure of a restructured recipe and its checks |
| `coverage.py` | Counts of dishes with videos, with captions and without |
| `../../../server/tests/experiments/dish_recipes/` | Offline tests (fakes only) |

## Outputs stay local

Everything the tools write goes to `data/dish-recipes/` at the repository root, which git ignores: `dish-videos.json` (snapshot), `inputs/<dish>.json` (caption text), `inputs/_missing.json`, `coverage.json`. Video titles, caption text and recipes restructured from them are third-party content and are never committed.

## Unofficial caption route (risk)

The YouTube Data API returns caption text only to the video's owner. Stage B instead uses the `youtube-transcript-api` package, which reads the caption track the web player uses. It runs through `uv run --with youtube-transcript-api` (a temporary environment, no global install). Risks: it may conflict with the YouTube terms, it can break or be blocked without notice, and the text is auto-generated speech recognition (errors in cooking terms and amounts are common). The fetch is polite (one request at a time, 2 s pause) and stops at the first sign of blocking. It is a demo-only tool; the legal question is open.

## Run

```sh
cd server && uv sync --locked
export PYTHONPATH=.:../research
# A: video snapshot (model + YouTube calls; budget 160 model calls, $1.5; dry run without the flag)
uv run python -m experiments.dish_recipes.collect_videos --allow-live-api
# B: captions
uv run --with youtube-transcript-api python -m experiments.dish_recipes.collect_captions --allow-network
# report
uv run python -m experiments.dish_recipes.coverage
# check a restructured recipe against its captions
uv run python -m experiments.dish_recipes.validate_recipe data/dish-recipes/recipes/<dish>.json
```

`validate_recipe` reads the captions from `data/dish-recipes/inputs/<dish_id>.json` (or `--input FILE`). A recipe is valid when it fits `schema.json`, its steps are numbered 1..n and at most 300 characters each and mostly Korean, and every ingredient name appears in the captions (spaces ignored, exact synonyms accepted) or is listed under `uncertain`. Grounding is by name only; amounts and step order are not checked against the captions.

## Limits

One dish gets one video's captions; that video is the model's first usable proposal, not a verified good recipe. Auto captions can be wrong or incomplete (`caption_gaps`). The validator checks form and ingredient grounding, not cooking correctness.
