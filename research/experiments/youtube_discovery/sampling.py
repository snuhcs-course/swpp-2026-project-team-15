# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Seeded, stratified choice of the dishes used in the YouTube discovery study."""

from __future__ import annotations

import random
from collections import Counter


def build_sample(dishes: list[dict], cached_ids: list[str], seed: int, extra: int) -> dict:
    """The cached dishes plus extra more drawn per category in proportion to its size.

    Category quotas use the largest-remainder rule over the dishes that are not cached; the dishes
    inside a category are drawn with random.Random(seed); the final order is shuffled with the
    same generator (the first 20 of the extra dishes are the ones that get a live API search).
    """
    rng = random.Random(seed)
    pool = [d for d in dishes if d["id"] not in set(cached_ids)]
    by_cat: dict[str, list[str]] = {}
    for d in sorted(pool, key=lambda d: d["id"]):
        by_cat.setdefault(d["category"], []).append(d["id"])
    total = len(pool)
    raw = {c: extra * len(v) / total for c, v in by_cat.items()}
    quota = {c: int(x) for c, x in raw.items()}
    left = extra - sum(quota.values())
    for c in sorted(raw, key=lambda c: (-(raw[c] - quota[c]), c))[:left]:
        quota[c] += 1
    picked: list[str] = []
    for c in sorted(by_cat):
        picked += rng.sample(by_cat[c], quota[c])
    rng.shuffle(picked)
    return {"cached": list(cached_ids), "extra": picked, "quota": dict(sorted(quota.items()))}


def category_counts(dishes: list[dict], ids: list[str]) -> Counter:
    by_id = {d["id"]: d["category"] for d in dishes}
    return Counter(by_id[i] for i in ids)
