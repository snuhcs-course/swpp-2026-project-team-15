# AI-generated with Claude Code (Sonnet 5.5), 2026-11-04; reviewed by Jaehyuk Choi.
"""Similarity-based frame selection variants compared with the app's time bins.

Pure Python (no numpy, no OpenCV) so the logic is tested next to the server code. Frame features
are plain lists of floats computed elsewhere (see ``frame_features`` for the OpenCV version).

Selections, all returning sorted frame indices:

- ``phased_time_bins``: the app's rule (sharpest frame per time bin + blur gate) on a time grid
  that can start part-way into the first bin; different phases give different frame sets from the
  same clip (used as replicates).
- ``drop_similar``: from a base selection, repeatedly remove the frame most similar to another
  remaining frame (ties remove the less sharp one).
- ``cluster_pool``: pick a larger pool by time bins, cluster it, keep the sharpest frame of each
  cluster.
- ``cluster_first``: cluster all blur-gated frames, split each cluster into runs wherever its
  frames are more than ``gap_ns`` apart, keep the sharpest frame of each run, cap the count.
- ``random_drop`` and ``uniform``: controls.

Similarity measures (``KINDS``): ``edge`` and ``gray`` are mean-centred correlations of vectors;
``hist`` is histogram intersection. Which measure is used changes how many frames look redundant
and in which order they are removed (``kendall_tau_b`` compares orderings).
"""

from __future__ import annotations

import hashlib
import math
import random
from collections.abc import Mapping, Sequence
from itertools import pairwise

from experiments.capture import frame_selection as fs

KINDS = {"edge": "corr", "gray": "corr", "hist": "intersection"}
DEFAULT_GAP_NS = 400_000_000
DEFAULT_CAP = 10
GATE_RATIO = 0.5


# --- similarity -----------------------------------------------------------------------------


def correlation(a: Sequence[float], b: Sequence[float]) -> float:
    """Mean-centred correlation; 1.0 when either vector is constant (nothing to compare)."""
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b, strict=True))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return num / den if den > 0 else 1.0


def intersection(a: Sequence[float], b: Sequence[float]) -> float:
    """Histogram intersection of two normalised histograms (1.0 = identical)."""
    return sum(min(x, y) for x, y in zip(a, b, strict=True))


def similarity(measure: str, a: Sequence[float], b: Sequence[float]) -> float:
    return correlation(a, b) if KINDS[measure] == "corr" else intersection(a, b)


def kendall_tau_b(x: Sequence[float], y: Sequence[float]) -> float:
    """Rank agreement between two orderings (1 = same, -1 = reversed); NaN if undefined."""
    concordant = discordant = ties_x = ties_y = 0
    for i in range(len(x)):
        for j in range(i + 1, len(x)):
            dx, dy = x[i] - x[j], y[i] - y[j]
            if dx == 0 and dy == 0:
                continue
            if dx == 0:
                ties_x += 1
            elif dy == 0:
                ties_y += 1
            elif dx * dy > 0:
                concordant += 1
            else:
                discordant += 1
    den = math.sqrt((concordant + discordant + ties_x) * (concordant + discordant + ties_y))
    return (concordant - discordant) / den if den else float("nan")


# --- time-bin selection with a phase ----------------------------------------------------------


def phased_time_bins(
    timestamps_ns: Sequence[int],
    sharpness: Sequence[float],
    bins: int = 10,
    phase: float = 0.0,
    ratio: float = GATE_RATIO,
) -> list[int]:
    """The app's rule on a grid starting ``phase`` bin widths into the clip (0 = the app's grid).

    Returns global indices. Frames before the start are ignored and the blur gate uses the median
    of the remaining frames.
    """
    if not sharpness:
        return []
    duration = max(timestamps_ns) + 1
    start = round(phase * duration / bins)
    keep = [i for i, t in enumerate(timestamps_ns) if t >= start]
    if not keep:
        return []
    local = fs.time_bins(
        [timestamps_ns[i] - start for i in keep],
        [sharpness[i] for i in keep],
        duration - start,
        bins,
        ratio,
    )
    return [keep[i] for i in local]


# --- removal of similar frames ---------------------------------------------------------------


