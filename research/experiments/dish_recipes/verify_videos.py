# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Verify the stored video links of each dish before they go into the server's stored file.

Stages (outputs are untracked under data/dish-recipes/):

  enrich   one official videos.list call per 50 ids (snippet, contentDetails, status); drops
           videos that no longer exist or are not public and embeddable
  judge    the two judges validated in the second YouTube discovery study (same prompt, same
           settings, one batch per dish): google/gemini-2.5-pro and anthropic/claude-haiku-4.5
  review   writes the pairs a person must read (judges disagree, primary says no, and a seeded
           10% sample of the pairs both judges accept) to review-queue.json
  build    applies the reviewer's decisions (review.json) and writes dish-videos.verified.json
           and verification.json

Relevance is judged from metadata only (title, channel, description, tags, duration), never
from the video itself.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import time

import httpx

from .common import DATA_DIR, REPO_ROOT, VIDEOS_FILE, load_json, now_iso, read_key, save_json

REMOVED_DISHES = frozenset({"egg-salad", "kimchi-porridge"})  # removed by the user on 2026-11-19
JUDGES = ("google/gemini-2.5-pro", "anthropic/claude-haiku-4.5")  # primary, secondary
SAMPLE_SHARE, SAMPLE_SEED = 0.10, 20261119
DESCRIPTION_CHARS = 800
ENRICHED = DATA_DIR / "videos-enriched.json"
JUDGED = DATA_DIR / "videos-judged.json"
QUEUE = DATA_DIR / "review-queue.json"
REVIEW = DATA_DIR / "review.json"
VERIFIED = DATA_DIR / "dish-videos.verified.json"
REPORT = DATA_DIR / "verification.json"
OR_URL = "https://openrouter.ai/api/v1/chat/completions"
YT_URL = "https://www.googleapis.com/youtube/v3/videos"

# Copied verbatim from research/experiments/youtube_discovery_v2/run.py (the validated judge).
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


def iso_seconds(duration: str) -> int | None:
    """ISO 8601 duration of videos.list (PT#H#M#S) in seconds."""
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration or "")
    if not m:
        return None
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return ((d * 24 + h) * 60 + mi) * 60 + s


def to_video(item: dict) -> dict:
    snip, status, details = (
        item.get("snippet", {}),
        item.get("status", {}),
        item.get("contentDetails", {}),
    )
    thumbs = snip.get("thumbnails", {})
    return {
        "id": item["id"],
        "title": snip.get("title", ""),
        "channel": snip.get("channelTitle", ""),
        "description": (snip.get("description") or "")[:DESCRIPTION_CHARS],
        "tags": snip.get("tags", [])[:20],
        "language": snip.get("defaultAudioLanguage") or snip.get("defaultLanguage"),
        "duration_s": iso_seconds(details.get("duration", "")),
        "thumbnail": (thumbs.get("medium") or thumbs.get("default") or {}).get("url"),
        "view_count": int(item.get("statistics", {}).get("viewCount", 0) or 0) or None,
        "public": status.get("privacyStatus") == "public",
        "embeddable": bool(status.get("embeddable")),
        "processed": status.get("uploadStatus") == "processed",
        "made_for_kids": bool(status.get("madeForKids")),
        "region_restriction": details.get("regionRestriction"),
    }


def playable(v: dict | None) -> bool:
    return bool(v and v["public"] and v["embeddable"] and v["processed"])


def item_text(key: str, dish: dict, v: dict) -> str:
    names = ", ".join([dish["name"], *dish.get("aliases", [])])
    return (
        f"[{key}] dish: {names} | title: {v['title']} | channel: {v['channel']} | "
        f"duration_s: {v['duration_s']} | description: {v['description']!r} | tags: {v['tags']}"
    )


def parse_judgements(text: str, keys: list[str]) -> dict[str, dict] | None:
    """{"judgements":[{"i","relevant","reason"}]} with exactly the given keys; None if unusable."""
    try:
        start, end = text.index("{"), text.rindex("}") + 1
        rows = json.loads(text[start:end])["judgements"]
        out = {
            str(r["i"]): {"relevant": bool(r["relevant"]), "reason": str(r.get("reason", ""))}
            for r in rows
        }
    except (ValueError, KeyError, TypeError):
        return None
    return out if set(out) == set(keys) else None


