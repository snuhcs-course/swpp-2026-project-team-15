# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Runner of study v2 (criteria.json). Every command is a dry run unless --allow-live-api is given.

  plan                       print the plan, no network
  collect                    stage 1: A1 (search.list), B and B2 (model), one videos.list per dish
  sample                     draw the 60 validation videos (writes data/.../sample.json, untracked)
  judge-validate             run J1 and E on the 60 labelled videos (needs labels.json)
  judge                      run J1 and E on every dish's candidates
  analyze                    combinations, decision (offline, reads stored files)
Keys are read from ~/.config/mylittlechef/ and never printed. Raw data stay under data/ (ignored).
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import httpx

from app.dishes.youtube import YouTubeClient, YouTubeError

from . import scoring

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CFG = Path.home() / ".config" / "mylittlechef"
DATA = REPO / "data" / "youtube-discovery-v2"
OR_URL = "https://openrouter.ai/api/v1/chat/completions"
DISCOVERY_MODEL = "google/gemini-2.5-flash-lite:online"
SELECTOR_MODEL = "google/gemini-2.5-flash-lite"
EVALUATOR_MODEL = "google/gemini-2.5-flash"
DISCOVERY_PROMPT = (
    "YouTube에서 '{dish} 레시피'를 만드는 가장 인기 있고 평가가 좋은 요리 영상을 "
    "최대 8개 찾아 주세요. 한국어 영상뿐 아니라 어떤 언어의 영상이든 괜찮습니다.{views} "
    "각 영상의 watch?v= 주소와 제목을 JSON 배열로만 답하고, "
    "검색 결과에서 실제로 확인한 주소만 쓰세요."
)
VIEWS_HINT = " 조회수가 가장 높은 영상을 우선하세요."
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
    return json.loads((HERE / "criteria.json").read_text(encoding="utf-8"))


def v1_sample() -> dict:
    p = HERE.parent / "youtube_discovery" / "criteria.json"
    return json.loads(p.read_text(encoding="utf-8"))["sample"]


def dish_table() -> dict[str, dict]:
    raw = json.loads((REPO / "server" / "app" / "dishes" / "dishes.json").read_text("utf-8"))
    return {d["id"]: d for d in raw["dishes"]}


def load(name: str, default):
    p = DATA / name
    return json.loads(p.read_text("utf-8")) if p.exists() else default