def removal_order(
    frames: Sequence[int],
    sharpness: Sequence[float],
    features: Sequence[Sequence[float]],
    measure: str,
) -> list[int]:
    """Frames in the order they would be removed: the one most similar to another remaining frame
    first, a tie removing the less sharp frame; the last survivor comes last."""
    remaining = list(frames)
    order: list[int] = []
    while len(remaining) > 1:
        best: tuple[tuple[float, float], int] | None = None
        for i in remaining:
            top = max(similarity(measure, features[i], features[j]) for j in remaining if j != i)
            key = (-round(top, 12), sharpness[i])
            if best is None or key < best[0]:
                best = (key, i)
        assert best is not None
        order.append(best[1])
        remaining.remove(best[1])
    return order + remaining


def drop_similar(
    frames: Sequence[int],
    sharpness: Sequence[float],
    features: Sequence[Sequence[float]],
    measure: str,
    drop: int,
) -> list[int]:
    order = removal_order(frames, sharpness, features, measure)
    removed = set(order[: min(drop, max(len(order) - 1, 0))])
    return sorted(i for i in frames if i not in removed)


def random_drop(frames: Sequence[int], drop: int, seed: str) -> list[int]:
    """Control: remove ``drop`` frames at random (seeded by any string)."""
    rng = random.Random(int(hashlib.sha256(seed.encode()).hexdigest()[:16], 16))
    keep = max(len(frames) - drop, 1)
    return sorted(rng.sample(list(frames), keep))


def uniform(frames: Sequence[int], count: int) -> list[int]:
    """Control: ``count`` frames evenly spaced over the given frame list."""
    return sorted(frames[i] for i in fs.uniform(len(frames), count))


# --- clustering -----------------------------------------------------------------------------


def average_linkage(dist: Sequence[Sequence[float]], k: int) -> list[list[int]]:
    """Agglomerative clustering with average linkage until ``k`` clusters remain.

    Ties merge the pair that comes first in index order. Returns lists of member indices.
    """
    clusters: dict[int, list[int]] = {i: [i] for i in range(len(dist))}
    d: dict[tuple[int, int], float] = {
        (i, j): dist[i][j] for i in range(len(dist)) for j in range(i + 1, len(dist))
    }
    while len(clusters) > max(k, 1):
        a, b = min(d, key=lambda pair: (d[pair], pair))
        na, nb = len(clusters[a]), len(clusters[b])
        for c in clusters:
            if c in (a, b):
                continue
            ka, kb = (min(a, c), max(a, c)), (min(b, c), max(b, c))
            d[(min(a, c), max(a, c))] = (na * d[ka] + nb * d[kb]) / (na + nb)
            del d[kb]
        del d[(a, b)]
        clusters[a] = clusters[a] + clusters[b]
        del clusters[b]
    return list(clusters.values())


def _distances(frames: Sequence[int], features, measure: str) -> list[list[float]]:
    return [[1.0 - similarity(measure, features[i], features[j]) for j in frames] for i in frames]


def _sharpest(members: Sequence[int], sharpness: Sequence[float]) -> int:
    return max(members, key=lambda i: (sharpness[i], -i))


def cluster_pool(
    pool: Sequence[int],
    sharpness: Sequence[float],
    features: Sequence[Sequence[float]],
    measure: str,
    k: int,
) -> list[int]:
    """Cluster a pool of frames into ``k`` clusters and keep the sharpest frame of each."""
    groups = average_linkage(_distances(pool, features, measure), min(k, len(pool)))
    return sorted(_sharpest([pool[m] for m in group], sharpness) for group in groups)


def cluster_first(
    frames: Sequence[int],
    timestamps_ns: Sequence[int],
    sharpness: Sequence[float],
    features: Sequence[Sequence[float]],
    measure: str,
    k: int,
    gap_ns: int = DEFAULT_GAP_NS,
    cap: int = DEFAULT_CAP,
    ratio: float = GATE_RATIO,
) -> tuple[list[int], dict]:
    """Cluster all blur-gated frames, split clusters into time runs, keep the sharpest per run.

    More runs than ``cap`` drop the least sharp runs first. Returns (frames, info) where info has
    the cluster sizes, run counts and how many runs the cap removed.
    """
    if not frames:
        return [], {"clusters": [], "runs": 0, "dropped_by_cap": 0}
    limit = ratio * _median([sharpness[i] for i in frames])
    gated = [i for i in frames if sharpness[i] >= limit]
    groups = average_linkage(_distances(gated, features, measure), min(k, len(gated)))
    reps: list[int] = []
    info_clusters = []
    for group in groups:
        members = sorted(gated[m] for m in group)
        runs, current = [], [members[0]]
        for a, b in pairwise(members):
            if timestamps_ns[b] - timestamps_ns[a] > gap_ns:
                runs.append(current)
                current = [b]
            else:
                current.append(b)
        runs.append(current)
        reps += [_sharpest(run, sharpness) for run in runs]
        info_clusters.append({"size": len(members), "runs": len(runs)})
    runs_total, dropped = len(reps), 0
    while len(reps) > cap:
        reps.remove(min(reps, key=lambda i: (sharpness[i], timestamps_ns[i])))
        dropped += 1
    return sorted(reps), {
        "clusters": info_clusters,
        "runs": runs_total,
        "dropped_by_cap": dropped,
    }


