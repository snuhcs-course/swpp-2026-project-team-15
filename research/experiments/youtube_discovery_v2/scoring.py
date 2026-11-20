# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Pure functions of study v2: candidate features, judges, ranking, selection (no network)."""

from __future__ import annotations

import json
import random
import re
from collections.abc import Callable
from statistics import median

from sklearn.metrics import cohen_kappa_score  # Cohen (1960), the textbook formula

ID_RE = re.compile(r"(?:v=|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})")
DUR_RE = re.compile(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$")
HANGUL = re.compile("[가-힣]")
RANKINGS = ("views", "like_ratio", "recency", "views_channel")
MIN_VIEWS_FOR_RATIO = 1000


def norm(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


def title_names_dish(title: str, name: str) -> bool:
    """Old rule (judge J0): the title contains the dish name (spaces, punctuation ignored)."""
    n = norm(name)
    return bool(n) and n in norm(title)


def extract_ids(text: str, citation_urls: list[str], limit: int = 12) -> list[str]:
    seen: dict[str, None] = {}
    for chunk in [text, *citation_urls]:
        for vid in ID_RE.findall(chunk or ""):
            seen.setdefault(vid)
    return list(seen)[:limit]


def duration_seconds(iso: str | None) -> int | None:
    m = DUR_RE.match(iso or "")
    if not m or not any(m.groups()):
        return None
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s


def to_candidate(item: dict) -> dict:
    """Flatten one raw videos.list item; `usable` = public and embeddable (API fields)."""
    sn, st, stat = item.get("snippet", {}), item.get("status", {}), item.get("statistics", {})
    views = stat.get("viewCount")
    likes = stat.get("likeCount")
    title = sn.get("title", "")
    return {
        "video_id": item["id"],
        "title": title,
        "channel": sn.get("channelTitle", ""),
        "channel_id": sn.get("channelId", ""),
        "description": (sn.get("description") or "")[:500],
        "tags": (sn.get("tags") or [])[:8],
        "published_at": sn.get("publishedAt", ""),
        "duration_s": duration_seconds(item.get("contentDetails", {}).get("duration")),
        "views": int(views) if views is not None else None,
        "likes": int(likes) if likes is not None else None,
        "usable": bool(st.get("embeddable")) and st.get("privacyStatus", "public") == "public",
        "hangul_title": bool(HANGUL.search(title)),
    }


def is_short(c: dict) -> bool:
    return c.get("duration_s") is not None and c["duration_s"] <= 60


def like_ratio(c: dict) -> float:
    v, lk = c.get("views"), c.get("likes")
    if not v or v < MIN_VIEWS_FOR_RATIO or lk is None:
        return -1.0
    return lk / v


def rank(cands: list[dict], how: str, k: int = 3) -> list[dict]:
    """Top k of the candidates by one ranking. Ties keep the input order (stable sort)."""
    if how == "views":
        ordered = sorted(cands, key=lambda c: c.get("views") or 0, reverse=True)
    elif how == "like_ratio":
        ordered = sorted(cands, key=like_ratio, reverse=True)
    elif how == "recency":
        ordered = sorted(cands, key=lambda c: c.get("published_at", ""), reverse=True)
    elif how == "views_channel":
        by_views = sorted(cands, key=lambda c: c.get("views") or 0, reverse=True)
        seen: set[str] = set()
        first, rest = [], []
        for c in by_views:
            ch = c.get("channel_id") or c["video_id"]
            (rest if ch in seen else first).append(c)
            seen.add(ch)
        ordered = first + rest  # one per channel first, repeats only fill the remaining slots
    else:
        raise ValueError(f"unknown ranking {how}")
    return ordered[:k]


def choose(cands: list[dict], relevant: Callable[[dict], bool], how: str, k: int = 3) -> list[dict]:
    return rank([c for c in cands if c["usable"] and relevant(c)], how, k)


def precision_at(chosen: list[dict], is_relevant: Callable[[dict], bool], k: int = 3) -> float:
    """Relevant chosen videos over k slots; empty slots count as misses."""
    return sum(1 for c in chosen if is_relevant(c)) / k


def cohen_kappa(a: list[bool], b: list[bool]) -> float | None:
    n = len(a)
    if n == 0 or n != len(b):
        return None
    pa, pb = sum(a) / n, sum(b) / n
    if pa * pb + (1 - pa) * (1 - pb) == 1:  # chance agreement is total: kappa is undefined
        return None
    return float(cohen_kappa_score(a, b))


def confusion(truth: list[bool], pred: list[bool]) -> dict:
    tp = sum(t and p for t, p in zip(truth, pred, strict=True))
    fp = sum((not t) and p for t, p in zip(truth, pred, strict=True))
    fn = sum(t and (not p) for t, p in zip(truth, pred, strict=True))
    tn = sum((not t) and (not p) for t, p in zip(truth, pred, strict=True))
    return {
        "n": len(truth),
        "agreement": (tp + tn) / len(truth) if truth else None,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "kappa": cohen_kappa(truth, pred),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
    }


def parse_judgements(text: str, keys: list[str]) -> dict[str, bool] | None:
    """Strict-JSON answer {"judgements":[{"i":key,"relevant":bool,"reason":str}]}; None if unusable.

    Every requested key must be present exactly once with a boolean, otherwise the whole answer is
    rejected (a partial answer would silently count as irrelevant).
    """
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
        rows = data["judgements"]
        out = {str(r["i"]): r["relevant"] for r in rows}
    except (ValueError, KeyError, TypeError):
        return None
    if set(out) != set(keys) or len(rows) != len(keys):
        return None
    if not all(isinstance(v, bool) for v in out.values()):
        return None
    return out


def bootstrap_diff(
    a: list[float], b: list[float], seed: int, reps: int = 10000
) -> tuple[float, float, float]:
    """Mean paired difference a-b with a percentile 95% interval over resampled dishes."""
    n = len(a)
    diffs = [x - y for x, y in zip(a, b, strict=True)]
    mean = sum(diffs) / n
    rng = random.Random(seed)
    means = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / n for _ in range(reps))
    return mean, means[int(0.025 * reps)], means[int(0.975 * reps) - 1]


def decide(
    table: dict[str, dict], baseline: str, seed: int, per_dish_p3: dict[str, list[float]]
) -> dict:
    """Frozen rule. table[combo] = {coverage, p3, cost, search_calls}; combo = method|judge|rank."""
    best_cov = max(r["coverage"] for r in table.values())
    eligible = {c: r for c, r in table.items() if r["coverage"] >= 0.9 * best_cov}
    ordered = sorted(
        eligible,
        key=lambda c: (-eligible[c]["p3"], eligible[c]["cost"], eligible[c]["search_calls"]),
    )
    winner = ordered[0]
    mean, lo, hi = bootstrap_diff(per_dish_p3[winner], per_dish_p3[baseline], seed)
    verdict = (
        "winner is the baseline"
        if winner == baseline
        else "inconclusive"
        if lo <= 0 <= hi
        else ("better" if mean > 0 else "worse")
    )
    return {
        "best_coverage": best_cov,
        "eligible": len(eligible),
        "winner": winner,
        "vs_baseline": {"mean_diff": mean, "ci95": [lo, hi], "verdict": verdict},
    }


def median_or_none(xs: list[float]) -> float | None:
    return median(xs) if xs else None
