# Revising a dish recipe to the ingredients at hand

Question: given a structured recipe and the ingredients a user owns, does the model (one call) rewrite the recipe so that it uses only what the user has, or refuse when the dish cannot be made, and does the server check (no model call) catch the answers that break the rules?

The feature is `POST /dishes/revise` (`server/app/dishes/revision.py`). The server marks each recipe ingredient as owned, assumed (a staple at home) or unavailable, asks the model to revise or refuse, and then rejects an answer that uses an unavailable ingredient, mentions one in a step or tip, points at rows or steps that do not exist, or drops an ingredient without a reason.

## Design of the study

- 12 hand-written recipes (generic cooking knowledge, not copied from a site or a video) in `fixtures.json`, 3 fridges each in `cases.json`: a minor ingredient missing (revise), an identity ingredient missing (refuse), and a minor ingredient missing with a possible stand-in at hand (revise). 36 cases, 36 planned model calls.
- Label rule: `refuse` when a recipe ingredient with role `main` is unavailable, otherwise `revise`. Every case has at least one unavailable ingredient, so the no-model shortcut never applies.
- Metrics and thresholds are in `criteria.json`; they were committed before any model call. The decision rule is there too: a missed threshold is reported, not tuned away in this study.

## Results

Run on 2026-11-18 at commit `b98d33f` (criteria committed earlier as `feda56e`), model `google/gemini-2.5-flash-lite`, temperature 0, one run, 36 requests (no retries), about $0.0074 in total. The server code under test is the one of `bc0fb22`.

| Metric | Threshold | Result | |
| --- | --- | --- | --- |
| Answers complete and schema-valid | >= 0.95 | 36/36 = 1.00 | pass |
| Post-check pass among non-refusals | >= 0.85 | 21/27 = 0.78 | **fail** |
| Wrongful refusals (expect revise) | <= 0.10 | 0/24 = 0.00 | pass |
| Refusal recall (expect refuse) | >= 0.80 | 9/12 = 0.75 | **fail** |
| Refusal precision | >= 0.90 | 9/9 = 1.00 | pass |
| Dropped ingredients that a change names (raw answer) | >= 0.90 | 1.00 | pass |
| Changed steps that a change names (raw answer) | >= 0.80 | 46/49 = 0.94 | pass |
| Median latency | <= 8 s | 1.4 s (p95 1.8 s) | pass |
| Mean cost per call | <= $0.002 | $0.0002 (about 810 in / 310 out tokens) | pass |

Outcomes by label: expect revise (24): 20 revised, 4 rejected by the check (2 `bad_reference`, 2 `unavailable_ingredient`); expect refuse (12): 9 refused, 2 rejected by the check (`mentions_unavailable`), 1 revised.

## Failures

- **`unavailable_ingredient` (R02a, R10c).** The model wrote the missing ingredient (carrot, pancake mix) back into the ingredient list with an empty amount. The check caught both; the user would see "failed", not a wrong recipe.
- **`bad_reference` (R01c, R08c).** The model numbered its changes by the position in its own revised list instead of the source rows (row 8 or 6 of a 7- or 5-row recipe). The check caught both.
- **Missed refusals (R01b, R08b, R12b).** The identity ingredient (rice, cheese, egg) was missing and the model revised instead of refusing. In R08b and R12b a step still named the missing ingredient and the check rejected the answer (`mentions_unavailable`), so the user would see "failed" instead of a clear refusal. **In R01b the answer was accepted**: the model dropped 밥 (rice) from the list, kept the step "밥을 넣고 고루 섞어 볶는다", and gave a reason. The check missed it because it ignores one-character ingredient names, and it has no rule that the identity ingredient (role main) must survive. This is the one case where a wrong recipe would reach the user.
- All refusals the model made were right (precision 1.00); it never refused a recipe that could be revised.

## What this means

The check did its job (6 of 7 bad answers were stopped), but the study shows two gaps that this round does not tune away: one-character names (밥, 김, 무, 파) are skipped by the step check, and a revised recipe that drops a `main` ingredient is not rejected. A change to the check or the prompt needs a new round with its own criteria. The labels follow a role rule (a main ingredient is missing, so refuse), and some cases a person might revise (a stand-in at hand) are not in the set.

## Limits

Synthetic recipes (the real ones will come from video captions and are noisier); one AI labeler; one run at temperature 0; 36 cases, 12 of them refusals, so one case moves a refusal metric by 8 points. In "stand-in" cases the catalog already counts some owned names as equivalents (for example 쪽파 for 대파), which makes them easier than a real fridge.
