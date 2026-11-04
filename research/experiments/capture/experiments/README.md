# Frame-selection studies: what did not change the app

Question: can the app's rule (sharpest frame per time bin, blur gate, up to 10 frames in one request) be improved by a prompt change, by removing similar frames, or by clustering? Each study had its criteria fixed before any model call. None passed, so the app keeps the time-bin rule.

| Path | Content |
| --- | --- |
| `frame_similarity.py` | Similarity measures, removal of the most similar frames, agglomerative clustering, cluster-first selection. Pure Python; OpenCV only for `frame_features`. |
| `run_multi_image.py` | Applies the arms in `arms.json` to a directory of clips and sends one request per arm through the server's vision provider. Dry run unless `--allow-live-api`. |
| `arms.json` | The arms below. |
| `../../../../server/tests/experiments/capture/test_frame_similarity.py` | Offline tests on synthetic data. |

Setup shared by all studies: six sweep clips of two fridges (1.5 to 4.7 s), the answer key and scorer in [`../recognition/`](../recognition/README.md), `google/gemini-2.5-flash-lite`, frames prepared as the app does (1024 px, JPEG q85, no metadata), all frames of an arm in one request. Replicates are different frame sets from the same clip, not new scenes.

## 1. Blank frames and the prompt

With black, dark or blurred frames the multi-view prompt makes the model list typical fridge items (8 black frames gave 11 items in the study). White frames broke the response format. Candidate fix: add "List only items you can actually see; never guess typical fridge contents. If no food is visible, return an empty list."

Criteria: at least 90% empty answers on blank input; on real clips recall not more than 0.05 lower and false recognition not higher.

| Prompt | Empty answers on blank input (4 inputs x 5) | Recall | False recognition |
| --- | --- | --- | --- |
| current | 0/20 | 0.579 | 0.341 |
| with the sentence | 20/20 | 0.471 | 0.455 |

Not adopted: blank input is fixed, real footage got worse (76 requests, about $0.02). A gate on brightness and sharpness before upload would avoid touching the prompt; it was not built.

## 2. Removing similar frames, and clustering the time-bin frames

Arms (`arms.json`): base10; `edge-drop2/4/6` and `hist-drop4` remove the frame most similar to another one (edge-map correlation or colour histogram); `random-drop4`; `uniform6`; `cluster6-pool` (20 time bins, 6 clusters, sharpest per cluster). Replicates: the time grid shifted by 0, 1/3 and 2/3 of a bin.

Criteria: at least 30% fewer frames, recall drop at most 0.05, false recognition at least 0.05 lower in the mean and with the same sign in at least 4 of 6 clips, and better than random removal of the same count by at least 0.03.

| Arm | Frames | Recall | False recognition |
| --- | --- | --- | --- |
| base10 (app) | 9.9 | 0.560 | 0.415 |
| edge-drop2 | 7.9 | 0.617 | 0.391 |
| edge-drop4 | 5.9 | 0.578 | 0.444 |
| edge-drop6 | 3.9 | 0.540 | 0.470 |
| hist-drop4 | 5.9 | 0.491 | 0.444 |
| random-drop4 | 5.9 | 0.510 | 0.444 |
| uniform6 | 6.0 | 0.472 | 0.511 |
| cluster6-pool | 6.0 | 0.656 | 0.375 |

No arm passed. `cluster6-pool` is the closest: it beats random removal, but false recognition fell by 0.04 with the right sign in 3 of 6 clips. Run to run, the same arm moved by about 0.22 on both measures, more than any difference between arms. Which frames count as "similar" depends on the measure: at correlation 0.9 about 3% of the app's frames are redundant, at thresholds calibrated on adjacent frames 32 to 80%; two measures order the removals differently (Kendall tau 0.58 to 0.89). A replay of stored per-frame answers suggested that dropping similar frames loses less than dropping random ones; the live one-request runs did not reproduce that (135 requests, about $0.03).

## 3. Cluster first, then time

Cluster all blur-gated frames, split each cluster into runs wherever its frames are more than 0.4 s apart (a revisited view counts again), keep the sharpest frame per run, cap at 10. Replicates: every third frame, three offsets. Same criteria as in study 2, plus not worse than `cluster6-pool`.

| Arm | Frames | Recall | False recognition |
| --- | --- | --- | --- |
| base10 (app) | 9.4 | 0.594 | 0.410 |
| cluster6-pool | 6.0 | 0.534 | 0.434 |
| cluster-first6 | 7.9 | 0.506 | 0.471 |
| cluster-first10 | 10.0 | 0.514 | 0.481 |
| cluster-first6-hist | 6.7 | 0.531 | 0.459 |
| random, same count as cluster-first6 | 7.9 | 0.465 | 0.522 |

Recall fell by 0.06 to 0.09 and false recognition rose by 0.05 to 0.07 against the app; the spread between replicates (0.10 to 0.22) is larger than the effect. Splitting clusters in time produces many runs (up to 17 for a clip), so the cap often decides. The tables of studies 2 and 3 use different replicate schemes and are not comparable (109 requests, about $0.03).

On a phone, clustering all frames means keeping every candidate frame: about 350 MB of 1024 px bitmaps for 150 frames, against at most 10 held now. A streaming variant (nearest cluster centre per frame, O(K) per frame) would keep memory bounded; it was not built or timed on a phone.

## Reproduce

```sh
(cd server && uv run --locked pytest tests/experiments/capture/test_frame_similarity.py)
# plan only: decodes the clips, applies the arms, prints requests and expected tokens
PYTHONPATH=server:research uv run --project server --locked \
    --with opencv-python-headless --with numpy \
    python -m experiments.capture.experiments.run_multi_image --videos CLIP_DIR
# similarity of the app's frames and agreement between measures: add --offline-report
# real requests (billed): add --allow-live-api --out data/capture-experiments/predictions.json
# score
PYTHONPATH=research uv run --project server --locked python -m experiments.capture.recognition.score \
    research/experiments/capture/recognition/answer_key.json data/capture-experiments/predictions.json OUT.json
```

Clip ids follow the answer key (A01 to A06 in file order, or `--clip-map`). Real requests need `OPENROUTER_API_KEY`; `--max-calls` caps them. The price flags only feed the cost estimate.

## Limits

- About two independent fridges and six short clips with fast motion; the app's 5 s sweep that lingers on one shelf is not covered.
- The answer key is a one-reviewer draft; one item moves recall by 0.03 to 0.1.
- One similarity measure family, one linkage, one gap (0.4 s); nothing was tuned on the results.
- Clips and run outputs are private and not in the repository.
