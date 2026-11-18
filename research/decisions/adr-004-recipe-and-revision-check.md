# ADR 004: Revise a stored recipe with one model call and a rule check without a model

- **Status:** Accepted (2026-11-19); the check has known gaps (see Consequences)

## Context

The earlier version revised a recipe-database recipe to the user's fridge. This version has no database. Recipes are written down only for dishes where a caption transcript was available: an AI restructures the transcript into ingredients (with a role: main, secondary, seasoning), numbered steps, tips and a list of uncertain items. Recipe text from a video is data, not an instruction, and an AI-made recipe can be wrong.

## Decision

- Recipes are read from one file (`DISH_RECIPES`, schema 1) into a `RecipeBook`; the file is third-party derived content and is not committed.
- `Reviser` decides availability on the server (owned, assumed staple, unavailable), makes ONE model call with a strict JSON schema, and passes the answer to `revision_check.check` (no model call). A result that uses an unavailable ingredient, mentions a dropped one in a step or tip, points at rows or steps that do not exist, or changes the recipe without a reason is reported as `failed`, never repaired.
- The model may refuse when the dish's identity depends on an unavailable ingredient; a refusal needs a reason. With nothing missing there is no model call.
- Every revised recipe carries the notice that it is an AI-made suggestion.

## Consequences

- The evaluation (`research/experiments/dish_revision`, 36 synthetic cases) shows two gaps the check does not close: it skips one-character ingredient names (밥) and has no rule that a main ingredient must survive, so one wrong recipe passed. The old code base used the role label for this; porting it is the next round.
- Accuracy of the stored recipes themselves is not measured.

## Not now

- No second model call to verify the first.
- No automatic repair of a rejected answer.
- No use of recipe text outside the app (no export, no search index).
- The legal status of building recipes from captions is open and is not decided by this ADR.
