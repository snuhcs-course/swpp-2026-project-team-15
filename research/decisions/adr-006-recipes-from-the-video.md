# ADR 006: Write the stored recipes from the video itself, keep only the video id

- **Status:** Accepted (2026-11-19); replaces the caption route of ADR 004 as the recipe source

## Context

The caption route (unofficial transcript fetch, then an AI restructuring) stopped after 31 videos when YouTube refused automated caption requests from our address. Google documents an official alternative: a Gemini model can take a public YouTube URL as input and watch it (about one frame per second plus the audio). OpenRouter forwards YouTube links to Gemini only through Google AI Studio. The recipe check (ADR 004) depends on the `role` label of each ingredient, so the labels must be consistent. YouTube API data such as titles may not be stored for long.

## Decision

- A build tool (`research/experiments/dish_recipes/run_video_recipes.py build`) writes one recipe per dish offline: for each dish it takes the first verified video (the stored, judged links), asks `gemini-2.5-flash` with a strict JSON schema whether the video cooks the dish and, if so, for the recipe in its own words; it tries at most three videos per dish. The recipe carries `source: ai_structured_from_video`.
- The recipe file keeps only the video id. `CreditedRecipes` wraps the `RecipeBook` and looks up title and channel live through the `VideoVerifier` role (reused for 24 hours, empty when the video is gone or the lookup fails); it is composed in the composition root, so the store and the service stay unchanged.
- The file is third-party derived, copied to the server by hand and never committed.

## Consequences

- In the comparison on 16 dishes with caption-based recipes, flash agreed more with them (median precision 0.85 against 0.71 for flash-lite), gave servings more often (7 against 2 of 15) and kept main labels consistent with them more often (89% against 76%); it costs about three times as much per video ($0.04 against $0.013 median) and was faster.
- A wrong main label still makes the recipe check refuse too often or too rarely; no human has checked the labels.
- The model may call a variant "another dish" (a paprika and bacon fried rice for 베이컨볶음밥) and move on to the next video.
- Whether recipes written from third-party videos may be shown in a store release is open.

## Not now

- No recipe generation at request time (cost and latency per view, and no review before users see it).
- No caption fetching.
- No second model to check the first; no human review of all recipes yet.
