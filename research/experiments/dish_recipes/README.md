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

## Recipes from the video itself

The caption route stopped when YouTube refused automated caption requests from our address (2026-11-18). This section replaces it with Google's own video input: a Gemini model watches the public YouTube video and writes the recipe.

**What the documentation says (read 2026-11-19).**

- Gemini API, [video understanding](https://ai.google.dev/gemini-api/docs/video-understanding): YouTube URLs can be passed directly ("Pass YouTube URLs"); the feature is a preview, "available at no charge", and "pricing and rate limits are likely to change". Only public videos; the free tier allows at most 8 hours of YouTube video per day, the paid tier has no length limit; Gemini 2.5 and later accept up to 10 videos per request. Frames are sampled at 1 frame per second; a second of video costs about 300 tokens at the default resolution (258 per frame plus 32 for audio), about 100 at low resolution.
- OpenRouter, [video inputs](https://openrouter.ai/docs/features/multimodal/videos): Chat Completions accept a `video_url` content part; "Google Gemini on AI Studio only supports YouTube links (not Vertex AI)", and OpenRouter sends video URLs only to providers that support them. The request therefore pins the provider to Google AI Studio without fallbacks. No media-resolution parameter is documented there, so the provider default is used.

**Feasibility (two calls, `gemini-2.5-flash-lite`, before the study design was fixed).** Both answers came back through Google AI Studio with `finish_reason` stop and a usable recipe: a 252 s video took 74,556 input tokens, 24.5 s and $0.0094; a 464 s video took 137,114 input tokens, 43.5 s and $0.0170. That is about 296 input tokens per second of video, close to the documented default resolution; OpenRouter billed the tokens.

**Study design** (fixed in [`criteria_video.json`](criteria_video.json) before any study call): the 16 dishes that have a caption-based recipe, the same video each, `gemini-2.5-flash-lite` and `gemini-2.5-flash`, one run each. Measured: valid recipe, whether the model says the video cooks the dish, ingredient agreement with the caption-based recipe (names with synonyms merged), ingredients not in the captions (each read by hand: plausible from the screen, invented, or unclear), amounts and servings given, steps, role labels, tokens, cost and latency. No pass/fail thresholds; the choice is a judgement next to the numbers.

| Path | Content |
| --- | --- |
| `video_recipes.py` | Request (YouTube link as a `video_url` part), answer schema, response parsing, conversion to the stored format |
| `run_video_recipes.py` | `study`, `analyze` and `build` (one recipe per dish from the first verified video the model confirms is the dish, at most three tried) |
| `criteria_video.json` | The fixed study design |

Raw answers and recipes go to a working directory outside the repository (`--workdir`); they are third-party-derived and never committed.