def save(name: str, obj) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def chat(orkey: str, model: str, prompt: str, *, json_mode: bool = False) -> dict:
    body: dict = {
        "model": model,
        "temperature": 0,
        "messages": [{"role": "user", "content": prompt}],
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    out = {"calls": 0, "cost": 0.0, "latency_s": 0.0}
    for attempt in range(2):
        t0 = time.monotonic()
        with httpx.Client(timeout=120) as c:
            r = c.post(OR_URL, json=body, headers={"Authorization": f"Bearer {orkey}"})
        out["calls"] += 1
        out["latency_s"] += time.monotonic() - t0
        if r.status_code == 429 and attempt == 0:
            time.sleep(8)
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


def enrich(yt: YouTubeClient, ids: list[str]) -> dict[str, dict]:
    """One videos.list call; the part list adds contentDetails (duration) to the app's default."""
    if not ids:
        return {}
    data = yt._get(  # noqa: SLF001 - the app client's details() does not request contentDetails
        "videos",
        {"part": "snippet,contentDetails,statistics,status", "id": ",".join(ids[:50])},
    )
    return {i["id"]: scoring.to_candidate(i) for i in data.get("items", [])}


def cmd_collect(args, crit) -> None:
    s = v1_sample()
    dishes = s["cached"] + s["extra"]
    paired = s["extra"][:20]
    table = dish_table()
    yt = YouTubeClient(key("youtube.env", "YOUTUBE_API_KEY"))
    orkey = key("openrouter.env", "OPENROUTER_API_KEY")
    store = load("candidates.json", {})
    searches = 0
    search_blocked = False
    for did in dishes:
        name = table[did]["name"]
        row = store.get(did, {"methods": {}, "cost": {}, "videos": {}})
        if (
            "A1" not in row["methods"]
            and did in paired
            and searches < args.max_search
            and not search_blocked
        ):
            try:
                row["methods"]["A1"] = yt.search(f"{name} 레시피")
                searches += 1
            except YouTubeError as err:  # the daily search quota is a separate, small bucket
                search_blocked = True
                print(f"A1 search stopped: {err}")
        for method, hint in (("B", ""), ("B2", VIEWS_HINT)):
            if method in row["methods"]:
                continue
            res = chat(orkey, DISCOVERY_MODEL, DISCOVERY_PROMPT.format(dish=name, views=hint))
            row["cost"][method] = {k: res.get(k) for k in ("calls", "cost", "latency_s", "error")}
            row["methods"][method] = (
                scoring.extract_ids(res.get("text", ""), res.get("citations", []))
                if "error" not in res
                else None
            )
        union = list(dict.fromkeys(i for ids in row["methods"].values() for i in (ids or [])))
        stale = any(c["duration_s"] is None for c in row["videos"].values())
        if union and (set(union) - set(row["videos"]) or stale):
            row["videos"] = {**row["videos"], **enrich(yt, union)}
        store[did] = row
        save("candidates.json", store)
    print(f"search.list calls: {searches}; videos.list requests: {yt.requests - searches}")


def cmd_sample(args, crit) -> None:
    store = load("candidates.json", {})
    table = dish_table()
    pool = []
    for did in sorted(store):
        for c in store[did]["videos"].values():
            if c["usable"]:
                pool.append({**c, "dish": did, "dish_name": table[did]["name"]})
    rng = random.Random(crit["seed"])
    rng.shuffle(pool)

    def named(c):
        return scoring.title_names_dish(c["title"], c["dish_name"])

    strata = [
        ("ko_named", lambda c: c["hangul_title"] and named(c) and not scoring.is_short(c), 20),
        (
            "ko_unnamed",
            lambda c: c["hangul_title"] and not named(c) and not scoring.is_short(c),
            15,
        ),
        ("non_hangul", lambda c: not c["hangul_title"], 15),
        ("short", scoring.is_short, 10),
    ]
    chosen: dict[tuple, dict] = {}
    for tag, pred, n in strata:
        for c in [c for c in pool if pred(c) and (c["dish"], c["video_id"]) not in chosen][:n]:
            chosen[(c["dish"], c["video_id"])] = {**c, "stratum": tag}
    for c in pool:
        if len(chosen) >= 60:
            break
        chosen.setdefault((c["dish"], c["video_id"]), {**c, "stratum": "fill"})
    rows = list(chosen.values())[:60]
    save("sample.json", rows)
    print({t: sum(r["stratum"] == t for r in rows) for t, _, _ in strata}, len(rows))


def item_text(k: str, dish: dict, c: dict) -> str:
    names = ", ".join([dish["name"], *dish.get("aliases", [])])
    return (
        f"[{k}] dish: {names} | title: {c['title']} | channel: {c['channel']} | "
        f"duration_s: {c['duration_s']} | description: {c['description']!r} | tags: {c['tags']}"
    )


def judge_batch(orkey: str, model: str, entries: list[tuple[str, dict, dict]]) -> dict:
    keys = [k for k, _, _ in entries]
    prompt = JUDGE_PROMPT.format(items="\n".join(item_text(k, d, c) for k, d, c in entries))
    res = chat(orkey, model, prompt, json_mode=True)
    parsed = scoring.parse_judgements(res.get("text", ""), keys) if "error" not in res else None
    if parsed is None and "error" not in res:  # one retry for an unusable answer
        again = chat(orkey, model, prompt, json_mode=True)
        again["calls"] += res["calls"]
        again["cost"] += res["cost"]
        res = again
        parsed = scoring.parse_judgements(res.get("text", ""), keys) if "error" not in res else None
    return {
        "judgements": parsed,
        "calls": res["calls"],
        "cost": res["cost"],
        "latency_s": res["latency_s"],
        "error": res.get("error") or (None if parsed else "unparsable"),
    }


def cmd_judge_validate(args, crit) -> None:
    labels = json.loads((HERE / "labels.json").read_text("utf-8"))["labels"]
    sample = load("sample.json", [])
    table = dish_table()
    orkey = key("openrouter.env", "OPENROUTER_API_KEY")
    entries = [(f"{r['dish']}:{r['video_id']}", table[r["dish"]], r) for r in sample]
    assert all(k in labels for k, _, _ in entries), "labels missing for some sample videos"
    out = {}
    for tag, model in (("J1", SELECTOR_MODEL), ("E", EVALUATOR_MODEL)):
        out[tag] = judge_batch(orkey, model, entries)
    save("validation_judgements.json", out)
    print({t: (v["error"], v["calls"]) for t, v in out.items()})


def cmd_judge(args, crit) -> None:
    store = load("candidates.json", {})
    table = dish_table()
    orkey = key("openrouter.env", "OPENROUTER_API_KEY")
    done = load("judgements.json", {})
    for did, row in store.items():
        usable = [c for c in row["videos"].values() if c["usable"]]
        if not usable:
            continue
        entries = [(c["video_id"], table[did], c) for c in usable]
        for tag, model in (("J1", SELECTOR_MODEL), ("E", EVALUATOR_MODEL)):
            if tag in done.get(did, {}) and not done[did][tag]["error"]:
                continue
            done.setdefault(did, {})[tag] = judge_batch(orkey, model, entries)
            save("judgements.json", done)
    print("judged", len(done), "dishes")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "command", choices=["plan", "collect", "sample", "judge-validate", "judge", "analyze"]
    )
    ap.add_argument("--allow-live-api", action="store_true")
    ap.add_argument("--max-search", type=int, default=0)
    args = ap.parse_args(argv)
    crit = criteria()
    s = v1_sample()
    if args.command == "plan" or (
        args.command in ("collect", "judge-validate", "judge") and not args.allow_live_api
    ):
        print(
            json.dumps(
                {
                    "dishes": len(s["cached"]) + len(s["extra"]),
                    "paired": 20,
                    "search_list": 20,
                    "discovery_calls": 80,
                    "judge_calls": 2 + 80,
                    "note": "dry run: nothing was called (use --allow-live-api)",
                }
            )
        )
        return 0
    if args.command == "analyze":
        from . import analyze

        analyze.main(DATA, crit, HERE)
        return 0
    {
        "collect": cmd_collect,
        "sample": cmd_sample,
        "judge-validate": cmd_judge_validate,
        "judge": cmd_judge,
    }[args.command](args, crit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
