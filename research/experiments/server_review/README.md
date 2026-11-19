# Server review findings: reproduce, measure, fix

A review of `server/` (2026-11-19, branch `feat/youtube-recipe-demo`) listed 13 findings. The owner asked to research a fix for all 13 before acting on severity. Each finding is reproduced first; a finding that does not reproduce is dropped and said so. Input is Korean only (the owner, 2026-11-19: English names are low priority and are not handled in these fixes).

## Protocol (fixed before any measurement)

No pass/fail thresholds: every number is reported and interpreted. Where a limit cannot be avoided (string length, time budget, cache lifetime) it is derived from data named below, with the reasoning written next to the result. The response shapes the current app reads do not change.

| # | Finding | Question | Measured | Inputs |
|---|---|---|---|---|
| 1 | Revision check misses some mentions of a removed ingredient | How many delivered revisions name a removed ingredient in a step or tip that the current check lets through, by kind (one-character name + particle not in the list, a synonym, a name inside a kept name)? How many of those are true misses on reading? | count per kind with the current check vs a candidate check; every disagreement read by hand | all model answers already recorded in revision round 3 (`data/dish-revision/round3-*.json`, 124 x variants N3, N3a and two N1 runs), against the recipes they were made from (`artifacts/dish-recipes/recipes.pre-shorts.json`) and the name table at HEAD; no new model calls |
| 2 | No length limit on ingredient strings; the addition endpoint has no list limit | Does a long string reach the model? How do prompt tokens grow with string length? What is the longest real name? | prompt characters per request built by the server for 1, 1k, 10k, 100k-character names (no model call); one paid call with a 10k-character name to read the provider's token count; the longest name in the dish list, the recipe name table, the stored recipes and the app's ingredient table | `dishes.json`, `recipe_names.json`, `recipes.json`, `android/.../ingredient_presentation.csv` |
| 3 | Video requests repeat paid calls and YouTube units | Model calls and YouTube calls per repeated request, for a dish with stored videos and for one whose discovery finds nothing | calls counted with fakes over 10 repeated requests, before and after | fakes only |
| 4 | Card, addition suggestion and revision disagree on owned names | For realistic Korean fridges, how often does the card's `missing` choice list contain a key ingredient that the addition suggestion or the recipe view counts as owned? | per fridge and per name, the three views side by side | fridges built from the app's onboarding presets plus common store names (햇반, 삼겹살, 다진마늘, 청양고추, 슬라이스치즈, 스팸) |
| 5 | A non-string value in a model answer raises a 500 | Which malformed answers crash the check? | each malformed field fed to the check | synthetic answers |
| 6 | Worst-case revise time exceeds the app's read timeout | What is the worst-case time per request from the code's timeouts and waits, and what does the app wait? | arithmetic from the code, checked with a fake transport that sleeps | `llm.py`, `http.py`, `recipes.py`, app `DishApi.kt` (90 s), nginx (210 s) |
| 7 | The dish service carries objects it does not use | Which fields of `DishService` does it use itself? | reading | code |
| 8 | Several synonym and normalisation functions behave differently | How many copies exist and where do their answers differ? | each copy run on the same names | name tables |
| 9 | Retry waits are a module global patched by tests | Can the waits be injected so no test patches a module? | reading, test change | code |
| 10 | The key fallback rule is written twice | Same | reading | code |
| 11 | Dead code | Which functions or constants does the running app never call? | import graph from `app.main` vs callers in tests and research | code |
| 12 | A contract test passes an always-empty verifier | Does a verifier that returns `[]` pass? | run the contract against that verifier | tests |
| 13 | Missing tests | Covered by the tests added for 1-12 | — | — |

Real model calls: only for 2 (one call) and for re-checking 1 if a candidate check changes delivered answers (none planned). Calls and cost are recorded in `results.json`.

## Results

(written after measuring)
