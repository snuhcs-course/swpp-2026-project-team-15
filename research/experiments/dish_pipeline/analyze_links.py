# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Round 2 (offline): how many model-provided links pass the embeddable check and are relevant.

Reads the stored outputs of the second YouTube discovery study (copied to
``data/youtube-discovery-v2/``; never committed) and prints the numbers listed in
``criteria_round2.json``. No model or API call.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path

from sklearn.metrics import cohen_kappa_score  # Cohen (1960), the textbook formula

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
DATA = REPO_ROOT / "data" / "youtube-discovery-v2"
DISHES = REPO_ROOT / "server" / "app" / "dishes" / "dishes.json"
FAILURE_TYPES = (
    "neighbouring dish",
    "other dish",
    "vlog or eating show",
    "short",
    "compilation or advertisement",
    "other",
)


def norm(text: str) -> str:
    return text.replace(" ", "").strip().lower()


def title_rule(title: str, dish_name: str) -> bool:
    """J0: the normalised title contains the normalised dish name."""
    return norm(dish_name) in norm(title)


def kappa(a: list[bool], b: list[bool]) -> float | None:
    n = len(a)
    if n == 0:
        return None
    pa, pb = sum(a) / n, sum(b) / n
    if pa * pb + (1 - pa) * (1 - pb) == 1:  # chance agreement is total: kappa is undefined
        return None
    return float(cohen_kappa_score(a, b))


def per_dish(
    candidates: dict, judgements: dict, names: dict[str, str], method: str, judge: str
) -> list[dict]:
    rows = []
    for dish, judged in judgements.items():
        if judged.get("E", {}).get("error") or judged.get("J1", {}).get("error"):
            continue
        if not judged.get("E", {}).get("judgements") and not judged.get("J1", {}).get("judgements"):
            continue
        entry = candidates[dish]
        videos = entry["videos"]
        provided = list(dict.fromkeys(entry["methods"][method]))
        usable = [i for i in provided if i in videos and videos[i]["usable"]]
        label = judged[judge]["judgements"]
        other = judged["J1" if judge == "E" else "E"]["judgements"]
        rows.append(
            {
                "dish": dish,
                "provided": len(provided),
                "exist": sum(i in videos for i in provided),
                "usable": usable,
                "relevant": [i for i in usable if label.get(i)],
                "other_judge": [i for i in usable if other.get(i)],
                "j0": [i for i in usable if title_rule(videos[i]["title"], names[dish])],
                "first_ok": bool(usable) and bool(label.get(usable[0])),
                "has_usable": bool(usable),
            }
        )
    return rows


def summarise(rows: list[dict]) -> dict:
    usable = sum(len(r["usable"]) for r in rows)
    relevant = sum(len(r["relevant"]) for r in rows)
    j0 = sum(len(r["j0"]) for r in rows)
    with_usable = [r for r in rows if r["usable"]]
    counts = Counter(min(len(r["relevant"]), 3) for r in rows)
    return {
        "dishes": len(rows),
        "links_provided": sum(r["provided"] for r in rows),
        "links_existing": sum(r["exist"] for r in rows),
        "links_usable": usable,
        "links_relevant": relevant,
        "per_dish_mean_provided": statistics.fmean(r["provided"] for r in rows),
        "per_dish_mean_usable": statistics.fmean(len(r["usable"]) for r in rows),
        "per_dish_mean_relevant": statistics.fmean(len(r["relevant"]) for r in rows),
        "relevant_share_pooled": relevant / usable if usable else None,
        "relevant_share_mean_over_dishes": statistics.fmean(
            len(r["relevant"]) / len(r["usable"]) for r in with_usable
        )
        if with_usable
        else None,
        "dishes_with_0_1_2_3plus_relevant": [counts.get(k, 0) for k in range(4)],
        "dishes_with_at_least_one_relevant": sum(bool(r["relevant"]) for r in rows),
        "first_usable_link_relevant_share": statistics.fmean(r["first_ok"] for r in rows),
        "j0_accepted": j0,
        "j0_share_of_usable": j0 / usable if usable else None,
        "j0_accepted_but_judge_rejects": sum(len(set(r["j0"]) - set(r["relevant"])) for r in rows),
        "judge_accepts_but_j0_rejects": sum(len(set(r["relevant"]) - set(r["j0"])) for r in rows),
        "dishes_with_at_least_one_j0": sum(bool(r["j0"]) for r in rows),
    }


def agreement(rows: list[dict], candidates: dict, judgements: dict) -> dict:
    a: list[bool] = []
    b: list[bool] = []
    for r in rows:
        for i in r["usable"]:
            a.append(bool(judgements[r["dish"]]["E"]["judgements"].get(i)))
            b.append(bool(judgements[r["dish"]]["J1"]["judgements"].get(i)))
    return {
        "links": len(a),
        "same_label_share": sum(x == y for x, y in zip(a, b, strict=True)) / len(a),
        "kappa": kappa(a, b),
        "relevant_by_E": sum(a),
        "relevant_by_J1": sum(b),
    }


def rejected_links(rows: list[dict], candidates: dict) -> list[dict]:
    out = []
    for r in rows:
        for i in r["usable"]:
            if i in r["relevant"]:
                continue
            v = candidates[r["dish"]]["videos"][i]
            out.append(
                {
                    "dish": r["dish"],
                    "id": i,
                    "title": v["title"],
                    "channel": v["channel"],
                    "duration_s": v.get("duration_s"),
                    "j1_relevant": i in r["other_judge"],
                }
            )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--method", default="B", choices=("B", "B2"))
    parser.add_argument("--list-rejected", action="store_true")
    parser.add_argument("--failure-labels", type=Path, default=HERE / "failure_types_round2.json")
    args = parser.parse_args(argv)
    candidates = json.loads((DATA / "candidates.json").read_text(encoding="utf-8"))
    judgements = json.loads((DATA / "judgements.json").read_text(encoding="utf-8"))
    names = {d["id"]: d["name"] for d in json.loads(DISHES.read_text(encoding="utf-8"))["dishes"]}
    out: dict = {}
    for judge in ("E", "J1"):
        rows = per_dish(candidates, judgements, names, args.method, judge)
        out[judge] = summarise(rows)
        if judge == "E":
            out["agreement"] = agreement(rows, candidates, judgements)
            rejected = rejected_links(rows, candidates)
            if args.list_rejected:
                for r in rejected:
                    print(json.dumps(r, ensure_ascii=False))
                return 0
            if args.failure_labels.exists():
                labels = json.loads(args.failure_labels.read_text(encoding="utf-8"))
                kinds = Counter(
                    labels.get(f"{r['dish']}:{r['id']}", "unlabelled") for r in rejected
                )
                out["failure_types_of_E_rejected_usable_links"] = dict(kinds)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
