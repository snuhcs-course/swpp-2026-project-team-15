# AI-generated with Claude Code (Opus 5.5), 2026-11-20; reviewed by Jaehyuk Choi.
"""The research statistics now come from libraries; the recorded numbers must not move."""

import random

from experiments.dish_pipeline import analyze_links, round3
from experiments.youtube_discovery_v2 import scoring
from statsmodels.stats.proportion import proportion_confint


def textbook_kappa(a, b):
    n = len(a)
    po = sum(x == y for x, y in zip(a, b, strict=True)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return None if pe == 1 else (po - pe) / (1 - pe)


def test_library_kappa_equals_the_formula_the_records_used():
    rng = random.Random(0)
    for _ in range(500):
        n = rng.randint(2, 60)
        a = [rng.random() < rng.random() for _ in range(n)]
        b = [rng.random() < 0.5 for _ in range(n)]
        want = textbook_kappa(a, b)
        for kappa in (analyze_links.kappa, round3.cohen_kappa, scoring.cohen_kappa):
            got = kappa(a, b)
            assert (got is None and want is None) or abs(got - want) < 1e-12


def test_recorded_wilson_intervals_are_reproduced():
    # ADR 004 / dish_revision round 3: 5 of 24 (recorded as 9% to 41%, corrected to 40%)
    lo, hi = proportion_confint(5, 24, method="wilson")
    assert (round(lo * 100), round(hi * 100)) == (9, 40)  # 40.47 %: the record said 41 %
    # dish_recipes link verification: 19 of 21, "71% to 97%"
    lo, hi = proportion_confint(19, 21, method="wilson")
    assert (round(lo * 100), round(hi * 100)) == (71, 97)
