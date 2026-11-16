# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Runner of round 3 (criteria_round3.json). Every command is a dry run unless --allow-live-api.

  plan      print the plan, no network
  collect   discovery call per dish and variant, one videos.list per dish
  judge     judge the usable links no judgement exists for yet (one call per judge and dish)
  analyze   metrics, paired differences and the frozen rule (offline, reads stored files)
Keys come from ~/.config/mylittlechef/ and are never printed. Raw data stay under data/ (ignored);
the earlier study's candidates.json and judgements.json are read from data/youtube-discovery-v2/.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import httpx

from app.dishes.youtube import YouTubeClient

from . import round3 as r3

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CFG = Path.home() / ".config" / "mylittlechef"
OLD = REPO / "data" / "youtube-discovery-v2"
DATA = REPO / "data" / "dish-pipeline-round3"
OR_URL = "https://openrouter.ai/api/v1/chat/completions"
WEB_MODEL = "google/gemini-2.5-flash-lite:online"
JUDGES = {"E": "google/gemini-2.5-pro", "J1": "anthropic/claude-haiku-4.5"}
SEED = 20261116
JUDGE_PROMPT = """You judge YouTube videos for a cooking app. For each item decide whether the
video is a recipe video whose main content is cooking the given dish.
relevant = the main content is cooking this dish (any language, any popular variant of it).
irrelevant = a different dish, a vlog, a mukbang (eating show), a product advertisement,
a compilation, or a video where the dish is only a side mention.
Judge only from the fields given. Answer with strict JSON only:
{{"judgements":[{{"i":"<key>","relevant":true|false,"reason":"<=12 words"}}]}}
with exactly one entry per item, in any order.

Items:
{items}
"""


def key(file: str, name: str) -> str:
    for line in (CFG / file).read_text(encoding="utf-8").splitlines():
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip()
    raise SystemExit(f"missing {name}")


def criteria() -> dict:
    return json.loads((HERE / "criteria_round3.json").read_text(encoding="utf-8"))


def catalog() -> list[dict]:
    raw = json.loads((REPO / "server" / "app" / "dishes" / "dishes.json").read_text("utf-8"))
    return raw["dishes"]


def load(path: Path, default):
    return json.loads(path.read_text("utf-8")) if path.exists() else default


