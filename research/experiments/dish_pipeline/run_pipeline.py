# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Run the frozen pipeline variants (criteria.json) on 12 inputs. Dry run by default.

``--allow-live-api`` calls OpenRouter models and YouTube ``videos.list`` (never ``search.list``).
Results go to the ignored ``data/dish-pipeline/`` directory.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path

from experiments.dish_tokens.calls import Call, chat, json_schema_format, read_key
from experiments.dish_tokens.run_tokens import MODEL, payload_for

from app.dishes.answers import check_suggest
from app.dishes.catalog import Catalog
from app.dishes.service import DishService

from . import discovery as d

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
YOUTUBE_KEY_FILE = Path.home() / ".config" / "mylittlechef" / "youtube.env"
VARIANTS = {  # name -> (links per dish, with titles)
    "ids3": (3, False),
    "ids5": (5, False),
    "idsTitles3": (3, True),
}
CEILING = 8192


def youtube_key() -> str:
    for line in YOUTUBE_KEY_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("YOUTUBE_API_KEY="):
            return line.split("=", 1)[1].strip().strip("\"'")
    return ""


def web_payload(system: str, user: str) -> dict:
    return {
        "model": d.WEB_MODEL,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_tokens": CEILING,
        "temperature": 0,
    }


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))]


def call_row(call: Call) -> dict:
    row = dict(call.__dict__)
    row.pop("data", None)
    return row


def judge(items: list[dict], key: str) -> tuple[dict[str, bool], Call | None]:
    """(video id + dish -> relevant, the judge call); unvalidated."""
    if not items:
        return {}, None
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": d.JUDGE_SYSTEM},
            {"role": "user", "content": d.judge_user(items)},
        ],
        "response_format": json_schema_format("judge", d.JUDGE_SCHEMA),
        "provider": {"require_parameters": True},
        "max_tokens": CEILING,
        "temperature": 0,
    }
    call = chat(payload, key)
    verdicts: dict[str, bool] = {}
    for item in (call.data or {}).get("judgements", []):
        if isinstance(item, dict) and isinstance(item.get("video_id"), str):
            verdicts[item["video_id"]] = bool(item.get("relevant"))
    return verdicts, call


