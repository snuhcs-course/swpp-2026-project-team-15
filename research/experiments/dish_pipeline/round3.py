# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Round 3 of the pipeline study: wording of the request that asks a web-search model for links.

Pure functions only (no network): the four request texts, link and video feature helpers, the
neighbour-dish rule, the metrics of one variant and the frozen decision rule. The judge prompt and
the video features are copies of the second YouTube discovery study so the judge stays the same
instrument (see ``criteria_round3.json``).
"""

from __future__ import annotations

import json
import random
import re
from statistics import median

ID_RE = re.compile(r"(?:v=|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})")
DUR_RE = re.compile(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$")
HANGUL = re.compile("[가-힣]")
VARIANTS = ("D0", "D1", "D2", "D3")
SHORT_SECONDS = 60
VLOG_WORDS = ("브이로그", "vlog", "먹방", "mukbang", "리뷰", "review", "광고", "협찬", "asmr")

_TAIL = (
    " 한국어 영상뿐 아니라 어떤 언어의 영상이든 괜찮습니다."
    " 각 영상의 watch?v= 주소와 제목을 JSON 배열로만 답하고,"
    " 검색 결과에서 실제로 확인한 주소만 쓰세요."
)
_HEAD = (
    "YouTube에서 '{dish}'를 보고 따라 하며 만들 수 있는 요리 영상"
    "(만드는 방법을 보여 주는 레시피 영상)을 최대 8개 찾아 주세요."
)
_D1 = " 혼자 처음 요리해 보는 청년, 즉 자취생이 따라 하기 위한 영상이면 좋습니다."
_D2 = (
    " 재료가 적게 들고, 도구가 간단하며,"
    " 화면만 보고도 단계를 따라 하기 쉽고, 길이가 짧은 영상을 찾아 주세요."
)
_D3 = (
    " 정확히 '{dish}'를 만드는 영상만 고르고 이웃 요리나 변형 요리는 제외하세요."
    " 쇼츠, 브이로그, 먹방, 리뷰, 광고는 제외하세요."
)
_EXTRA = {"D0": "", "D1": _D1, "D2": _D2, "D3": _D2 + _D3}


def request_text(variant: str, dish: str) -> str:
    """The exact user message of one variant (the model is gemini-2.5-flash-lite:online)."""
    if variant not in _EXTRA:
        raise ValueError(f"unknown variant {variant}")
    return (_HEAD + _EXTRA[variant] + _TAIL).format(dish=dish)


def norm(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


def title_names_dish(title: str, name: str) -> bool:
    n = norm(name)
    return bool(n) and n in norm(title)


def extract_ids(text: str, citation_urls: list[str], limit: int = 12) -> list[str]:
    """Video ids from the answer text, then the url citations, in that order, without repeats."""
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
    """Flatten one videos.list item; usable = public and embeddable (API fields)."""
    sn, st, stat = item.get("snippet", {}), item.get("status", {}), item.get("statistics", {})
    views, likes, title = stat.get("viewCount"), stat.get("likeCount"), sn.get("title", "")
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
    return c.get("duration_s") is not None and c["duration_s"] <= SHORT_SECONDS


def has_jachwi(c: dict) -> bool:
    """The keyword effect: 자취 in the title or in the tags."""
    return "자취" in c.get("title", "") or any("자취" in t for t in c.get("tags", []))


def failure_type(c: dict, dish: dict, catalog: list[dict]) -> str:
    """Rule-based type of a usable link the evaluator calls irrelevant (a proxy, not a judgement).

    short -> vlog_or_show -> neighbour_dish (another dish of the same category is named in the
    title and this dish is not) -> other_dish (a dish of another category is named) -> other.
    """
    if is_short(c):
        return "short"
    hay = (c["title"] + " " + " ".join(c.get("tags", []))).lower()
    if any(w in hay for w in VLOG_WORDS):
        return "vlog_or_show"
    if title_names_dish(c["title"], dish["name"]):
        return "other"
    named = [
        d for d in catalog if d["id"] != dish["id"] and title_names_dish(c["title"], d["name"])
    ]
    if any(d["category"] == dish["category"] for d in named):
        return "neighbour_dish"
    return "other_dish" if named else "other"


def parse_judgements(text: str, keys: list[str]) -> dict[str, bool] | None:
    """Strict JSON {"judgements":[{"i","relevant","reason"}]}; every key exactly once, else None."""
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        rows = json.loads(m.group(0))["judgements"]
        out = {str(r["i"]): r["relevant"] for r in rows}
    except (ValueError, KeyError, TypeError):
        return None
    if set(out) != set(keys) or len(rows) != len(keys):
        return None
    return out if all(isinstance(v, bool) for v in out.values()) else None


def cohen_kappa(a: list[bool], b: list[bool]) -> float | None:
    n = len(a)
    if n == 0 or n != len(b):
        return None
    po = sum(x == y for x, y in zip(a, b, strict=True)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return None if pe == 1 else (po - pe) / (1 - pe)


def quartiles(xs: list[float]) -> tuple[float, float, float] | None:
    if not xs:
        return None
    s = sorted(xs)

    def at(p: float) -> float:
        k = (len(s) - 1) * p
        lo = int(k)
        hi = min(lo + 1, len(s) - 1)
        return s[lo] + (s[hi] - s[lo]) * (k - lo)

    return at(0.25), at(0.5), at(0.75)


def variant_metrics(rows: list[dict], judge: str) -> dict:
    """Metrics of one variant. Each row is one dish: {"links": [usable link dicts in the model's
    order, each with "rel" = {"E": bool, "J1": bool}], "provided": n, "exist": n, "cost": x,
    "latency_s": x, "error": bool}. ``judge`` is the judge ("E" or "J1") of the relevance figures.
    """
    links = [lk for r in rows for lk in r["links"]]
    rel = [lk for lk in links if lk["rel"][judge]]
    firsts = [r["links"][0]["rel"][judge] for r in rows if r["links"]]
    durations = [lk["duration_s"] for lk in links if lk.get("duration_s") is not None]
    return {
        "dishes": len(rows),
        "provided": sum(r["provided"] for r in rows),
        "exist": sum(r["exist"] for r in rows),
        "usable": len(links),
        "usable_per_dish": len(links) / len(rows) if rows else 0.0,
        "relevant": len(rel),
        "relevant_share": len(rel) / len(links) if links else None,
        "dishes_with_relevant": sum(any(lk["rel"][judge] for lk in r["links"]) for r in rows),
        "first_link_relevant": sum(firsts) / len(firsts) if firsts else None,
        "shorts_share": sum(is_short(lk) for lk in links) / len(links) if links else None,
        "duration_s_quartiles": quartiles(durations),
        "jachwi_share": sum(has_jachwi(lk) for lk in links) / len(links) if links else None,
        "cost_per_request": sum(r["cost"] for r in rows) / len(rows) if rows else None,
        "latency_median_s": median([r["latency_s"] for r in rows]) if rows else None,
        "errors": sum(bool(r["error"]) for r in rows),
    }


def pooled_diff(a: list[dict], b: list[dict], judge: str, seed: int, reps: int = 10000):
    """Paired difference (a - b) of the pooled relevant share with a percentile 95% interval.

    ``a`` and ``b`` hold the same dishes in the same order; dishes are resampled with replacement
    and the pooled share (relevant / usable links over the resampled dishes) is recomputed.
    """

    def counts(r: dict) -> tuple[int, int]:
        return sum(lk["rel"][judge] for lk in r["links"]), len(r["links"])

    ca, cb = [counts(r) for r in a], [counts(r) for r in b]
    n = len(ca)

    def share(cs: list[tuple[int, int]]) -> float:
        tot = sum(t for _, t in cs)
        return sum(x for x, _ in cs) / tot if tot else 0.0

    mean = share(ca) - share(cb)
    rng = random.Random(seed)
    diffs = []
    for _ in range(reps):
        idx = [rng.randrange(n) for _ in range(n)]
        diffs.append(share([ca[i] for i in idx]) - share([cb[i] for i in idx]))
    diffs.sort()
    return mean, diffs[int(0.025 * reps)], diffs[int(0.975 * reps) - 1]


def decide(metrics: dict[str, dict], diffs: dict[str, tuple[float, float, float]]) -> dict:
    """Frozen rule. metrics[variant] from variant_metrics (judge E); diffs[variant] = pooled_diff
    against D0 (not for D0). The default is D0."""
    base = metrics["D0"]
    ok = [
        v
        for v, m in metrics.items()
        if m["relevant_share"] is not None
        and m["dishes_with_relevant"] >= base["dishes_with_relevant"] - 1
        and m["usable_per_dish"] >= base["usable_per_dish"] - 0.5
    ]
    ordered = sorted(
        ok, key=lambda v: (-metrics[v]["relevant_share"], metrics[v]["cost_per_request"] or 0)
    )
    winner = ordered[0] if ordered else "D0"
    verdict = "winner is D0"
    if winner != "D0":
        _, lo, hi = diffs[winner]
        verdict = "inconclusive, keep D0" if lo <= 0 <= hi else "adopt " + winner
    return {"eligible": ok, "winner_by_share": winner, "verdict": verdict}


def shuffled(keys: list[str], seed: int) -> list[str]:
    out = list(keys)
    random.Random(seed).shuffle(out)
    return out
