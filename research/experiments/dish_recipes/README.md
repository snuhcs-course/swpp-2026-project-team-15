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

### Results (2026-11-19, one run per model, 32 calls, $0.88)

| | `gemini-2.5-flash-lite` | `gemini-2.5-flash` |
| --- | --- | --- |
| Answers / valid recipes | 16 / 15 | 16 / 15 |
| "Not the requested dish" | 1 (베이컨볶음밥: the video is a paprika and bacon fried rice) | 1 (same video) |
| Ingredients agreeing with the caption-based recipe: median precision / recall | 0.71 / 0.73 | 0.85 / 0.79 |
| Median ingredients / steps | 13 / 9 | 13 / 12 |
| Ingredients with an amount | 63% | 66% |
| Servings given | 2 of 15 | 7 of 15 |
| Shared ingredients with the same main / non-main label as the caption-based recipe | 96 of 126 (76%) | 125 of 141 (89%) |
| Ingredients not named in the captions | 31 | 42 |
| Cost per video: median / total | $0.013 / $0.20 | $0.040 / $0.67 |
| Latency: median / max | 35 s / 67 s | 19 s / 43 s |

Both models received every video through Google AI Studio. A video costs about 296 input tokens per second (Shorts of 50–60 s cost $0.002–0.009); output is under 1,500 tokens.

**Ingredients not in the captions, read by hand** (title, description and caption context; the video itself was not watched):

| | lite | flash |
| --- | --- | --- |
| In the captions under another name (다진 생강 for 생강, 케첩 for 케찹, 고추냉이(와사비), 식용유 for "기름", 셀러리/샐러리) | 16 | 18 |
| Not said but plausibly seen on screen (oil, sesame seeds, pepper; all of 비빔밥, whose captions are fragments) | 12 | 19 |
| Unclear: neither said in the captions nor typical to see (김치 국물 for 김치볶음밥, 간장 for 김밥, 후추 for 불고기덮밥; flash also 굴소스 for 계란볶음밥, 빨간 파프리카 and 양송이버섯 for 오므라이스) | 3 | 5 |

No item was clearly invented, but the unclear ones cannot be settled without watching the videos.

**Side by side (6 dishes: 김치볶음밥, 계란볶음밥, 김밥, 오므라이스, 버섯볶음밥, 두부덮밥).** Both models follow the same cooking order as the caption-based recipes and often add the amounts shown on screen (계란볶음밥: 1공기 200 g, 대파 40 g, 식용유 4큰술). flash splits steps more finely (김밥 25 steps against 10–12) and copies the on-screen ingredient card more completely (오므라이스: 20 ingredients including the garnish). The clearest difference is the main label: lite marked 양파, 당근, 피망, 버섯, 소시지 and 체다 치즈 as main for 오므라이스 and 양파 and 대파 for 버섯볶음밥, which would make the recipe check refuse a change whenever one of them is missing; flash kept main to what the dish is built on in these cases, but marked only 김 as main for 김밥.

**Interpretation.**

- The video route works without the caption route and gives at least as much: agreement with the captions is high where the captions are good (된장찌개, 계란간장밥, 스팸마요덮밥 at 1.0 with flash) and the video adds amounts and visual items where they are not.
- flash agrees more with the caption-based recipes, gives servings more often and labels main ingredients more consistently (89% against 76%). Since the recipe check refuses a change when a main ingredient is missing, the main label decides behaviour; this is the strongest reason to prefer flash. It costs three times as much per video but is faster.
- The stored file is therefore built with flash. The labels are still one model's judgement: a wrong main label makes the check refuse too often (lite's 오므라이스) or too rarely (flash's 김밥), and the reference is itself AI-made from captions.
- The "not the requested dish" answer for 베이컨볶음밥 is arguably too strict (a paprika and bacon fried rice is a variant); the build then tries the next verified video.