def judge_items(kept: dict[str, list[str]], info: dict[str, dict]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    items = []
    for dish, ids in kept.items():
        for vid in ids:
            if (dish, vid) in seen:
                continue
            seen.add((dish, vid))
            items.append({"video_id": vid, "dish": dish, **info[vid]})
    return items


def summarize_check(check: dict, expected_dishes: list[str]) -> dict:
    kept = check["kept"]
    dishes = len(expected_dishes)
    with_link = sum(1 for n in expected_dishes if kept.get(n))
    return {
        "dishes": dishes,
        "dishes_with_link": with_link,
        "links_kept": sum(len(kept.get(n, [])) for n in expected_dishes),
        "returned_ids": check["returned_ids"],
        "existing_ids": check["existing_ids"],
    }


def aggregate(rows: list[dict]) -> dict:
    tot = lambda k: sum(r.get(k, 0) for r in rows)  # noqa: E731
    dishes = tot("dishes")
    returned = tot("returned_ids")
    return {
        "requests": len(rows),
        "dishes": dishes,
        "dishes_with_link_share": tot("dishes_with_link") / dishes if dishes else None,
        "links_per_dish": tot("links_kept") / dishes if dishes else None,
        "id_existence_rate": tot("existing_ids") / returned if returned else None,
        "failure_rate": sum(1 for r in rows if r.get("failed")) / len(rows) if rows else None,
        "judged_relevance_share": (
            sum(r.get("judged_relevant", 0) for r in rows) / tot("judged")
            if tot("judged")
            else None
        ),
        "mean_input_tokens": statistics.fmean(r["input_tokens"] for r in rows),
        "mean_output_tokens": statistics.fmean(r["output_tokens"] for r in rows),
        "mean_reasoning_tokens": statistics.fmean(r["reasoning_tokens"] for r in rows),
        "mean_cost_usd": statistics.fmean(r["cost_usd"] for r in rows),
        "cards_latency_p50": percentile([r["cards_latency_s"] for r in rows], 0.5),
        "cards_latency_p95": percentile([r["cards_latency_s"] for r in rows], 0.95),
        "videos_latency_p50": percentile([r["videos_latency_s"] for r in rows], 0.5),
        "videos_latency_p95": percentile([r["videos_latency_s"] for r in rows], 0.95),
    }


def choose(variants: dict[str, dict]) -> str | None:
    """The pre-registered rule over P1-P3 (P4 is reported, not ranked)."""
    ok = {
        n: v
        for n, v in variants.items()
        if n.split("-")[0] in ("P1", "P2", "P3")
        and (v["dishes_with_link_share"] or 0) >= 0.9
        and (v["cards_latency_p50"] or 99) <= 6.0
    }
    return min(ok, key=lambda n: ok[n]["mean_cost_usd"]) if ok else None


def run_request(case_id, sel, extra, dishes, links_by_dish, fetch, key, expected):
    """Rule check + judge for one request; returns the result row."""
    check = d.apply_rule_check(links_by_dish, fetch)
    verdicts, judge_call = judge(judge_items(check["kept"], check["info"]), key)
    return check, verdicts, judge_call


def summarize(case_id, calls, check, expected, verdicts, cards, videos):
    s = (
        summarize_check(check, expected)
        if check
        else dict.fromkeys(
            ("dishes", "dishes_with_link", "links_kept", "returned_ids", "existing_ids"), 0
        )
    )
    return {
        "id": case_id,
        **s,
        "failed": any(not c.ok for c in calls),
        "judged": len(verdicts),
        "judged_relevant": sum(1 for v in verdicts.values() if v),
        "input_tokens": sum(c.prompt_tokens for c in calls),
        "output_tokens": sum(c.completion_tokens for c in calls),
        "reasoning_tokens": sum(c.reasoning_tokens for c in calls),
        "cost_usd": sum(c.cost_usd for c in calls),
        "cards_latency_s": cards,
        "videos_latency_s": videos,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-live-api", action="store_true")
    parser.add_argument("--selection", default="B", help="selection variant of the token study")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "data" / "dish-pipeline")
    args = parser.parse_args(argv)
    criteria = json.loads((HERE / "criteria.json").read_text(encoding="utf-8"))
    naive = json.loads((HERE.parent / "dish_naive" / "criteria.json").read_text(encoding="utf-8"))
    by_id = {c["id"]: c["ingredients"] for c in naive["cases"]}
    inputs = {i: by_id[i] for i in criteria["inputs"]["input_ids"]}
    cap = criteria["max_additional_model_calls"]
    print(f"{len(inputs)} inputs, about 171 model calls planned (cap {cap})")
    if not args.allow_live_api:
        print("dry run: no model call (use --allow-live-api)")
        return 0
    key, yt = read_key(), youtube_key()
    if not key or not yt:
        print("missing OpenRouter or YouTube key", file=sys.stderr)
        return 2
    fetch = d.youtube_fetcher(yt)
    catalog = Catalog.load()
    service = DishService(catalog)
    names = [d.name for d in service.catalog.all()]
    rng = random.Random(criteria["inputs"]["seed"])
    n_calls = 0
    rows: dict[str, list[dict]] = {}

    selections = {}
    for case_id, ingredients in inputs.items():
        call = chat(payload_for(args.selection, ingredients, names), key)
        n_calls += 1
        dishes = (
            [x.name for x in check_suggest(call.data, service.catalog, service.recipes)]
            if call.data
            else []
        )
        selections[case_id] = (call, dishes)

    # P2: one batched discovery call for all selected dishes
    for vname, (links, titles) in VARIANTS.items():
        out = []
        for case_id in inputs:
            sel, dishes = selections[case_id]
            calls, check, verdicts = [sel], None, {}
            videos_latency = sel.latency_s
            if dishes:
                call = chat(
                    web_payload(d.DISCOVERY_SYSTEM, d.discovery_user(dishes, links, titles)), key
                )
                n_calls += 1
                calls.append(call)
                videos_latency += call.latency_s
                parsed = d.parse_dishes(call.data)
                by_dish = {n: parsed.get(n, {}).get("ids", []) for n in dishes}
                check, verdicts, jc = run_request(
                    case_id, sel, [call], dishes, by_dish, fetch, key, dishes
                )
                if jc:
                    n_calls += 1
                    calls.append(jc)
            out.append(
                summarize(case_id, calls, check, dishes, verdicts, sel.latency_s, videos_latency)
            )
        rows[f"P2-{vname}"] = out

    # P3: selection and links in one web-model call
    for vname in ("ids3", "idsTitles3"):
        links, titles = VARIANTS[vname]
        out = []
        for case_id, ingredients in inputs.items():
            call = chat(
                web_payload(
                    d.SELECT_AND_LINK_SYSTEM,
                    d.select_and_link_user(ingredients, names, links, titles),
                ),
                key,
            )
            n_calls += 1
            parsed = d.parse_dishes(call.data)
            dishes = [n for n in parsed if service.catalog.by_name(n) is not None]
            calls, check, verdicts = [call], None, {}
            if dishes:
                check, verdicts, jc = run_request(
                    case_id,
                    call,
                    [],
                    dishes,
                    {n: parsed[n]["ids"] for n in dishes},
                    fetch,
                    key,
                    dishes,
                )
                if jc:
                    n_calls += 1
                    calls.append(jc)
            out.append(
                summarize(case_id, calls, check, dishes, verdicts, call.latency_s, call.latency_s)
            )
        rows[f"P3-{vname}"] = out

    # P1/P4: one seeded dish per input, one discovery call per dish (unit measurements)
    sample = {}
    for case_id, (_sel, dishes) in selections.items():
        if dishes:
            sample[case_id] = rng.choice(dishes)
    units: dict[str, list[dict]] = {}
    for vname, (links, titles) in VARIANTS.items():
        unit_calls, by_dish, lat = [], {}, []
        for case_id, dish in sample.items():
            call = chat(
                web_payload(d.DISCOVERY_SYSTEM, d.discovery_user([dish], links, titles)), key
            )
            n_calls += 1
            parsed = d.parse_dishes(call.data)
            by_dish[f"{case_id}:{dish}"] = parsed.get(dish, {}).get("ids", [])
            unit_calls.append(call)
            lat.append(call.latency_s)
        check = d.apply_rule_check(by_dish, fetch)
        verdicts, jc = judge(judge_items(check["kept"], check["info"]), key)
        n_calls += 1 if jc else 0
        s = summarize_check(check, list(by_dish))
        units[vname] = {
            "calls": len(unit_calls),
            **s,
            "failed": sum(1 for c in unit_calls if not c.ok),
            "judged": len(verdicts),
            "judged_relevant": sum(1 for v in verdicts.values() if v),
            "mean_cost_usd": statistics.fmean(c.cost_usd for c in unit_calls),
            "mean_input_tokens": statistics.fmean(c.prompt_tokens for c in unit_calls),
            "mean_output_tokens": statistics.fmean(c.completion_tokens for c in unit_calls),
            "latency_p95_s": percentile(lat, 0.95),
        }
    for vname, u in units.items():  # model P1 (eager) and P4 (lazy) requests from the units
        p1, p4_1, p4_3 = [], [], []
        for case_id in inputs:
            sel, dishes = selections[case_id]
            base = {
                "input_tokens": sel.prompt_tokens,
                "output_tokens": sel.completion_tokens,
                "reasoning_tokens": sel.reasoning_tokens,
            }
            common = {
                "id": case_id,
                "dishes": u["dishes"] // max(1, len(sample)),
                "dishes_with_link": u["dishes_with_link"] // max(1, len(sample)),
                "links_kept": 0,
                "returned_ids": 0,
                "existing_ids": 0,
                "failed": not sel.ok or bool(u["failed"]),
                "judged": 0,
                "judged_relevant": 0,
                "cards_latency_s": sel.latency_s,
            }
            n = len(dishes)
            p1.append(
                {
                    **base,
                    **common,
                    "cost_usd": sel.cost_usd + n * u["mean_cost_usd"],
                    "videos_latency_s": sel.latency_s + (u["latency_p95_s"] or 0),
                }
            )
            p4_1.append(
                {
                    **base,
                    **common,
                    "cost_usd": sel.cost_usd + u["mean_cost_usd"],
                    "videos_latency_s": sel.latency_s + (u["latency_p95_s"] or 0),
                }
            )
            p4_3.append(
                {
                    **base,
                    **common,
                    "cost_usd": sel.cost_usd + 3 * u["mean_cost_usd"],
                    "videos_latency_s": sel.latency_s + (u["latency_p95_s"] or 0),
                }
            )
        rows[f"P1-{vname}"] = p1
        rows[f"P4-{vname}-open1"] = p4_1
        rows[f"P4-{vname}-open3"] = p4_3

    variants = {}
    for name, rs in rows.items():
        variants[name] = aggregate(rs)
        if name.startswith(
            ("P1", "P4")
        ):  # per-dish shares come from the units, not the placeholders
            v = units[name.split("-")[1]]
            variants[name].update(
                dishes=v["dishes"],
                dishes_with_link_share=v["dishes_with_link"] / v["dishes"] if v["dishes"] else None,
                links_per_dish=v["links_kept"] / v["dishes"] if v["dishes"] else None,
                id_existence_rate=v["existing_ids"] / v["returned_ids"]
                if v["returned_ids"]
                else None,
                judged_relevance_share=v["judged_relevant"] / v["judged"] if v["judged"] else None,
                failure_rate=v["failed"] / v["calls"],
                modelled=True,
            )
    winner = choose(variants)
    summary = {
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "selection_variant": args.selection,
        "winner": winner,
        "model_calls": n_calls,
        "variants": variants,
        "units": units,
        "rows": rows,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"summary-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("winner", winner, "model calls", n_calls)
    for name, v in variants.items():
        print(
            name,
            {
                k: (round(x, 4) if isinstance(x, float) else x)
                for k, x in v.items()
                if k
                in (
                    "mean_cost_usd",
                    "dishes_with_link_share",
                    "cards_latency_p50",
                    "videos_latency_p50",
                    "id_existence_rate",
                    "judged_relevance_share",
                    "failure_rate",
                )
            },
        )
    print("wrote", path.relative_to(REPO_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
