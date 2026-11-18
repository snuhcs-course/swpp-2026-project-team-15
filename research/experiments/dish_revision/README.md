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

## Round 2: refusal before the call and main-ingredient preservation

Design in `criteria_round2.json` (committed as `cc3e75a` before any model call; two dated amendments before re-runs). Code: `round2.py`, `run_round2.py`; the candidate rules are pure functions in `server/app/dishes/revision_check.py`. No thresholds: all numbers are reported and interpreted.

**Variants.** The same server request and one model answer per case; the variants differ only in steps before and after the call, so they are compared on identical answers.

| Variant | Before the call | After the call |
| --- | --- | --- |
| current | - | the round-1 check |
| prescreen | refuse without a call when an unavailable ingredient is what the dish is named after (2+ characters anywhere in the name, a one-character name only at its end: 김치볶음밥 → 밥) | the round-1 check |
| main-kept | - | round-1 check, then: an unavailable main ingredient dropped without an owned replacement named in a change → returned as a refusal; an owned main ingredient dropped → failure; a removed one-character ingredient named as a word in a step (밥을, not 밥솥) → failure |
| both | prescreen | main-kept |

**Inputs.** The 36 frozen synthetic cases (12 expect refuse) and 29 fridges for the 16 recipes made from video captions (16 expect refuse), built by rule before any call (`round2.build_real_cases`; the file is not committed, its sha256 is in the criteria). Labels: refuse when a main ingredient is missing; the roles of the real recipes were written by the AI that structured the captions.

**Runs.** 2026-11-19, `google/gemini-2.5-flash-lite`, temperature 0, cap 4096. Synthetic: one run (report `round2-20261118T153815Z`, 36 calls, $0.0074). Real: third run (report `round2-20261118T154211Z`, 30 requests including 2 retried 429s, $0.0108); the first two real runs had a runner defect for the one case that needs no model call (recorded in the amendments); their other 28 outcomes were identical. All runs together: 122 requests, about $0.040.

| | current | prescreen | main-kept | both |
| --- | --- | --- | --- | --- |
| **Synthetic (36)**: wrong recipe accepted (expect refuse, shown revised) | 1 | 0 | 0 | 0 |
| refused / expect refuse (12) | 9 | 12 | 10 | 12 |
| failed / expect refuse | 2 | 0 | 2 | 0 |
| wrongful refusals / expect revise (24) | 0 | 0 | 0 | 0 |
| failed / expect revise | 4 | 4 | 4 | 4 |
| model calls | 36 | 25 | 36 | 25 |
| **Real (29)**: wrong recipe accepted | **8** | 4 | 1 | **1** |
| refused / expect refuse (16) | 6 | 12 | 13 | 15 |
| failed / expect refuse | 2 | 0 | 2 | 0 |
| wrongful refusals / expect revise (13) | 0 | 0 | 0 | 0 |
| failed or no answer / expect revise | 5 | 5 | 5 | 5 |
| model calls | 28 | 16 | 28 | 16 |

Refusal precision was 1.00 in every cell. Change reasons in the raw revising answers: dropped ingredients named in a change 34/34 (synthetic) and 32/32 (real), changed steps 46/49 and 32/34. Median latency 1.4 s (synthetic) and 2.1 s (real), maximum 8.2 s (a real answer cut at the cap).

**What the numbers show.**

- With the current check the real recipes are where it goes wrong: 8 of 16 "main ingredient missing" fridges got a revised recipe, 4 of them rice dishes whose answer removed rice from the ingredient list but still says to add or spread rice in a step (밥을 넣고 볶는다). The synthetic set (1 of 12) understated the problem.
- The prescreen alone stops the dishes named after the missing ingredient (bibimbap, bulgogi bowl, egg fried rice, gimbap) and saves 11 of 36 and 12 of 28 calls; it cannot see a main ingredient that is not in the dish name (rice in 오므라이스, 즉석밥 in 햄볶음밥, potato in curry).
- The main-ingredient rule closes those (curry rice, ham fried rice, omurice) and turns the two answers that were failures into clear refusals only together with the prescreen.
- Together (both): wrong recipes accepted 1 of 28 refuse cases (synthetic and real), refusals 27 of 28, no wrongful refusal, fewer calls. The remaining case is mushroom fried rice without 새송이버섯: the user owns three other mushrooms, the dish list counts mushrooms as interchangeable, so the server needs no call and shows the recipe unchanged; the label "refuse" is debatable there.
- Nothing changed for the cases that expect a revision: the 4 synthetic and 4 real failures are answers that keep naming a missing ingredient (two use it, e.g. eggs in bacon fried rice; one suggests an ingredient the user lacks; one only says "달걀은 생략합니다", which the check also rejects), and one real answer was cut at the 4096-token cap.

