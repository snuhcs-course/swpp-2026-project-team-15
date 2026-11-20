# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Run the YouTube discovery study defined in criteria.json.

Default: a dry run that prints the plan (no network). Live calls need --allow-live-api.
  --methods a,b,c   which methods to run (default all)
  --max-search N    cap on search.list calls for method A (default 0; cached dishes need none)
Keys are read from ~/.config/mylittlechef/ and never printed. Raw results (titles, ids) are written
under the ignored data/youtube-discovery/ directory.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

from . import scoring
from .youtube_client import YouTubeClient, to_video

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CFG = Path.home() / ".config" / "mylittlechef"
CACHE = REPO.parent.parent / "artifacts" / "dish-cache" / "videos-demo.json"
OUT = REPO / "data" / "youtube-discovery" / "results.json"
MODEL = "google/gemini-2.5-flash-lite:online"
URL = "https://openrouter.ai/api/v1/chat/completions"
PROMPT = (
    "유튜브에서 '{q}' 영상 3개를 찾아 각각 YouTube 주소(watch?v=)와 제목을 JSON 배열로만 답해줘. "
    "주소는 검색 결과에서 실제로 확인한 것만."
)


def read_key(file: str, name: str) -> str:
    for line in (CFG / file).read_text(encoding="utf-8").splitlines():
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip()
    raise SystemExit(f"missing {name}")


def load_criteria() -> dict:
    return json.loads((HERE / "criteria.json").read_text(encoding="utf-8"))


def dish_table() -> dict[str, dict]:
    # the sample was drawn from the catalog of the freeze (130 dishes)
    frozen = REPO / "research" / "experiments" / "dish_eval" / "catalog_at_freeze.json"
    raw = json.loads(frozen.read_text("utf-8"))
    return {d["id"]: d for d in raw["dishes"]}


def ask_model(key: str, query: str) -> dict:
    body = {
        "model": MODEL,
        "temperature": 0,
        "messages": [{"role": "user", "content": PROMPT.format(q=query)}],
    }
    t0 = time.monotonic()
    with httpx.Client(timeout=90) as c:
        r = c.post(URL, json=body, headers={"Authorization": f"Bearer {key}"})
    latency = time.monotonic() - t0
    if r.status_code != 200:
        return {"error": f"HTTP {r.status_code}", "latency_s": latency, "cost": 0.0}
    data = r.json()
    msg = data["choices"][0]["message"]
    cites = [a.get("url_citation", {}).get("url", "") for a in (msg.get("annotations") or [])]
    return {
        "ids": scoring.extract_ids(msg.get("content") or "", cites),
        "latency_s": latency,
        "cost": float((data.get("usage") or {}).get("cost") or 0.0),
    }


def row_from(videos_raw: list[dict], dish: dict, **extra) -> dict:
    """Score verified candidates (raw videos.list items) of one dish."""
    exist = len(videos_raw)
    vids = [v for item in videos_raw if (v := to_video(item))]
    names = [dish["name"], *dish.get("aliases", [])]
    kept = scoring.keep_top(vids, dish["name"])
    return {
        "dish": dish["id"],
        "existing": exist,
        "embeddable": len(vids),
        "named": sum(scoring.names_dish(v["title"], dish["name"]) for v in vids),
        "named_loose": sum(scoring.names_any(v["title"], names) for v in vids),
        "kept": len(kept),
        "kept_views": [v["view_count"] for v in kept],
        "titles": [v["title"] for v in vids],
        **extra,
    }


def run_a(yt: YouTubeClient, dish: dict) -> dict:
    t0 = time.monotonic()
    ids = yt.search(f"{dish['name']} 레시피")
    items = yt.details(ids) if ids else []
    return row_from(
        items,
        dish,
        extracted=None,
        cost_usd=0.0,
        search_calls=1,
        videos_calls=1 if ids else 0,
        latency_s=[time.monotonic() - t0],
        candidates_comparable=True,
        live=True,
    )