def save(name: str, obj) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def chat(orkey: str, model: str, prompt: str, *, json_mode: bool = False) -> dict:
    """One OpenRouter call; at most two retries after HTTP 429 (waits 8 s and 20 s), all counted."""
    body: dict = {
        "model": model,
        "temperature": 0,
        "messages": [{"role": "user", "content": prompt}],
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    out = {"calls": 0, "cost": 0.0, "latency_s": 0.0}
    for wait in (8, 20, None):
        t0 = time.monotonic()
        with httpx.Client(timeout=180) as c:
            r = c.post(OR_URL, json=body, headers={"Authorization": f"Bearer {orkey}"})
        out["calls"] += 1
        out["latency_s"] += time.monotonic() - t0
        if r.status_code == 429 and wait:
            time.sleep(wait)
            continue
        if r.status_code != 200:
            return {**out, "error": f"HTTP {r.status_code}"}
        data = r.json()
        msg = data["choices"][0]["message"]
        out["cost"] += float((data.get("usage") or {}).get("cost") or 0.0)
        out["text"] = msg.get("content") or ""
        out["citations"] = [
            a.get("url_citation", {}).get("url", "") for a in (msg.get("annotations") or [])
        ]
        return out
    return {**out, "error": "HTTP 429"}


def item_text(k: str, dish: dict, c: dict) -> str:
    names = ", ".join([dish["name"], *dish.get("aliases", [])])
    return (
        f"[{k}] dish: {names} | title: {c['title']} | channel: {c['channel']} | "
        f"duration_s: {c['duration_s']} | description: {c['description']!r} | tags: {c['tags']}"
    )


def spend() -> float:
    total = 0.0
    for row in load(DATA / "collected.json", {}).values():
        total += sum((v or {}).get("cost") or 0 for v in row["calls"].values())
    for per in load(DATA / "judgements.json", {}).values():
        total += sum((v or {}).get("cost") or 0 for v in per.values())
    return total


def discovery_calls() -> int:
    return sum(
        (v or {}).get("calls") or 0
        for row in load(DATA / "collected.json", {}).values()
        for v in row["calls"].values()
    )


def cmd_collect(args, crit) -> None:
    table = {d["id"]: d for d in catalog()}
    orkey = key("openrouter.env", "OPENROUTER_API_KEY")
    yt = YouTubeClient(key("youtube.env", "YOUTUBE_API_KEY"))
    store = load(DATA / "collected.json", {})
    cap = crit["budget"]["discovery_calls"]
    for did in crit["dishes"]["list"]:
        row = store.get(did, {"ids": {}, "calls": {}, "videos": {}})
        for v in r3.VARIANTS:
            failed = bool((row["calls"].get(v) or {}).get("error"))
            if v in row["calls"] and not (args.repeat_failed and failed):
                continue  # a failed call is repeated only after an amendment (--repeat-failed)
            if v in row["calls"]:
                row.setdefault("failed_attempts", {})[v] = row["calls"][v]
            if discovery_calls() >= cap:
                print("discovery call cap reached")
                save("collected.json", store)
                return
            res = chat(orkey, WEB_MODEL, r3.request_text(v, table[did]["name"]))
            row["calls"][v] = {k: res.get(k) for k in ("calls", "cost", "latency_s", "error")}
            row["ids"][v] = (
                r3.extract_ids(res.get("text", ""), res.get("citations", []))
                if "error" not in res
                else []
            )
            row.setdefault("text", {})[v] = (res.get("text") or "")[:1500]
            store[did] = row
            save("collected.json", store)
        union = list(dict.fromkeys(i for v in r3.VARIANTS for i in row["ids"].get(v, [])))
        missing = [i for i in union if i not in row["videos"]]
        if missing:
            data = yt._get(  # noqa: SLF001 - the app client's details() lacks contentDetails
                "videos",
                {"part": "snippet,contentDetails,statistics,status", "id": ",".join(union[:50])},
            )
            found = {i["id"]: r3.to_candidate(i) for i in data.get("items", [])}
            row["videos"] = {**row["videos"], **found, **{i: None for i in union if i not in found}}
        store[did] = row
        save("collected.json", store)
    print(
        f"discovery calls {discovery_calls()}, spend {spend():.3f} USD, videos.list {yt.requests}"
    )


def old_judgement(old: dict, did: str, vid: str, judge: str):
    tag = "E" if judge == "E" else "J1"
    got = ((old.get(did) or {}).get(tag) or {}).get("judgements") or {}
    return got.get(vid)


def cmd_judge(args, crit) -> None:
    table = {d["id"]: d for d in catalog()}
    orkey = key("openrouter.env", "OPENROUTER_API_KEY")
    store = load(DATA / "collected.json", {})
    old = load(OLD / "judgements.json", {})
    done = load(DATA / "judgements.json", {})
    stop = crit["budget"]["judge_stop_usd"]
    for did in crit["dishes"]["list"]:
        row = store.get(did)
        if not row:
            continue
        usable = {
            vid: c
            for vid, c in row["videos"].items()
            if c and c["usable"] and any(vid in row["ids"].get(v, []) for v in r3.VARIANTS)
        }
        for judge, model in JUDGES.items():
            new = [vid for vid in usable if old_judgement(old, did, vid, judge) is None]
            if not new or (done.get(did, {}).get(judge) and not done[did][judge].get("error")):
                continue
            if spend() >= stop:
                print(f"stopped before {did}: spend {spend():.2f} USD")
                return
            order = r3.shuffled(new, SEED)
            prompt = JUDGE_PROMPT.format(
                items="\n".join(item_text(k, table[did], usable[k]) for k in order)
            )
            res = chat(orkey, model, prompt, json_mode=True)
            parsed = r3.parse_judgements(res.get("text", ""), order) if "error" not in res else None
            if parsed is None and "error" not in res:  # one retry for an unusable answer
                again = chat(orkey, model, prompt, json_mode=True)
                again["calls"] += res["calls"]
                again["cost"] += res["cost"]
                res = again
                parsed = (
                    r3.parse_judgements(res.get("text", ""), order) if "error" not in res else None
                )
            reasons = {}
            if parsed is not None:
                m = re.search(r"\{.*\}", res.get("text", ""), re.S)
                reasons = {
                    str(x["i"]): x.get("reason", "") for x in json.loads(m.group(0))["judgements"]
                }
            done.setdefault(did, {})[judge] = {
                "judgements": parsed,
                "reasons": reasons,
                "calls": res["calls"],
                "cost": res["cost"],
                "latency_s": res["latency_s"],
                "error": res.get("error") or (None if parsed else "unparsable"),
            }
            save("judgements.json", done)
    print(f"judged {len(done)} dishes, spend {spend():.3f} USD")


def link_rows(crit: dict) -> tuple[dict[str, list[dict]], list[str]]:
    """Rows per variant (OLD, D0..D3) for the dishes judged by both judges."""
    store = load(DATA / "collected.json", {})
    old_cand = load(OLD / "candidates.json", {})
    old_j = load(OLD / "judgements.json", {})
    new_j = load(DATA / "judgements.json", {})

    def rel(did: str, vid: str, judge: str):
        got = old_judgement(old_j, did, vid, judge)
        if got is None:
            got = (((new_j.get(did) or {}).get(judge) or {}).get("judgements") or {}).get(vid)
        return got

    dishes = []
    for did in crit["dishes"]["list"]:
        row = store.get(did)
        if not row or any(v not in row["calls"] for v in r3.VARIANTS):
            continue
        links = {
            vid
            for v in r3.VARIANTS
            for vid in row["ids"].get(v, [])
            if row["videos"].get(vid) and row["videos"][vid]["usable"]
        }
        if all(rel(did, vid, j) is not None for vid in links for j in JUDGES):
            dishes.append(did)
    rows: dict[str, list[dict]] = {v: [] for v in ("OLD", *r3.VARIANTS)}
    for did in dishes:
        row = store[did]
        for v in r3.VARIANTS:
            ids = row["ids"].get(v, [])
            usable = [
                row["videos"][i] for i in ids if row["videos"].get(i) and row["videos"][i]["usable"]
            ]
            rows[v].append(
                {
                    "dish": did,
                    "provided": len(ids),
                    "exist": sum(1 for i in ids if row["videos"].get(i)),
                    "links": [
                        {**c, "rel": {j: rel(did, c["video_id"], j) for j in JUDGES}}
                        for c in usable
                    ],
                    "cost": (row["calls"][v] or {}).get("cost") or 0.0,
                    "latency_s": (row["calls"][v] or {}).get("latency_s") or 0.0,
                    "error": bool((row["calls"][v] or {}).get("error")),
                }
            )
        o = old_cand[did]
        ids = o["methods"]["B"] or []
        usable = [o["videos"][i] for i in ids if o["videos"].get(i) and o["videos"][i]["usable"]]
        cost = o["cost"].get("B") or {}
        rows["OLD"].append(
            {
                "dish": did,
                "provided": len(ids),
                "exist": sum(1 for i in ids if o["videos"].get(i)),
                "links": [
                    {**c, "rel": {j: rel(did, c["video_id"], j) for j in JUDGES}} for c in usable
                ],
                "cost": cost.get("cost") or 0.0,
                "latency_s": (cost.get("latency_s") or 0.0),
                "error": False,
            }
        )
    return rows, dishes


def cmd_analyze(args, crit) -> None:
    rows, dishes = link_rows(crit)
    cat = catalog()
    table = {d["id"]: d for d in cat}
    out: dict = {"dishes": len(dishes), "dish_ids": dishes, "variants": {}}
    for v, rs in rows.items():
        m = {j: r3.variant_metrics(rs, j) for j in JUDGES}
        ftype: dict[str, int] = {}
        for r in rs:
            for lk in r["links"]:
                if not lk["rel"]["E"]:
                    t = r3.failure_type(lk, table[r["dish"]], cat)
                    ftype[t] = ftype.get(t, 0) + 1
        out["variants"][v] = {"E": m["E"], "J1": m["J1"], "failure_types_E": ftype}
    pairs = [
        (a["rel"]["E"], a["rel"]["J1"]) for rs in rows.values() for r in rs for a in r["links"]
    ]
    out["agreement_E_J1"] = {
        "links": len(pairs),
        "agree": sum(x == y for x, y in pairs) / len(pairs) if pairs else None,
        "kappa": r3.cohen_kappa([x for x, _ in pairs], [y for _, y in pairs]),
    }
    diffs = {}
    for judge in JUDGES:
        for v in r3.VARIANTS[1:]:
            diffs[f"{v}|{judge}"] = r3.pooled_diff(rows[v], rows["D0"], judge, SEED)
    out["paired_vs_D0"] = diffs
    out["paired_old_vs_D0_E"] = r3.pooled_diff(rows["OLD"], rows["D0"], "E", SEED)
    metrics_e = {v: out["variants"][v]["E"] for v in r3.VARIANTS}
    out["decision"] = r3.decide(metrics_e, {v: diffs[f"{v}|E"] for v in r3.VARIANTS[1:]})
    out["decision_J1_sensitivity"] = r3.decide(
        {v: out["variants"][v]["J1"] for v in r3.VARIANTS},
        {v: diffs[f"{v}|J1"] for v in r3.VARIANTS[1:]},
    )
    out["spend_usd"] = spend()
    save("analysis.json", out)
    print(json.dumps(out, ensure_ascii=False, indent=1))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["plan", "collect", "judge", "analyze"])
    ap.add_argument("--allow-live-api", action="store_true")
    ap.add_argument("--repeat-failed", action="store_true")
    args = ap.parse_args(argv)
    crit = criteria()
    if args.command == "plan" or (args.command in ("collect", "judge") and not args.allow_live_api):
        n = len(crit["dishes"]["list"])
        print(
            json.dumps(
                {
                    "dishes": n,
                    "discovery_calls": n * len(r3.VARIANTS),
                    "videos_list_requests": n,
                    "judge_calls_at_most": 2 * n,
                    "note": "dry run: nothing was called (use --allow-live-api)",
                }
            )
        )
        return 0
    {"collect": cmd_collect, "judge": cmd_judge, "analyze": cmd_analyze}[args.command](args, crit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
