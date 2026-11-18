# ADR 004: Revise a stored recipe with one model call and a rule check without a model

- **Status:** Accepted (2026-11-19); amended the same day after round 2 of the evaluation; the recipe source (captions) is replaced by [ADR 006](adr-006-recipes-from-the-video.md), the check is unchanged

## Context

The earlier version revised a recipe-database recipe to the user's fridge. This version has no database. Recipes are written down only for dishes where a caption transcript was available: an AI restructures the transcript into ingredients (with a role: main, secondary, seasoning), numbered steps, tips and a list of uncertain items. Recipe text from a video is data, not an instruction, and an AI-made recipe can be wrong.

## Decision

- Recipes are read from one file (`DISH_RECIPES`, schema 1) into a `RecipeBook`; the file is third-party derived content and is not committed.
- `Reviser` decides availability on the server (owned, assumed staple, unavailable), makes ONE model call with a strict JSON schema, and passes the answer to `revision_check.check` (no model call). A result that uses an unavailable ingredient, mentions a dropped one in a step or tip, points at rows or steps that do not exist, or changes the recipe without a reason is reported as `failed`, never repaired.
- Before the call, the server refuses without a model call when an unavailable ingredient is what the dish is named after (a name of two or more characters anywhere in the dish name, a one-character name only at its end, because a Korean dish name ends in its head: 김치볶음밥 → 밥).
- After the check, a dropped main ingredient means the dish cannot be made: unavailable and not replaced by an owned ingredient named in a change → returned as a refusal; owned → failure. A removed one-character ingredient named as a word in a step (밥을, not 밥솥) is a failure.
- The model may refuse on its own; a refusal needs a reason. With nothing missing there is no model call.
- Every revised recipe carries the notice that it is an AI-made suggestion.

## Consequences

- Round 2 of `research/experiments/dish_revision` (36 synthetic and 29 real-recipe cases, one shared answer per case): wrong recipes accepted fell from 9 of 28 refuse cases to 1, refusals rose from 15 to 27, no wrongful refusal, and 23 of 64 model calls are no longer made.
- The main-ingredient rule trusts the `role` field, which an AI wrote when it structured the captions. A wrong role (potato as the main ingredient of curry) makes the server refuse a recipe a person might accept.
- One-character names inside compounds in a step (볶음밥, 흰밥) are not seen; answers that mention an omitted ingredient only to say it is left out are still rejected.
- Accuracy of the stored recipes themselves is not measured.

## Not now

- No second model call to verify the first.
- No automatic repair of a rejected answer.
- No use of recipe text outside the app (no export, no search index).
- The legal status of building recipes from captions is open and is not decided by this ADR.
