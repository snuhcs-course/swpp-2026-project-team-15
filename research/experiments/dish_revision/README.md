# Revising a dish recipe to the ingredients at hand

Question: given a structured recipe and the ingredients a user owns, does the model (one call) rewrite the recipe so that it uses only what the user has, or refuse when the dish cannot be made, and does the server check (no model call) catch the answers that break the rules?

The feature is `POST /dishes/revise` (`server/app/dishes/revision.py`). The server marks each recipe ingredient as owned, assumed (a staple at home) or unavailable, asks the model to revise or refuse, and then rejects an answer that uses an unavailable ingredient, mentions one in a step or tip, points at rows or steps that do not exist, or drops an ingredient without a reason.

## Design of the study

- 12 hand-written recipes (generic cooking knowledge, not copied from a site or a video) in `fixtures.json`, 3 fridges each in `cases.json`: a minor ingredient missing (revise), an identity ingredient missing (refuse), and a minor ingredient missing with a possible stand-in at hand (revise). 36 cases, 36 planned model calls.
- Label rule: `refuse` when a recipe ingredient with role `main` is unavailable, otherwise `revise`. Every case has at least one unavailable ingredient, so the no-model shortcut never applies.
- Metrics and thresholds are in `criteria.json`; they were committed before any model call. The decision rule is there too: a missed threshold is reported, not tuned away in this study.

## Results

Not run yet.

## Limits

Synthetic recipes (the real ones will come from video captions and are noisier); one AI labeler; one run at temperature 0; 36 cases, 12 of them refusals.
