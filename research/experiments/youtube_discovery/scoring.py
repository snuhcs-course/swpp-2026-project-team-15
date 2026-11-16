# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Pure scoring for the YouTube discovery study (no network)."""

from __future__ import annotations

import re
from statistics import median

ID_RE = re.compile(r"(?:v=|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})")


def norm(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


def names_dish(title: str, name: str) -> bool:
    n = norm(name)
    return bool(n) and n in norm(title)


def names_any(title: str, names: list[str]) -> bool:
    return any(names_dish(title, n) for n in names)


def extract_ids(text: str, citation_urls: list[str]) -> list[str]:
    """Distinct video ids in first-seen order, from the answer text then the citations."""
    seen: dict[str, None] = {}
    for chunk in [text, *citation_urls]:
        for vid in ID_RE.findall(chunk or ""):
            seen.setdefault(vid)
    return list(seen)


def keep_top(videos: list[dict], name: str, keep: int = 3) -> list[dict]:
    """Embeddable public videos whose title names the dish, most viewed first."""
    named = [v for v in videos if names_dish(v["title"], name)]
    return sorted(named, key=lambda v: v["view_count"] or 0, reverse=True)[:keep]


def ratio(num: int, den: int) -> float | None:
    return num / den if den else None


def summarize(rows: list[dict]) -> dict:
    """Aggregate per-dish rows of one method.

    Row keys: extracted (ids from the model; None for A), existing, embeddable,
    named (candidates naming the dish), named_loose, kept_views (list), kept,
    cost_usd, search_calls, videos_calls, latency_s (list), candidates_comparable.
    """
    cand = [r for r in rows if r.get("candidates_comparable", True)]
    emb = sum(r["embeddable"] for r in cand)
    ext = sum(r["extracted"] for r in rows if r.get("extracted") is not None)
    exi = sum(r["existing"] for r in rows if r.get("extracted") is not None)
    existing_all = sum(r["existing"] for r in rows)
    views = [v for r in rows for v in r["kept_views"] if v is not None]
    lat = [x for r in rows for x in r["latency_s"]]
    return {
        "dishes": len(rows),
        "relevance_strict": ratio(sum(r["named"] for r in cand), emb),
        "relevance_loose": ratio(sum(r["named_loose"] for r in cand), emb),
        "embeddable_share": ratio(sum(r["embeddable"] for r in rows), existing_all),
        "existence_rate": ratio(exi, ext) if ext else None,
        "coverage": ratio(sum(1 for r in rows if r["kept"] >= 3), len(rows)),
        "median_views": median(views) if views else None,
        "cost_usd_per_dish": ratio_f(sum(r["cost_usd"] for r in rows), len(rows)),
        "quota_units": sum(100 * r["search_calls"] + r["videos_calls"] for r in rows),
        "median_latency_s": median(lat) if lat else None,
    }


def ratio_f(num: float, den: int) -> float | None:
    return num / den if den else None


def decide(a: dict, b: dict, rule: dict) -> dict:
    """Apply the frozen rule to one model-discovery method; a is A on the paired dishes."""
    r = rule["prefer_model_discovery_if_all"]
    checks = {
        "relevance": b["relevance_strict"] is not None
        and a["relevance_strict"] is not None
        and b["relevance_strict"] >= a["relevance_strict"] + r["relevance_strict_min_delta_vs_A"],
        "coverage": b["coverage"] is not None
        and a["coverage"] is not None
        and b["coverage"] >= a["coverage"] + r["coverage_min_delta_vs_A"],
        "kept_embeddable": True,
        "existence": b["existence_rate"] is not None
        and b["existence_rate"] >= r["existence_rate_min"],
        "cost": b["cost_usd_per_dish"] is not None
        and b["cost_usd_per_dish"] <= r["cost_usd_per_dish_max"],
    }
    return {"checks": checks, "passes": all(checks.values())}
