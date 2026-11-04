# AI-generated with Claude Code (Sonnet 5.5), 2026-11-03; reviewed by Jaehyuk Choi.
"""Scoring for the multi-frame recognition evaluation: matching, metrics, merges, bootstrap.

The unit of analysis is the fridge (a scene). Nothing here calls a model or opens a photo; it only
compares name lists. Pass/fail is reported only against a frozen thresholds file.

Answer key (answer_key.json):
  {"fridges": {"<id>": [{"id": "egg", "names": ["달걀", "계란"], "status": "visible"}]},
   "scenes": [["<id>", ...], ...]}
Prediction file, one entry per call group:
  {"runs": [{"fridge": "<id>", "variant": "overlap", "repeat": 0,
             "frames": [["달걀"], ["우유", "달걀"]],  # per-frame names, merged here; or
             "candidates": ["달걀", ...],                  # an already merged list
             "schema_valid": true, "latency_ms": 1234, "prompt_tokens": 1500, "frames_sent": 8}]}

Usage from the repository root:
  PYTHONPATH=research uv run --project server --locked \\
      python -m experiments.capture.recognition.score KEY.json PREDICTIONS.json OUT.json
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import unicodedata
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
AMBIGUOUS_POLICIES = ("exclude", "count_as_item")


def norm(text: str) -> str:
    return "".join(unicodedata.normalize("NFC", text).lower().split())


def name_matches(candidate: str, allowed: list[str]) -> bool:
    """True when the normalized candidate equals, contains or is contained in an allowed name.

    Allowed names shorter than two characters never match, so a one-character name (쌀, 무, 김)
    cannot match every candidate that contains it. Such an item needs a longer allowed name; the
    alias map (see merge) can rewrite a short candidate into a longer one before matching.
    """
    c = norm(candidate)
    if not c:
        return False
    for raw in allowed:
        a = norm(raw)
        if len(a) >= 2 and (a in c or (len(c) >= 2 and c in a)):
            return True
    return False


def match_fridge(
    items: list[dict], candidates: list[str], ambiguous_policy: str = "exclude"
) -> dict:
    """One-to-one greedy assignment in key order: each item is found once, each candidate used once.

    A candidate that only matches an ambiguous item is ignored under "exclude" (neither found nor
    extra) and treated like a visible item under "count_as_item".
    """
    if ambiguous_policy not in AMBIGUOUS_POLICIES:
        raise ValueError(f"unknown ambiguous policy {ambiguous_policy}")
    visible = [i for i in items if i.get("status", "visible") == "visible"]
    ambiguous = [i for i in items if i.get("status") == "ambiguous"]
    scored = visible + (ambiguous if ambiguous_policy == "count_as_item" else [])
    used: set[int] = set()
    found, missed = [], []
    for item in scored:
        hit = next(
            (
                k
                for k, c in enumerate(candidates)
                if k not in used and name_matches(c, item["names"])
            ),
            None,
        )
        if hit is None:
            missed.append(item["id"])
        else:
            used.add(hit)
            found.append(item["id"])
    ignored = []
    if ambiguous_policy == "exclude":
        for k, c in enumerate(candidates):
            if k not in used and any(name_matches(c, i["names"]) for i in ambiguous):
                used.add(k)
                ignored.append(c)
    extra = [c for k, c in enumerate(candidates) if k not in used]
    return {"found": found, "missed": missed, "extra": extra, "ignored": ignored}


def metrics(m: dict) -> dict:
    n_true = len(m["found"]) + len(m["missed"])
    n_pred = len(m["found"]) + len(m["extra"])
    return {
        "recall": len(m["found"]) / n_true if n_true else None,
        "precision": len(m["found"]) / n_pred if n_pred else None,
        "false_recognition": len(m["extra"]) / n_pred if n_pred else None,
        # edits on the confirmation screen: items to add plus items to delete
        "fix_count": len(m["missed"]) + len(m["extra"]),
        "n_true": n_true,
        "n_pred": n_pred,
    }


def merge(
    frames: list[list[str]], strategy: str, alias: dict[str, str] | None = None
) -> list[str]:
    """M1 union; M2 names seen in two or more frames; M3 union (the caller scores "to confirm").

    Names are deduplicated after normalization and the optional alias map (variant -> canonical).
    The result keeps first-seen order, so scoring does not depend on the interpreter's hash seed.
    """
    amap = {norm(k): v for k, v in (alias or {}).items()}
    counts: dict[str, int] = defaultdict(int)
    shown: dict[str, str] = {}
    for fr in frames:
        keys: dict[str, None] = {}
        for name in fr:
            key = amap.get(norm(name), norm(name))
            if key:
                keys[key] = None
                shown.setdefault(key, amap.get(norm(name), name.strip()))
        for key in keys:
            counts[key] += 1
    if strategy in ("M1", "M3"):
        return [shown[k] for k in counts]
    if strategy == "M2":
        return [shown[k] for k, c in counts.items() if c >= 2]
    raise ValueError(f"unknown merge strategy {strategy}")


def run_candidates(run: dict, merge_strategy: str = "M1", alias=None) -> list[str]:
    if "frames" in run:
        return merge(run["frames"], merge_strategy, alias)
    return list(run["candidates"])


def score_runs(
    key: dict,
    runs: list[dict],
    ambiguous_policy: str = "exclude",
    merge_strategy: str = "M1",
    alias=None,
) -> list[dict]:
    rows = []
    for run in runs:
        items = key["fridges"][run["fridge"]]
        m = match_fridge(
            items, run_candidates(run, merge_strategy, alias), ambiguous_policy
        )
        rows.append(
            {
                "fridge": run["fridge"],
                "variant": run["variant"],
                "repeat": run.get("repeat", 0),
                **metrics(m),
                "schema_valid": run.get("schema_valid", True),
                "latency_ms": run.get("latency_ms"),
                "prompt_tokens": run.get("prompt_tokens"),
                "frames_sent": run.get("frames_sent"),
                "missed": m["missed"],
                "extra": m["extra"],
            }
        )
    return rows


def per_fridge(rows: list[dict], variant: str, metric: str) -> dict[str, float]:
    """Mean over repeats for each fridge; fridges where the metric is undefined are dropped."""
    acc: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        if r["variant"] == variant and r[metric] is not None:
            acc[r["fridge"]].append(r[metric])
    return {f: statistics.mean(v) for f, v in acc.items()}


def pooled(rows: list[dict], variant: str) -> dict:
    """Micro-average over fridges: total found / total true, and so on."""
    sel = [r for r in rows if r["variant"] == variant]
    n_true = sum(r["n_true"] for r in sel)
    n_pred = sum(r["n_pred"] for r in sel)
    found = sum(r["n_true"] - len(r["missed"]) for r in sel)
    return {
        "recall": found / n_true if n_true else None,
        "precision": found / n_pred if n_pred else None,
        "false_recognition": 1 - found / n_pred if n_pred else None,
        "fix_count_mean": statistics.mean(r["fix_count"] for r in sel) if sel else None,
        "schema_valid_rate": statistics.mean(r["schema_valid"] for r in sel)
        if sel
        else None,
    }


def bootstrap_ci(
    values: list[float], seed: int, reps: int = 10000, level: float = 0.95
) -> tuple[float, float]:
    rng = random.Random(seed)
    n = len(values)
    means = sorted(
        statistics.mean(rng.choice(values) for _ in range(n)) for _ in range(reps)
    )
    return means[int((1 - level) / 2 * reps)], means[int((1 + level) / 2 * reps) - 1]


def paired_difference(
    rows: list[dict],
    a: str,
    b: str,
    metric: str,
    seed: int,
    reps: int = 10000,
    scenes: list[list[str]] | None = None,
) -> dict:
    """Variant a minus variant b on the fridges both have, with a bootstrap interval.

    Without ``scenes`` the fridge is resampled. With ``scenes`` the per-fridge differences are
    averaged inside each scene and the scene is resampled, which respects that clips of one
    fridge are not independent.
    """
    pa, pb = per_fridge(rows, a, metric), per_fridge(rows, b, metric)
    common = sorted(set(pa) & set(pb))
    if scenes is None:
        diffs = [pa[f] - pb[f] for f in common]
    else:
        diffs = []
        for group in scenes:
            d = [pa[f] - pb[f] for f in group if f in common]
            if d:
                diffs.append(statistics.mean(d))
    if len(diffs) < 2:
        return {"n_units": len(diffs), "mean": None, "ci95": None}
    lo, hi = bootstrap_ci(diffs, seed, reps)
    return {
        "n_units": len(diffs),
        "mean": statistics.mean(diffs),
        "ci95": [lo, hi],
        "wins": sum(d > 0 for d in diffs),
        "losses": sum(d < 0 for d in diffs),
    }


def thresholds_frozen(th: dict) -> bool:
    metrics_ = th.get("metrics", {})
    return (
        th.get("status") == "FROZEN"
        and bool(metrics_)
        and all(v.get("value") is not None for v in metrics_.values())
    )


def judge(th: dict, summary: dict) -> dict:
    """Pass/fail only against frozen thresholds (value, op in {">=", "<="})."""
    if not thresholds_frozen(th):
        return {"status": "thresholds not frozen: no pass/fail is reported"}
    out = {}
    for name, rule in th["metrics"].items():
        got = summary.get(name)
        if got is None:
            out[name] = "no value"
        else:
            ok = got >= rule["value"] if rule["op"] == ">=" else got <= rule["value"]
            out[name] = {
                "value": got,
                "threshold": rule["value"],
                "op": rule["op"],
                "pass": ok,
            }
    return out


def evaluate(
    key: dict,
    runs: list[dict],
    th: dict,
    merge_strategy="M1",
    alias=None,
    seed=20261103,
) -> dict:
    rows = score_runs(
        key, runs, th.get("ambiguous_policy") or "exclude", merge_strategy, alias
    )
    variants = sorted({r["variant"] for r in rows})
    summary = {v: pooled(rows, v) for v in variants}
    scenes = key.get("scenes")
    paired = {
        f"{a}-{b}": {
            m: paired_difference(rows, a, b, m, seed, scenes=scenes)
            for m in ("recall", "false_recognition", "fix_count")
        }
        for a in variants
        for b in variants
        if a < b
    }
    return {
        "merge": merge_strategy,
        "ambiguous_policy": th.get("ambiguous_policy"),
        "variants": summary,
        "paired": paired,
        "verdict": {v: judge(th, summary[v]) for v in variants},
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("key")
    ap.add_argument("predictions")
    ap.add_argument("out")
    ap.add_argument("--thresholds", default=str(HERE / "thresholds.json"))
    ap.add_argument("--aliases", default=str(HERE / "aliases.json"))
    ap.add_argument("--merge", default="M1", choices=["M1", "M2", "M3"])
    ap.add_argument("--seed", type=int, default=20261103)
    args = ap.parse_args(argv)
    key = json.loads(Path(args.key).read_text(encoding="utf-8"))
    runs = json.loads(Path(args.predictions).read_text(encoding="utf-8"))["runs"]
    th = json.loads(Path(args.thresholds).read_text(encoding="utf-8"))
    alias = (
        json.loads(Path(args.aliases).read_text(encoding="utf-8"))
        if args.aliases
        else None
    )
    result = evaluate(key, runs, th, args.merge, alias, args.seed)
    Path(args.out).write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(
        json.dumps(
            {k: result[k] for k in ("variants", "verdict")},
            ensure_ascii=False,
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
