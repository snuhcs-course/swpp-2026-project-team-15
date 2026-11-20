# AI-generated with Claude Code (Opus 5.5), 2026-11-20; reviewed by Jaehyuk Choi.
"""Summarise the beta week's usage file (one JSON object per line) into the metrics of README.md.

    uv run python ../research/experiments/telemetry/summarize.py usage.jsonl [--out summary.json]

Every rate is printed with its counts; nothing is judged against a threshold.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any


def read(lines: Iterable[str]) -> list[dict[str, Any]]:
    out = []
    for line in lines:
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except ValueError:
                continue  # a cut last line after a crash
    return out


def _spread(values: list[int]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "median_ms": None, "p90_ms": None}
    ordered = sorted(values)
    p90 = ordered[min(len(ordered) - 1, round(0.9 * (len(ordered) - 1)))]
    return {"n": len(values), "median_ms": statistics.median(ordered), "p90_ms": p90}


def _rate(done: int, total: int) -> dict[str, Any]:
    return {"done": done, "total": total, "rate": round(done / total, 3) if total else None}


def _sessions(app: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in app:
        by[e["session"]].append(e)
    for events in by.values():
        events.sort(key=lambda e: e["t"])
    return by


def _first_after(events: list[dict[str, Any]], start: int, name: str) -> dict[str, Any] | None:
    return next((e for e in events if e["t"] >= start and e["name"] == name), None)


def task_fill(sessions: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """T1: first ingredients added in a session -> the next dish list (done: at least one dish)."""
    total = done = 0
    times = []
    for events in sessions.values():
        start = next((e for e in events if e["name"] == "fridge_add"), None)
        if start is None:
            continue
        total += 1
        end = _first_after(events, start["t"], "dish_list")
        if end and end.get("status") == "ok" and end.get("count", 0) > 0:
            done += 1
            times.append(end["t"] - start["t"])
    return {"completion": _rate(done, total), "time": _spread(times)}


def task_open(sessions: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """T2: first non-empty dish list in a session -> a recipe shown."""
    total = done = 0
    times = []
    for events in sessions.values():
        start = next(
            (e for e in events if e["name"] == "dish_list" and e.get("status") == "ok"), None
        )
        if start is None:
            continue
        total += 1
        end = next(
            (
                e
                for e in events
                if e["t"] >= start["t"] and e["name"] == "recipe_view" and e.get("status") == "ok"
            ),
            None,
        )
        if end:
            done += 1
            times.append(end["t"] - start["t"])
    return {"completion": _rate(done, total), "time": _spread(times)}


def task_revise(app: list[dict[str, Any]]) -> dict[str, Any]:
    """T3: each "내 재료로 바꾸기" attempt and how it ended."""
    tries = [e for e in app if e["name"] == "revise"]
    outcomes = Counter(e.get("status", "missing") for e in tries)
    return {
        "outcomes": dict(outcomes),
        "completion": _rate(outcomes["revised"], len(tries)),
        "time": _spread([e["duration_ms"] for e in tries if "duration_ms" in e]),
    }


def errors(app: list[dict[str, Any]], requests: list[dict[str, Any]]) -> dict[str, Any]:
    by_route: dict[str, Counter] = defaultdict(Counter)
    for r in requests:
        # OpenTelemetry HTTP names since 2026-11-20; the first beta records used short names.
        status = r.get("http.response.status_code", r.get("status"))
        method = r.get("http.request.method", r.get("method"))
        route = r.get("http.route", r.get("route"))
        kind = "server_error" if status >= 500 else "client_error" if status >= 400 else "ok"
        by_route[f"{method} {route}"][kind] += 1
    routes = {
        route: {
            **dict(c),
            "total": sum(c.values()),
            "server_error_rate": round(c["server_error"] / sum(c.values()), 3),
        }
        for route, c in sorted(by_route.items())
    }
    app_errors = Counter(e["name"] for e in app if e.get("status") == "error")
    app_errors.update(e["name"] for e in app if e["name"] == "player_error")
    return {"requests": routes, "app": dict(app_errors)}


def usage(app: list[dict[str, Any]], sessions: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    installs: dict[str, set[str]] = defaultdict(set)
    for e in app:
        installs[e["install"]].add(e["session"])
    lengths = [e["duration_ms"] for e in app if e["name"] == "session_end" and "duration_ms" in e]
    return {
        "installs": len(installs),
        "sessions": len(sessions),
        "sessions_per_install": _spread([len(s) for s in installs.values()]) | {"unit": "sessions"},
        "session_length": _spread(lengths),
        "screens": dict(Counter(e["screen"] for e in app if e["name"] == "screen_view")),
        "fridge_add_sources": dict(
            Counter(e.get("source") for e in app if e["name"] == "fridge_add")
        ),
    }


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    app = [r for r in records if r.get("kind") == "app"]
    requests = [r for r in records if r.get("kind") == "request"]
    sessions = _sessions(app)
    return {
        "records": {"app": len(app), "request": len(requests)},
        "T1_fill_fridge_to_dish_list": task_fill(sessions),
        "T2_dish_list_to_recipe": task_open(sessions),
        "T3_revise": task_revise(app),
        "errors": errors(app, requests),
        "usage": usage(app, sessions),
    }


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("usage", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    result = summarize(read(args.usage.read_text(encoding="utf-8").splitlines()))
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return result


if __name__ == "__main__":
    main()