def review_queue(pairs: dict[str, dict], seed: int = SAMPLE_SEED) -> dict[str, str]:
    """Pair key -> why a person reads it: disagreement, primary no, or the agreed-yes sample."""
    queue = {}
    agreed = []
    for k, p in sorted(pairs.items()):
        a, b = (p["judges"].get(m, {}).get("relevant") for m in JUDGES)
        if a is None or b is None or a != b:
            queue[k] = "disagree_or_missing"
        elif a is False:
            queue[k] = "primary_no"
        else:
            agreed.append(k)
    rng = random.Random(seed)
    for k in rng.sample(agreed, max(1, round(len(agreed) * SAMPLE_SHARE))) if agreed else []:
        queue[k] = "agreed_sample"
    return queue


def decide(pair: dict, why: str | None, review: dict | None) -> tuple[bool, str]:
    """Keep or drop one (dish, video) pair; returns (keep, basis)."""
    if review is not None:
        return review["decision"] == "relevant", f"reviewer:{review['decision']}"
    if why is not None:
        return False, "unreviewed"
    return True, "both_judges"


def chat(key: str, model: str, prompt: str) -> dict:
    body = {
        "model": model,
        "temperature": 0,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
    }
    out = {"calls": 0, "cost": 0.0}
    for attempt in range(3):
        with httpx.Client(timeout=180) as c:
            r = c.post(OR_URL, json=body, headers={"Authorization": f"Bearer {key}"})
        out["calls"] += 1
        if r.status_code == 429 and attempt < 2:
            time.sleep((3, 8)[attempt])
            continue
        if r.status_code != 200:
            return {**out, "error": f"HTTP {r.status_code}"}
        data = r.json()
        out["cost"] += float((data.get("usage") or {}).get("cost") or 0.0)
        out["text"] = data["choices"][0]["message"].get("content") or ""
        return out
    return {**out, "error": "HTTP 429"}


def dish_table() -> dict[str, dict]:
    raw = json.loads((REPO_ROOT / "server" / "app" / "dishes" / "dishes.json").read_text("utf-8"))
    return {d["id"]: d for d in raw["dishes"]}


def stored() -> dict[str, list[str]]:
    dishes = load_json(VIDEOS_FILE, {})["dishes"]
    return {d: [v["id"] for v in e["videos"]] for d, e in dishes.items() if d not in REMOVED_DISHES}


def cmd_enrich() -> None:
    key = read_key("YOUTUBE_API_KEY", "youtube.env")
    ids = sorted({i for vs in stored().values() for i in vs})
    found, units = {}, 0
    for n in range(0, len(ids), 50):
        r = httpx.get(
            YT_URL,
            params={
                "part": "snippet,contentDetails,statistics,status",
                "id": ",".join(ids[n : n + 50]),
            },
            headers={"X-Goog-Api-Key": key},
            timeout=30,
        )
        units += 1
        r.raise_for_status()
        found.update({i["id"]: to_video(i) for i in r.json().get("items", [])})
    save_json(
        ENRICHED, {"fetched_at": now_iso(), "videos": found, "requested": ids, "units": units}
    )
    gone = [i for i in ids if i not in found]
    print(
        f"{len(ids)} ids, {len(found)} returned, {len(gone)} gone, "
        f"{sum(not playable(v) for v in found.values())} not playable, {units} units"
    )


