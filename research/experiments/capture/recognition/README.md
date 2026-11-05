# Multi-frame recognition evaluation

Question: does sending several frames from a short fridge sweep recognise more ingredients than one photo, and which frame selection is best? This directory holds the answer key, the frozen pass criteria, a scorer, and a gated runner. Photos and videos are not tracked.

## Contents

| File | Role |
| --- | --- |
| `answer_key.json` | Expected ingredient names per scene (`A01`–`A06` sweep clips, `B01`–`B11` single photos) and the grouping of clips into scenes. Names only. |
| `thresholds.json` | Pass criteria, frozen before any result was computed. |
| `variants.json` | The frame-selection variants and merge rules compared. |
| `aliases.json` | Rewrites for one-character candidates (쌀, 무, 김) before matching. |
| `score.py` | Matching, per-fridge metrics, merges, paired bootstrap, verdict. No model calls. |
| `predict.py` | Sends selected frames to the vision model and writes predictions. Dry run by default. |
| `../../../../server/tests/experiments/capture/test_recognition_eval.py` | Offline known-answer tests. |

## Method

- **Unit:** one fridge (scene). Clips of the same fridge are grouped (`scenes` in the key, by visual overlap) and the interval resamples scenes, because clips of one fridge are not independent.
- **Matching:** a candidate matches an item when its normalized text equals, contains or is contained in an allowed name. Allowed names shorter than two characters never match. Each item and each candidate is used once. Ambiguous items are excluded by default.
- **Metrics:** recall, false recognition (share of candidates matching no item), fixes per scan (missed plus wrong), schema-valid rate.
- **Criteria (`thresholds.json`):** recall ≥ 0.60; false recognition ≤ 0.30; mean fixes ≤ 6.0; schema-valid ≥ 0.95. A variant beats another when the paired 95% interval excludes 0 and the difference is at least 0.10. Verdicts are provisional below 30 fridges.
- **Input:** frames re-encoded to 1024 px long side, JPEG quality 85, no metadata. The vision model (`google/gemini-2.5-flash-lite` through OpenRouter) counts a fixed 258 input tokens per image (measured), so a request with N images costs about 8 + 258 N input tokens: 2,072 for 8 frames, 3,878 for 15.
- **Variants:** `single` one photo; `uniform` evenly spaced; `time-bins` sharpest per time bin; `overlap` overlap groups with a farthest-first pick, taking the temporally farthest candidate on a score tie; `overlap-strict` the same with a stricter blur gate (0.7 x median); `all` about 2.5 frames per second.
- **Merge:** per-frame calls, then M1 union (primary), M2 seen in at least two frames, M3 union with a frame count.

## Run

Scoring and planning need only the server environment:

```sh
uv sync --project server --locked
(cd server && uv run --locked pytest tests/experiments/capture)
PYTHONPATH=research uv run --project server --locked \
  python -m experiments.capture.recognition.score \
  research/experiments/capture/recognition/answer_key.json PREDICTIONS.json OUT.json
```

`predict.py` takes a selection file and prints the plan (requests, images, expected input tokens) without sending anything:

```sh
PYTHONPATH=server:research uv run --project server --locked \
  python -m experiments.capture.recognition.predict SELECTION.json OUT.json --frames-dir DIR
```

Real requests need `--allow-live-api` and `OPENROUTER_API_KEY` in the environment. They are billed; read the plan first. `--mode multi_image` sends all frames of a variant in one request.

## Results as measured

Six sweep clips (about 2 independent scenes, loosely 3), M1 merge, two repeats, fixed tie-break. Recall / false recognition / mean fixes:

| Variant | Recall | False recognition | Fixes |
| --- | --- | --- | --- |
| single | 0.433 | 0.435 | 4.5 |
| uniform | 0.600 | 0.775 | 12.3 |
| time-bins | 0.767 | 0.697 | 10.0 |
| overlap | 0.600 | 0.783 | 12.8 |
| overlap-strict | 0.733 | 0.744 | 12.0 |
| all | 0.633 | 0.782 | 13.2 |

- More than one frame finds more: overlap with the tie-break fix beats single by +0.18 recall [+0.05, +0.35] (interval over 6 clips: 3 wins, 0 losses, 3 ties; positive in both scenes, but two scenes give no usable interval).
- No variant meets all four criteria. Every multi-frame variant has false recognition 0.74–0.78 against the 0.30 limit; one photo has 0.435 and also misses recall. Recall of 0.600 sits exactly on the limit for uniform and overlap and drops below it under small changes to the key.
- The ranking of variants is not stable. Differences between multi-frame variants are within the intervals, so this evaluation supports "more than one frame helps recall" but not the choice of a selection variant. time-bins is not comparable: the key was drafted from nearly the same frames time-bins selects (45 of 48).

## Limits

- About 2 independent scenes, far below the 30 planned.
- The key was drafted by one reviewer with a model's help. Uncertain items were checked and removed; the remaining items were not independently verified.
- One vision model and one prompt.
- Generic answers (sauce, drink, bottle) count as wrong when they match no item, which raises false recognition for every variant.