**Limits.** One run, one model. The main-ingredient rule and the labels both use the role field written by an AI, so its zero wrongful refusals is partly by construction: if a role is wrong (potato as the main ingredient of curry), the rule refuses a recipe a person might accept. The word rule for one-character names misses compounds in a step (볶음밥, 흰밥). 28 refusal cases in total; one case moves a share by 3–4 points.

**Adopted** (judgement, implemented in `server/app/dishes/revision.py`): both steps. The wrong recipes the check let through are the outcome the feature must avoid, both steps removed 15 of the 16 seen here without a wrongful refusal and they need fewer model calls. The cost is a dependence on the role labels, recorded in ADR 004.

## Round 2b: keep owned and assumed rows (design, 2026-11-19, before any call)

Trigger: on the phone, 두부부침 with only 두부 owned failed twice (`unexplained_change`): the model kept only 두부 in the ingredient list and dropped the assumed staples, one of them (식용유) without a reason. Question: does one added sentence in rule 2 ("keep every owned or assumed source ingredient the revised recipe still uses in the ingredient list, with its source amount") stop such answers? Variants `old` (served text) and `keep`; the 36 frozen synthetic cases plus the demo case, one run each through the served `Reviser`. Metrics and plan: [criteria_round2b.json](criteria_round2b.json). No pass/fail thresholds; the decision is written after the numbers. Runner: `run_round2b.py` (dry run by default).

Amendment (2026-11-19, before the real-sample calls): the synthetic fixtures have no assumed rows, so they cannot show the targeted failure. Added 20 served recipes sampled with seed 20261119, fridge = the recipe's main ingredients only, old vs keep, one run each.

### Round 2b results (2026-11-19)

Model calls: about 150 (two runs of the 36 synthetic + 1 demo case, then 20 served recipes x 2); cost under $0.06. One run per variant at temperature 0.

| Set | Variant | Served revised | Refused | Failed (codes) | Other |
|---|---|---|---|---|---|
| 36 synthetic (24 revise, 12 refuse) | old | 20/24 | 12/12 | 4 (bad_reference 2, unavailable_ingredient 2) | |
| | keep | 19/24 | 12/12 | 5 (mentions_unavailable 3, bad_reference 1, unavailable_ingredient 1) | |
| Demo case 두부부침 with ['두부'] | old | | | failed (unexplained_change) | twice before on the server |
| | keep | revised | | | |
| 20 served recipes, fridge = main ingredients | old | 11 | 4 | 5 (mentions_unavailable 3, unavailable_ingredient 2) | |
| | keep | 12 | 3 | 4 (mentions_unavailable 3, unavailable_ingredient 1) | 1 provider error (cut-off answer) |

Interpretation: the sentence removes the failure seen on the phone, and neither set shows a cost of it; the case-by-case outcomes flip in both directions between the two runs (7 of 36 synthetic, 8 of 20 served), so run-to-run variation is larger than any difference between the variants and the sets cannot rank them. The synthetic fixtures have no assumed rows, and in the served sample the targeted failure (unexplained_change) did not occur in either variant, so this failure is rarer than the phone case suggested. Adopted: `keep` (judgement: removes an observed failure, no measured harm). Bigger finding: with only the main ingredients owned, about a quarter of served recipes end in a failed answer, mostly a step that still mentions an omitted ingredient (`mentions_unavailable`); this is not addressed here.