def cmd_judge(max_cost: float) -> None:
    key = read_key("OPENROUTER_API_KEY", "openrouter.env")
    table, videos = dish_table(), load_json(ENRICHED, {})["videos"]
    judged = load_json(JUDGED, {})
    spent = sum(j.get("cost", 0) for d in judged.values() for j in d.values())
    for dish_id, ids in stored().items():
        entries = [
            (f"{dish_id}|{i}", table[dish_id], videos[i]) for i in ids if playable(videos.get(i))
        ]
        if not entries:
            continue
        for model in JUDGES:
            if (judged.get(dish_id, {}).get(model) or {}).get("judgements"):
                continue
            if spent >= max_cost:
                print(f"stop: spending cap {max_cost} reached")
                save_json(JUDGED, judged)
                return
            keys = [k for k, _, _ in entries]
            prompt = JUDGE_PROMPT.format(items="\n".join(item_text(k, d, v) for k, d, v in entries))
            res = chat(key, model, prompt)
            parsed = parse_judgements(res.get("text", ""), keys) if "error" not in res else None
            if (
                parsed is None and "error" not in res
            ):  # one retry for an unusable answer, as in the study
                again = chat(key, model, prompt)
                again["calls"] += res["calls"]
                again["cost"] += res["cost"]
                res = again
                parsed = parse_judgements(res.get("text", ""), keys) if "error" not in res else None
            spent += res["cost"]
            judged.setdefault(dish_id, {})[model] = {
                "judgements": parsed,
                "calls": res["calls"],
                "cost": res["cost"],
                "error": res.get("error") or (None if parsed else "unparsable"),
            }
            save_json(JUDGED, judged)
    calls = sum(j["calls"] for d in judged.values() for j in d.values())
    print(f"judged {len(judged)} dishes, {calls} calls, ${spent:.3f}")


def pairs_from_files() -> dict[str, dict]:
    videos, judged, table = load_json(ENRICHED, {})["videos"], load_json(JUDGED, {}), dish_table()
    pairs = {}
    for dish_id, ids in stored().items():
        for rank, i in enumerate(ids):
            k = f"{dish_id}|{i}"
            v = videos.get(i)
            pairs[k] = {
                "dish": dish_id,
                "dish_name": table[dish_id]["name"],
                "video": i,
                "rank": rank,
                "playable": playable(v),
                "title": (v or {}).get("title"),
                "channel": (v or {}).get("channel"),
                "judges": {
                    m: ((judged.get(dish_id, {}).get(m) or {}).get("judgements") or {}).get(k, {})
                    for m in JUDGES
                }
                if playable(v)
                else {},
            }
    return pairs


def cmd_review() -> None:
    pairs = {k: p for k, p in pairs_from_files().items() if p["playable"]}
    queue = review_queue(pairs)
    videos = load_json(ENRICHED, {})["videos"]
    save_json(
        QUEUE,
        [
            {
                "pair": k,
                "why": why,
                **pairs[k],
                "description": videos[pairs[k]["video"]]["description"],
                "tags": videos[pairs[k]["video"]]["tags"],
                "duration_s": videos[pairs[k]["video"]]["duration_s"],
            }
            for k, why in sorted(queue.items())
        ],
    )
    print({w: sum(1 for x in queue.values() if x == w) for w in set(queue.values())}, len(queue))


def cmd_build() -> None:
    pairs, videos = pairs_from_files(), load_json(ENRICHED, {})["videos"]
    review = load_json(REVIEW, {})
    queue = review_queue({k: p for k, p in pairs.items() if p["playable"]})
    out, report = {}, {}
    for k, p in pairs.items():
        if not p["playable"]:
            keep, basis = False, "gone_or_not_embeddable"
        else:
            keep, basis = decide(p, queue.get(k), review.get(k))
        report[k] = {
            **p,
            "queued": queue.get(k),
            "review": review.get(k),
            "keep": keep,
            "basis": basis,
        }
        entry = out.setdefault(p["dish"], {"fetched_at": now_iso(), "videos": []})
        if keep:
            v = videos[p["video"]]
            entry["videos"].append(
                {
                    f: v[f]
                    for f in ("id", "title", "channel", "thumbnail", "duration_s", "view_count")
                }
            )
    save_json(VERIFIED, {"schema": 1, "dishes": out})
    save_json(REPORT, report)
    print(f"kept {sum(r['keep'] for r in report.values())} of {len(report)} pairs")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("stage", choices=("enrich", "judge", "review", "build"))
    ap.add_argument("--allow-network", action="store_true")
    ap.add_argument("--max-cost", type=float, default=4.0)
    args = ap.parse_args(argv)
    if args.stage in ("enrich", "judge") and not args.allow_network:
        ap.error("this stage calls external services; pass --allow-network")
    {
        "enrich": cmd_enrich,
        "judge": lambda: cmd_judge(args.max_cost),
        "review": cmd_review,
        "build": cmd_build,
    }[args.stage]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