def cached_a(entry: dict, dish: dict) -> dict:
    vids = entry["videos"]
    names = [dish["name"], *dish.get("aliases", [])]
    kept = scoring.keep_top(vids, dish["name"])
    return {
        "dish": dish["id"],
        "extracted": None,
        "existing": len(vids),
        "embeddable": len(vids),
        "named": sum(scoring.names_dish(v["title"], dish["name"]) for v in vids),
        "named_loose": sum(scoring.names_any(v["title"], names) for v in vids),
        "kept": len(kept),
        "kept_views": [v["view_count"] for v in kept],
        "cost_usd": 0.0,
        "search_calls": 0,
        "videos_calls": 0,
        "latency_s": [],
        "candidates_comparable": False,
        "live": False,
        "titles": [v["title"] for v in vids],
    }


def model_ids(key: str, queries: list[str]) -> dict:
    ids: list[str] = []
    out = {"cost": 0.0, "latency_s": [], "errors": []}
    for q in queries:
        res = ask_model(key, q)
        out["cost"] += res["cost"]
        out["latency_s"].append(res["latency_s"])
        if "error" in res:
            out["errors"].append(res["error"])
        ids += [i for i in res.get("ids", []) if i not in ids]
    return {**out, "ids": ids, "model_calls": len(queries)}


def verified(yt: YouTubeClient, dish: dict, found: dict) -> dict:
    ids = found["ids"]
    items = yt.details(ids[:50]) if ids else []
    return row_from(
        items,
        dish,
        extracted=len(ids),
        cost_usd=found["cost"],
        search_calls=0,
        videos_calls=1 if ids else 0,
        latency_s=found["latency_s"],
        candidates_comparable=True,
        errors=found["errors"],
        model_calls=found["model_calls"],
        ids=ids,
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--allow-live-api", action="store_true")
    ap.add_argument("--methods", default="a,b,c")
    ap.add_argument("--max-search", type=int, default=0)
    args = ap.parse_args(argv)
    crit = load_criteria()
    s = crit["sample"]
    methods = set(args.methods.split(","))
    live_a = s["extra"][:20]
    plan = {
        "dishes": len(s["cached"]) + len(s["extra"]),
        "a_cached": len(s["cached"]),
        "a_live_max": min(args.max_search, len(live_a)),
        "model_calls": (40 if "b" in methods else 0) + (40 if "c" in methods else 0),
        "videos_list_calls": 40 + 40 * ("a" in methods),
    }
    print(json.dumps(plan))
    if not args.allow_live_api:
        print("dry run: no call made (use --allow-live-api)")
        return 0
    table = dish_table()
    yt = YouTubeClient(read_key("youtube.env", "YOUTUBE_API_KEY"))
    orkey = read_key("openrouter.env", "OPENROUTER_API_KEY")
    results = json.loads(OUT.read_text("utf-8")) if OUT.exists() else {"a": {}, "b": {}, "c": {}}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    cache = json.loads(CACHE.read_text("utf-8")) if CACHE.exists() else {}
    cache = cache.get("dishes", cache)
    searches = 0
    for did in s["cached"] + s["extra"]:
        dish = table[did]
        if "a" in methods and did not in results["a"]:
            if did in cache:
                results["a"][did] = cached_a(cache[did], dish)
            elif did in live_a and searches < args.max_search:
                results["a"][did] = run_a(yt, dish)
                searches += 1
        if "b" in methods and did not in results["b"]:
            first = model_ids(orkey, [f"{dish['name']} 레시피"])
            results["b"][did] = verified(yt, dish, first)
        if "c" in methods and did not in results["c"] and did in results["b"]:
            first_row = results["b"][did]
            second = model_ids(orkey, [f"{dish['name']} 만들기"])
            both = {
                "ids": first_row["ids"] + [i for i in second["ids"] if i not in first_row["ids"]],
                "cost": first_row["cost_usd"] + second["cost"],
                "latency_s": first_row["latency_s"] + second["latency_s"],
                "errors": first_row["errors"] + second["errors"],
                "model_calls": first_row["model_calls"] + 1,
            }
            results["c"][did] = verified(yt, dish, both)
        OUT.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"search.list calls this run: {searches}; videos.list requests: {yt.requests - searches}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
