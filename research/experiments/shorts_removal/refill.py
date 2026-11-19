# AI-generated with Claude Code (Opus 5.5), 2026-11-19; not yet reviewed.
"""Shorts removal: landscape-only stored links, refill of emptied and single-link dishes.

Run from pr-work/ytdemo/server with PYTHONPATH=.:../research. Data stay in W (outside git).
Stages: plan | collect --live | judge --live | queue | merge
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import httpx

from app.dishes.video_search import OPENROUTER, WEB_MODEL, extract_ids, video_request
from experiments.dish_recipes.common import load_json, now_iso, read_key
from experiments.dish_recipes.orientation import orientation
from experiments.dish_recipes.search_videos import SEARCH_URL, search_params, result_ids
from experiments.dish_recipes.verify_videos import (
    JUDGE_PROMPT, JUDGES, YT_URL, chat, dish_table, item_text, parse_judgements, playable, to_video,
)

ROOT = Path("/home/hyuk/PRJ/MyLittleChef/artifacts/dish-recipes")
LINKS = ROOT / "link-data"
W = ROOT / "shorts-removal"
VERIFIED = LINKS / "dish-videos.verified.json"
ORIENT = ROOT / "orientation.json"
STATE = W / "state.json"
REVIEW = W / "review.json"
KEEP = 5  # same per-dish cap as the earlier search supplement (search_videos.KEEP)


def private(path: Path, value) -> None:
    W.mkdir(exist_ok=True)
    os.chmod(W, 0o700)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=1), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def plan() -> None:
    dishes = load_json(VERIFIED, {})["dishes"]
    ori = load_json(ORIENT, {})["orientation"]
    kept, empty, single = {}, [], []
    for d, e in dishes.items():
        vids = [v for v in e["videos"] if ori.get(v["id"]) != "vertical"]
        kept[d] = [v["id"] for v in vids]
        if not vids:
            empty.append(d)
        elif len(vids) == 1:
            single.append(d)
    state = load_json(STATE, {})
    state.update(
        planned_at=now_iso(),
        landscape=kept,
        targets={"empty": sorted(empty), "single": sorted(single)},
        removed_vertical=sum(
            ori.get(v["id"]) == "vertical" for e in dishes.values() for v in e["videos"]
        ),
        dishes=state.get("dishes", {}),
        units=state.get("units", 0),
        or_calls=state.get("or_calls", 0),
        or_cost=state.get("or_cost", 0.0),
    )
    private(STATE, state)
    print(len(empty), "empty,", len(single), "single,", state["removed_vertical"], "vertical removed")


def seen_ids(dish: str) -> set[str]:
    report = load_json(LINKS / "verification.json", {})
    # Pairs never reached by a reviewer (beyond the earlier per-dish cap) are candidates again.
    return {p["video"] for p in report.values() if p["dish"] == dish and p["basis"] != "not_reached"}


def d0(key: str, name: str) -> tuple[list[str], float, str | None]:
    with httpx.Client(timeout=120) as c:
        r = c.post(OPENROUTER, json=video_request(WEB_MODEL, name),
                   headers={"Authorization": f"Bearer {key}"})
    if r.status_code != 200:
        return [], 0.0, f"HTTP {r.status_code}"
    data = r.json()
    msg = data["choices"][0]["message"]
    cites = [(a.get("url_citation") or {}).get("url", "") for a in msg.get("annotations") or []]
    return extract_ids(msg.get("content") or "", cites), float((data.get("usage") or {}).get("cost") or 0), None


def details(key: str, ids: list[str]) -> dict[str, dict]:
    out = {}
    for n in range(0, len(ids), 50):
        r = httpx.get(YT_URL, params={
            "part": "snippet,contentDetails,statistics,status,player", "maxWidth": 1000,
            "id": ",".join(ids[n:n + 50])}, headers={"X-Goog-Api-Key": key}, timeout=30)
        r.raise_for_status()
        for item in r.json().get("items", []):
            v = to_video(item)
            p = item.get("player", {})
            v["orientation"] = orientation(p.get("embedWidth"), p.get("embedHeight"))
            out[item["id"]] = v
    return out


def collect() -> None:
    yt, orkey = read_key("YOUTUBE_API_KEY", "youtube.env"), read_key("OPENROUTER_API_KEY", "openrouter.env")
    state, table = load_json(STATE, {}), dish_table()
    prior = load_json(LINKS / "search.json", {"dishes": {}})["dishes"]
    for d in state["targets"]["empty"] + state["targets"]["single"]:
        e = state["dishes"].setdefault(d, {})
        if "candidates" in e:
            continue
        name = table[d]["name"]
        if "d0" in e:
            prop = e["d0"]["ids"]
        else:
            prop, cost, err = d0(orkey, name)
            state["or_calls"] += 1
            state["or_cost"] += cost
            e["d0"] = {"at": now_iso(), "ids": prop, "error": err, "cost": cost}
        searches = [s for s in prior.get(d, {}).get("searches", []) if s.get("results")]
        if searches:
            res = searches[0]["results"]
            e["search"] = {"reused": searches[0]["at"], "q": searches[0]["q"], "ids": res}
        else:
            q = f"{name} 레시피"
            r = httpx.get(SEARCH_URL, params=search_params(q), headers={"X-Goog-Api-Key": yt}, timeout=30)
            state["units"] += 100
            if r.status_code != 200:
                e["search"] = {"at": now_iso(), "q": q, "error": f"HTTP {r.status_code}"}
                private(STATE, state)
                print(d, "search HTTP", r.status_code, "- stopping")
                return
            e["search"] = {"at": now_iso(), "q": q, "ids": result_ids(r.json())}
        seen = seen_ids(d) | set(state["landscape"][d])
        order = []
        for vid in prop + e["search"]["ids"]:
            if vid not in seen and vid not in order:
                order.append(vid)
        info = details(yt, order) if order else {}
        state["units"] += (len(order) + 49) // 50
        e["new"] = order
        e["dropped"] = {
            vid: ("gone" if vid not in info else "not_playable" if not playable(info[vid])
                  else info[vid]["orientation"])
            for vid in order
            if vid not in info or not playable(info[vid]) or info[vid]["orientation"] in ("vertical", "unknown")
        }
        e["candidates"] = {vid: info[vid] for vid in order if vid not in e["dropped"]}
        e["order"] = [vid for vid in order if vid in e["candidates"]]
        private(STATE, state)
        print(f"{d}: d0 {len(prop)} search {len(e['search']['ids'])} new {len(order)} "
              f"landscape-playable {len(e['order'])} dropped {len(e['dropped'])}")


def judge() -> None:
    key = read_key("OPENROUTER_API_KEY", "openrouter.env")
    state, table = load_json(STATE, {}), dish_table()
    for d, e in state["dishes"].items():
        e.setdefault("judged", {})
        todo = [v for v in e.get("order", []) if f"{d}|{v}" not in e["judged"]]
        if not todo:
            continue
        keys = [f"{d}|{v}" for v in todo]
        items = "\n".join(item_text(k, table[d], e["candidates"][v]) for k, v in zip(keys, todo))
        for model in JUDGES:
            res = chat(key, model, JUDGE_PROMPT.format(items=items))
            parsed = parse_judgements(res.get("text", ""), keys) if "error" not in res else None
            state["or_cost"] += res["cost"]
            state["or_calls"] += res["calls"]
            for k in keys:
                e["judged"].setdefault(k, {})[model] = (parsed or {}).get(k)
        private(STATE, state)
        print(d, "judged", len(keys))


def parse(text: str, keys: list[str]) -> dict | None:
    """parse_judgements, also accepting answers that give only the video id part of the key."""
    full = parse_judgements(text, keys)
    if full is not None:
        return full
    by_vid = {k.split("|", 1)[1]: k for k in keys}
    try:
        start, end = text.index("{"), text.rindex("}") + 1
        rows = json.loads(text[start:end])["judgements"]
        out = {by_vid.get(str(r["i"]), str(r["i"])): {"relevant": bool(r["relevant"]),
               "reason": str(r.get("reason", ""))} for r in rows}
    except (ValueError, KeyError, TypeError):
        return None
    return out if set(out) == set(keys) else None


def rejudge() -> None:
    """Retry only the missing answers, per model, in batches of six (big batches failed to parse)."""
    key = read_key("OPENROUTER_API_KEY", "openrouter.env")
    state, table = load_json(STATE, {}), dish_table()
    for d, e in state["dishes"].items():
        for model in JUDGES:
            todo = [k for k, j in e.get("judged", {}).items() if j.get(model) is None]
            for n in range(0, len(todo), 6):
                keys = todo[n:n + 6]
                items = "\n".join(item_text(k, table[d], e["candidates"][k.split("|", 1)[1]]) for k in keys)
                res = chat(key, model, JUDGE_PROMPT.format(items=items))
                parsed = parse(res.get("text", ""), keys) if "error" not in res else None
                state["or_cost"] += res["cost"]
                state["or_calls"] += res["calls"]
                for k in keys:
                    e["judged"][k][model] = (parsed or {}).get(k)
                print(d, model, len(keys), "ok" if parsed else res.get("error", "unparsed"))
            private(STATE, state)


def queue() -> None:
    """Every candidate in order until the dish would reach KEEP links (a person reads each)."""
    state, table, review = load_json(STATE, {}), dish_table(), load_json(REVIEW, {})
    for d, e in state["dishes"].items():
        have = len(state["landscape"][d])
        kept = sum(1 for v in e.get("order", []) if review.get(f"{d}|{v}", {}).get("decision") == "relevant")
        for v in e.get("order", []):
            k = f"{d}|{v}"
            if k in review:
                continue
            if have + kept >= KEEP:
                break
            c, j = e["candidates"][v], e["judged"].get(k, {})
            js = "/".join({True: "Y", False: "N", None: "?"}[(j.get(m) or {}).get("relevant")] for m in JUDGES)
            print(f"{k} || {table[d]['name']} || {js} || {c['duration_s']}s || {c['channel']} || {c['title']} || "
                  f"{c['description'][:160]!r}")
            kept += 1  # assume relevant for the look-ahead; rerun after reviewing


def merge() -> None:
    state, review = load_json(STATE, {}), load_json(REVIEW, {})
    verified = load_json(VERIFIED, {})
    out = {}
    stats = {}
    for d, entry in verified["dishes"].items():
        keep_ids = list(state["landscape"][d])
        videos = {v["id"]: v for v in entry["videos"]}
        e = state["dishes"].get(d, {})
        for vid in e.get("order", []):
            if len(keep_ids) >= KEEP:
                break
            if review.get(f"{d}|{vid}", {}).get("decision") == "relevant":
                keep_ids.append(vid)
                c = e["candidates"][vid]
                videos[vid] = {f: c[f] for f in ("id", "title", "channel", "thumbnail", "duration_s", "view_count")}
        added = len(keep_ids) - len(state["landscape"][d])
        out[d] = {"fetched_at": now_iso() if added else entry["fetched_at"],
                  "videos": [videos[i] for i in keep_ids]}
        stats[d] = {"before": len(entry["videos"]), "landscape_kept": len(state["landscape"][d]), "added": added}
    backup = LINKS / "dish-videos.verified.pre-shorts.json"
    if not backup.exists():
        shutil.copy2(VERIFIED, backup)
        os.chmod(backup, 0o600)
    new = {**verified, "dishes": out}
    target = LINKS / "dish-videos.verified.json"
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(new, ensure_ascii=False, indent=1), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(target)
    state["merge"] = {"at": now_iso(), "per_dish": stats}
    private(STATE, state)
    counts = [len(v["videos"]) for v in out.values()]
    print("links", sum(counts), "dist", {n: counts.count(n) for n in sorted(set(counts))})


if __name__ == "__main__":
    stage = sys.argv[1]
    if stage in ("collect", "judge", "rejudge") and "--live" not in sys.argv:
        raise SystemExit("pass --live")
    {"plan": plan, "collect": collect, "judge": judge, "queue": queue, "rejudge": rejudge, "merge": merge}[stage]()
