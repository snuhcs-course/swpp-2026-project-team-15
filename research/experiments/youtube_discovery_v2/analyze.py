# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Offline analysis of study v2: judge validation, 32 combinations, the frozen decision rule."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import median

from . import scoring

METHODS = ("A1", "B", "B2", "U")
JUDGES = ("J0", "J1")


def load(data: Path, name: str, default):
    p = data / name
    return json.loads(p.read_text("utf-8")) if p.exists() else default


def dish_names() -> dict[str, dict]:
    repo = Path(__file__).resolve().parents[3]
    raw = json.loads((repo / "server" / "app" / "dishes" / "dishes.json").read_text("utf-8"))
    return {d["id"]: d for d in raw["dishes"]}


def method_ids(row: dict, method: str) -> list[str]:
    m = row["methods"]
    if method == "U":
        return list(dict.fromkeys(i for k in ("A1", "B", "B2") for i in (m.get(k) or [])))
    return list(m.get(method) or [])


def validation(data: Path, labels: dict) -> dict:
    sample = load(data, "validation_judgements.json", {})
    rows = load(data, "sample.json", [])
    table = dish_names()
    keys = [f"{r['dish']}:{r['video_id']}" for r in rows]
    truth = [labels[k]["relevant"] for k in keys]
    out = {}
    j0 = [scoring.title_names_dish(r["title"], table[r["dish"]]["name"]) for r in rows]
    out["J0"] = scoring.confusion(truth, j0)
    for model, res in sample.items():
        got = (res or {}).get("judgements")
        if got:
            out[model] = scoring.confusion(truth, [got[k] for k in keys])
    # the old rule on the subsets it is suspected to fail on
    for name, pick in (
        ("non_hangul", lambda r: not r["hangul_title"]),
        (
            "ko_unnamed",
            lambda r: (
                r["hangul_title"]
                and not scoring.title_names_dish(r["title"], table[r["dish"]]["name"])
            ),
        ),
    ):
        idx = [i for i, r in enumerate(rows) if pick(r)]
        out[f"J0_on_{name}"] = scoring.confusion([truth[i] for i in idx], [j0[i] for i in idx])
    return out


def one_combo(store: dict, judged: dict, table: dict, dishes: list[str], combo: tuple) -> tuple:
    method, judge, how = combo
    p3s: list[float] = []
    chosen_n = rel_n = full = zero = english = 0
    views: list[int] = []
    cost = 0.0
    for did in dishes:
        row = store[did]
        pool = [row["videos"][i] for i in method_ids(row, method) if i in row["videos"]]
        ev = (judged.get(did, {}).get("E") or {}).get("judgements") or {}
        sel = (judged.get(did, {}).get("J1") or {}).get("judgements") or {}
        dn = table[did]["name"]

        def relevant(c, dn=dn, sel=sel):
            if judge == "J0":
                return scoring.title_names_dish(c["title"], dn)
            return bool(sel.get(c["video_id"]))

        def is_rel(c, ev=ev):
            return bool(ev.get(c["video_id"]))

        chosen = scoring.choose(pool, relevant, how)
        p3s.append(scoring.precision_at(chosen, is_rel))
        chosen_n += len(chosen)
        rel_n += sum(is_rel(c) for c in chosen)
        views += [c["views"] for c in chosen if c["views"] is not None]
        english += sum(1 for c in chosen if not c["hangul_title"] and is_rel(c))
        full += len(chosen) == 3
        zero += not any(is_rel(c) for c in chosen)
        for m in ("B", "B2") if method == "U" else (method,):
            cost += (row["cost"].get(m) or {}).get("cost") or 0
        if judge == "J1":
            cost += (judged.get(did, {}).get("J1") or {}).get("cost") or 0
    n = len(dishes)
    return p3s, {
        "dishes": n,
        "p3": sum(p3s) / n if n else None,
        "precision_chosen": rel_n / chosen_n if chosen_n else None,
        "coverage": full / n if n else None,
        "zero_relevant": zero,
        "median_views": median(views) if views else None,
        "english_relevant_chosen": english,
        "cost": cost / n if n else None,
        "search_calls": (1.0 if method in ("A1", "U") else 0.0),
    }


def combos(data: Path, trusted: dict[str, bool]) -> tuple[dict, dict, dict, dict]:
    store = load(data, "candidates.json", {})
    judged = load(data, "judgements.json", {})
    table = dish_names()
    paired = [d for d, r in store.items() if r["methods"].get("A1") is not None]
    rows: dict[str, dict] = {}
    per_dish: dict[str, list[float]] = {}
    all_rows: dict[str, dict] = {}
    for method in METHODS:
        for judge in JUDGES:
            for how in scoring.RANKINGS:
                name = f"{method}|{judge}|{how}"
                p3s, stats = one_combo(store, judged, table, paired, (method, judge, how))
                rows[name] = {**stats, "trusted": trusted.get(judge, False)}
                per_dish[name] = p3s
                if method in ("B", "B2"):
                    _, all_stats = one_combo(
                        store, judged, table, list(store), (method, judge, how)
                    )
                    all_rows[name] = all_stats
    return rows, per_dish, all_rows, {"paired": len(paired), "dishes": len(store)}


def main(data: Path, crit: dict, here: Path, selector: str, evaluator: str) -> None:
    labels = json.loads((here / "labels.json").read_text("utf-8"))["labels"]
    val = validation(data, labels)

    def kappa(t):
        return (val.get(t) or {}).get("kappa")

    trusted = {
        "J0": True,
        "J1": (kappa(selector) or 0) >= 0.6,
        "E": (kappa(evaluator) or 0) >= 0.6,
    }
    rows, per_dish, all_rows, meta = combos(data, trusted)
    out = {
        "validation": val,
        "trusted": trusted,
        "combos": rows,
        "model_methods_all_dishes": all_rows,
        **meta,
    }
    if trusted["E"]:
        cand = {c: r for c, r in rows.items() if r["trusted"] and r["p3"] is not None}
        out["decision"] = scoring.decide(cand, crit["baseline"], crit["seed"], per_dish)
    else:
        out["decision"] = "no decision: the evaluator judge is not trusted (kappa < 0.6)"
    (data / "analysis.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "validation": {
                    k: {x: v[x] for x in ("n", "agreement", "kappa")} for k, v in val.items()
                },
                "trusted": trusted,
                "decision": out["decision"],
            },
            ensure_ascii=False,
            indent=1,
        )
    )