def _median(values: Sequence[float]) -> float:
    s = sorted(values)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


# --- one arm of an experiment -----------------------------------------------------------------


def select_frames(
    arm: Mapping,
    timestamps_ns: Sequence[int],
    sharpness: Sequence[float],
    features: Mapping[str, Sequence[Sequence[float]]],
    replicate: int,
    replicates: int,
    clip: str,
) -> list[int]:
    """Frame indices an arm sends for one clip and replicate.

    Time-bin arms (``scheme`` "phase", the default) shift the grid by ``replicate / replicates``
    of a bin; ``cluster_first`` arms (``scheme`` "stride") use every ``replicates``-th frame
    starting at ``replicate``. Arm types: time_bins, drop_similar, random_drop, uniform,
    cluster_pool, cluster_first.
    """
    kind = arm["type"]
    phase = replicate / replicates
    if kind == "cluster_first":
        pool = [i for i in range(len(timestamps_ns)) if i % replicates == replicate]
        chosen, _ = cluster_first(
            pool,
            timestamps_ns,
            sharpness,
            features[arm["measure"]],
            arm["measure"],
            arm["k"],
            round(arm.get("gap_s", 0.4) * 1e9),
            arm.get("cap", DEFAULT_CAP),
        )
        return chosen
    if kind == "uniform":
        gated = [i for i, ok in enumerate(fs.passes_gate(sharpness)) if ok] or [0]
        return uniform(gated, arm["count"])
    if kind == "cluster_pool":
        pool = phased_time_bins(timestamps_ns, sharpness, arm.get("pool_bins", 20), phase)
        return cluster_pool(pool, sharpness, features[arm["measure"]], arm["measure"], arm["k"])
    base = phased_time_bins(
        timestamps_ns, sharpness, arm.get("base_bins", arm.get("bins", 10)), phase
    )
    if kind == "time_bins":
        return base
    if kind == "drop_similar":
        return drop_similar(base, sharpness, features[arm["measure"]], arm["measure"], arm["drop"])
    if kind == "random_drop":
        seed = f"{clip}|{replicate}|{arm.get('seed', 0)}"
        return random_drop(base, arm["drop"], seed)
    raise ValueError(f"unknown arm type {kind!r}")


# --- OpenCV features --------------------------------------------------------------------------


def frame_features(frame_bgr, measures: Sequence[str]) -> dict[str, list[float]]:
    """Feature vectors of one BGR frame for the requested measures.

    ``edge``: Sobel magnitude on a 64x36 grayscale copy; ``gray``: 16x9 grayscale after a blur;
    ``hist``: 16x8 hue/saturation histogram (normalised). Needs OpenCV and numpy, which the
    server environment does not include (declare them on the command line).
    """
    import cv2

    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    out: dict[str, list[float]] = {}
    if "edge" in measures:
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1)
        small = cv2.resize(cv2.magnitude(gx, gy), (64, 36), interpolation=cv2.INTER_AREA)
        out["edge"] = small.ravel().tolist()
    if "gray" in measures:
        blurred = cv2.GaussianBlur(gray, (0, 0), 8)
        out["gray"] = cv2.resize(blurred, (16, 9), interpolation=cv2.INTER_AREA).ravel().tolist()
    if "hist" in measures:
        hsv = cv2.cvtColor(cv2.resize(frame_bgr, (160, 90)), cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [16, 8], [0, 180, 0, 256]).ravel()
        out["hist"] = (hist / hist.sum()).tolist()
    return out


def frame_sharpness(frame_bgr) -> float:
    """Variance of the Laplacian on a copy whose long side is 256 px (as the app computes it)."""
    import cv2

    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    scale = 256 / max(h, w)
    small = cv2.resize(
        gray,
        (max(1, round(w * scale)), max(1, round(h * scale))),
        interpolation=cv2.INTER_AREA,
    )
    return float(cv2.Laplacian(small, cv2.CV_64F).var())
