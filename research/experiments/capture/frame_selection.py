# AI-generated with Claude Code (Sonnet 5.5), 2026-11-03; reviewed by Jaehyuk Choi.
"""Reference implementations of the frame-selection rules compared for a short fridge sweep.

Pure Python (no numpy, no OpenCV) so the rules can be tested next to the server code. The overlap
between two frames is supplied by the caller as ``pair(a, b) -> (overlap, reliable)``; see
``overlap_orb.py`` for an ORB + RANSAC estimator.

``time_bins`` is the rule the Android app uses (``SweepSelector`` in the app's ``domain/sweep``
package): ``test_frame_selection.py`` pins both to the same expected indices. The other rules exist
to compare against it.

Rules, each returning a sorted list of frame indices:

- ``single``: the sharpest frame (the one-photo baseline).
- ``uniform``: ``k`` frames evenly spaced in index.
- ``time_bins``: the sharpest frame of each of ``k`` equal time bins, then a blur gate.
- ``overlap_groups``: blur gate, group consecutive frames that overlap the group's first frame,
  keep the sharpest frame of each group, then pick ``k`` of those farthest-first by overlap.
  Equal scores are broken by temporal distance (a plain "first candidate wins" collapsed the
  picks to the start of long clips: span 0.24 -> 0.99 on a 143-frame clip after the fix).
- ``dense``: one frame every 0.4 s (an upper bound on what a request could carry).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from statistics import median

GATE_RATIO = 0.5
MIN_OVERLAP = (
    0.5  # a frame starts a new group below this overlap with the group's first frame
)
UNKNOWN_OVERLAP = 0.5  # overlap assumed when the estimator fails
MAX_GAP_NS = 250_000_000  # a new group also starts after this gap
DENSE_INTERVAL_NS = 400_000_000
MIN_K, MAX_K = 8, 15  # per-request frame cap bounds (the server accepts 2..15)

Pair = Callable[[int, int], tuple[float, bool]]


def clamp_k(k: int) -> int:
    return max(MIN_K, min(MAX_K, k))


def single(sharpness: Sequence[float]) -> list[int]:
    if not sharpness:
        return []
    return [max(range(len(sharpness)), key=lambda i: sharpness[i])]


def uniform(n: int, k: int) -> list[int]:
    if n <= k:
        return list(range(n))
    step = (n - 1) / (k - 1)
    return [n - 1 if i == k - 1 else round(i * step) for i in range(k)]


def passes_gate(sharpness: Sequence[float], ratio: float = GATE_RATIO) -> list[bool]:
    """True for frames at least ``ratio`` times as sharp as the median frame."""
    if not sharpness:
        return []
    limit = ratio * median(sharpness)
    return [s >= limit for s in sharpness]


def time_bins(
    timestamps_ns: Sequence[int],
    sharpness: Sequence[float],
    duration_ns: int,
    k: int = 10,
    ratio: float = GATE_RATIO,
    min_frames: int = 2,
) -> list[int]:
    """Sharpest frame per time bin, then drop blurred ones; falls back to the single sharpest."""
    if not sharpness:
        return []
    best: dict[int, int] = {}
    for i, (t, s) in enumerate(zip(timestamps_ns, sharpness, strict=True)):
        b = min(k - 1, max(0, int(min(max(t, 0), duration_ns - 1) * k // duration_ns)))
        if b not in best or s > sharpness[best[b]]:
            best[b] = i
    held = sorted(best.values())
    limit = ratio * median(sharpness)
    passing = [i for i in held if sharpness[i] >= limit]
    if len(passing) < min_frames:
        return [max(held, key=lambda i: sharpness[i])]
    return passing


def dense(timestamps_ns: Sequence[int]) -> list[int]:
    out, next_at = [], 0
    for i, t in enumerate(timestamps_ns):
        rel = t - timestamps_ns[0]
        if rel >= next_at:
            out.append(i)
            next_at = (rel // DENSE_INTERVAL_NS + 1) * DENSE_INTERVAL_NS
    return out


def group_by_overlap(
    kept: Sequence[int], timestamps_ns: Sequence[int], pair: Pair
) -> list[list[int]]:
    """Consecutive kept frames join the current group while they overlap its first frame."""
    if not kept:
        return []
    groups, anchor = [[kept[0]]], kept[0]
    for i in kept[1:]:
        overlap, reliable = pair(anchor, i)
        effective = overlap if reliable else 0.0
        too_far = timestamps_ns[i] - timestamps_ns[anchor] >= MAX_GAP_NS
        if effective < MIN_OVERLAP or too_far:
            groups.append([i])
            anchor = i
        else:
            groups[-1].append(i)
    return groups


def farthest_first(
    reps: Sequence[int], k: int, pair: Pair, tie_break: bool = True
) -> list[int]:
    """Start from the first representative; add the one overlapping the chosen ones least.

    With ``tie_break``, equal overlap scores go to the candidate whose nearest chosen frame is
    farthest in index; remaining ties keep the earliest candidate.
    """
    if len(reps) <= k:
        return list(reps)

    def known(result: tuple[float, bool]) -> float:
        return result[0] if result[1] else UNKNOWN_OVERLAP

    chosen = [reps[0]]
    while len(chosen) < k:
        best, best_score, best_dist = -1, 2.0, -1
        for r in reps:
            if r in chosen:
                continue
            score = max(max(known(pair(r, c)), known(pair(c, r))) for c in chosen)
            dist = min(abs(r - c) for c in chosen) if tie_break else 0
            if score < best_score or (
                tie_break and score == best_score and dist > best_dist
            ):
                best, best_score, best_dist = r, score, dist
        chosen.append(best)
    return sorted(chosen)


def overlap_groups(
    timestamps_ns: Sequence[int],
    sharpness: Sequence[float],
    pair: Pair,
    k: int = 8,
    ratio: float = GATE_RATIO,
    tie_break: bool = True,
) -> list[int]:
    if not sharpness:
        return []
    gate = passes_gate(sharpness, ratio)
    kept = [i for i in range(len(sharpness)) if gate[i]]
    groups = group_by_overlap(kept, timestamps_ns, pair)
    reps = [max(g, key=lambda i: sharpness[i]) for g in groups]
    return farthest_first(reps, clamp_k(k), pair, tie_break)


def span(chosen: Sequence[int], n: int) -> float:
    """Share of the clip between the first and last chosen frame (1.0 = the whole clip)."""
    if n < 2 or len(chosen) < 2:
        return 0.0
    return (max(chosen) - min(chosen)) / (n - 1)
