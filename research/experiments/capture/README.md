# Capturing several frames for ingredient recognition

Question: does sending a few well-chosen frames from a short fridge sweep recognise more ingredients than one photo, and can a phone pick those frames cheaply while the camera runs?

The app-side result of this work is the video mode of the capture screen and multi-image `/analyze` (see the API overview). This directory holds the reference rules, the demo app used to measure them on a phone, and the evaluation tooling.

| Path | Content |
| --- | --- |
| `frame_selection.py` | Reference implementations of the selection rules (single, uniform, time bins, overlap groups, dense). Pure Python. |
| `overlap_orb.py` | ORB + RANSAC overlap estimate between two frames (needs OpenCV). |
| `android-demo/` | Separate Gradle project that measures the rules, camera stream and decoding on a phone. Not part of the app build. |
| `recognition/` | Scorer, thresholds, answer key and protocol for comparing selection rules by recognition quality. |
| `experiments/` | Studies that did not change the app: a prompt change for blank frames, removal of similar frames, clustering. Reproducible runner and tests. |
| `../../../server/tests/experiments/capture/` | Offline tests for the rules above. |

## Findings

Measured on one Android phone with a 1024 px JPEG (q85) per frame and `google/gemini-2.5-flash-lite`.

**Request cost.** The model counts a fixed 258 input tokens per image regardless of size, so a request costs about 8 + 258 N tokens: 2,072 for 8 frames and 3,878 for 15. A 1024 px frame is about 56 KB from video and 103 KB from a photo, so 8 frames are well below the 15 MiB request limit.

**Selection rule.** Frames chosen by overlap grouping need a reliable overlap estimate, which failed for 62% of real fridge frame pairs (1,284 of 2,065; 66% in a second run). The app therefore uses the time-bin rule: the sharpest frame of each of 10 time bins, minus frames below half the median sharpness. It needs one pass, holds at most 10 frames and does no feature matching.

**Tie-break defect (overlap groups).** When many candidates scored equally, the first one won and the picks stayed at the start of the clip. Choosing the temporally farthest candidate raised the span of a 143-frame clip from 0.24 to 0.99 (phone: 0.31 to 0.96). `frame_selection.overlap_groups` has the fix; `tie_break=False` reproduces the defect.

**Same rule on host and phone.** Python and Kotlin selections were index-identical on every recorded input and on live camera runs. Python and phone choices differ on some video files only because their video decoders return slightly different frames.

**Phone cost per frame** (camera stream, 1280x720, median / p95):

| Step | 30 fps | 15 fps (auto) |
| --- | --- | --- |
| Analysis total (luma copy, sharpness, ORB) | 14.5 / 24.7 ms | 21.3 / 26.4 ms |
| of which sharpness | 3.9 ms | 7.8 ms |
| Frames dropped | none | none |

Other timings: JPEG encode at 1024 px 1.5 to 2.5 ms; converting a camera frame to a bitmap path costs 10 to 14 ms, about 3 times the direct luma path; recording a clip and decoding it afterwards costs 124 to 173 ms per frame, so analysing the live stream is about 6 to 8 times faster; still capture runs 0.71 stills/s (latency 1.4 s); a burst of 8 stills took 0.74 s and 15 took 1.2 s; thermal status stayed at none. The camera was covered during these runs, so the numbers check speed and plumbing, not recognition.

**Recognition.** See [`recognition/`](recognition/README.md): several frames recognised more than one photo (recall +0.18, 95% interval +0.05 to +0.35, for overlap groups with the fixed tie-break), but they also raised false positives, no rule met the pre-set thresholds and their ranking was not stable. The evaluation covers about two independent scenes, so it supports "more than one frame helps" and nothing finer.

## Reproduce

```sh
# Rule tests (no media, no network)
(cd server && uv run --locked pytest tests/experiments/capture)
# Overlap estimator (optional dependencies, declared on the command line)
PYTHONPATH=research uv run --with opencv-python-headless --with numpy \
    python -m experiments.capture.overlap_orb --help
```

The phone measurements are described in [`android-demo/README.md`](android-demo/README.md). They need a device and short sweep videos or the live camera; neither is stored here.

## Limits

- Videos, photos and run outputs are private and not in the repository.
- Phone timings come from one device and a covered camera; the video-file runs use six short clips of two fridges.
- The recognition comparison is small; see its README before drawing conclusions about selection rules.
