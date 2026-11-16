# Naive dish selection: the model decides, the server checks names

Question: if the model gets only the dish names and the user's ingredients, and answers with the dishes plus what the user has and lacks, how often is that answer consistent with the user's input, compared with computing have/missing on the server from key ingredients?

This is the design the demo started from. It replaces the server-side key-ingredient calculation, the substitution table and the rules fallback. Video discovery and token cost are separate studies (`../dish_tokens/`).

## Design under test

- Prompt: the dish names (one list) and the user's ingredients. No key ingredients, no categories, no table.
- Answer (strict JSON): `{"dishes":[{"name","have":[...],"missing":[...]}]}`, best first, no fixed count, an empty list is allowed.
- The server drops names that are not in the list and duplicates, keeps the order, and returns `have`/`missing` as the model wrote them (trimmed).
- Model failure: HTTP 502, no fallback.
- Adapt: the model proposes for each missing ingredient a substitute taken from the user's own ingredients, or null. The server checks only the JSON shape and that substitutes come from that list.

## Frozen before running (`criteria.json`)

The 31 suggestion inputs of `../dish_eval/cases.json` (inputs only; the two `limit` cases are dropped), the metrics and the thresholds are fixed in `criteria.json`, committed before any model call of this study. The thresholds apply to the naive path. A model call cap of 80 applies.

Metrics per answer: share of returned names in the dish list; `have` items that are not among the user's ingredients; `missing` items that are among them; non-empty answers when the reference set is not empty; recall and precision against the reference set; share of dishes with at most two missing key ingredients; refusal of malformed input; latency; tokens and cost.

Reference set: dishes with at least one owned key ingredient and at most one missing key ingredient, computed from the dish list by the old rule. The stored answers of the earlier design (hybrid, run 2 of `../dish_eval/`) are scored against the same reference for comparison; they are not subject to thresholds here.

**Ground truth is not human-labelled.** The reference is made by rule from the same list the system uses, so it measures consistency with that list and not how good a dish is for a person. It is also conservative: a dish with two missing ingredients can be a good suggestion.

## Limits

One run at temperature 0, one model, 31 inputs (one case moves a share by about 3 points), one author for the criteria.

## Reproduce

```sh
cd server && uv run --locked python -m experiments.dish_naive.run            # dry run, no call
```
