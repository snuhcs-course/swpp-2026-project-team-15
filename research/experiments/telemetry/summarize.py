# AI-generated with Claude Code (Opus 5.5), 2026-11-20; reviewed by Jaehyuk Choi.
# Modified with Claude Code (Opus 5.5), 2026-11-26: version and period filters, crashes, scanner
# requests apart from the app's routes, cooking mode (T4).
"""Summarise the beta week's usage file (one JSON object per line) into the metrics of README.md.

    uv run python ../research/experiments/telemetry/summarize.py usage.jsonl [--out summary.json]
        [--version 1.0.1 ...] [--since 2026-12-07] [--until 2026-12-11]

--version keeps the app events of those app versions (development builds such as
1.0.0-cloud-test are left out); request records carry no version and are kept. --since and
--until take a date (a whole day, UTC) or an ISO time and apply to both kinds of record; app
events are placed by the time the server received them.

Every rate is printed with its counts; nothing is judged against a threshold.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
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


# A route outside the API: internet scanners probing the open port, not the app.
UNMATCHED = "unmatched"


def _instant(text: str, *, end: bool) -> int:
    """Milliseconds since the epoch; a bare date means the start (or the end) of that UTC day."""
    try:
        day = date.fromisoformat(text)
    except ValueError:
        moment = datetime.fromisoformat(text)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        return int(moment.timestamp() * 1000)
    start = datetime(day.year, day.month, day.day, tzinfo=UTC) + timedelta(days=1 if end else 0)
    return int(start.timestamp() * 1000) - (1 if end else 0)


def _when(record: dict[str, Any]) -> int | None:
    """Server time: when an app event arrived (a phone clock can be wrong), else its own time."""
    received = record.get("received")
    if isinstance(received, str):
        try:
            return _instant(received, end=False)
        except ValueError:
            pass
    t = record.get("t")
    return t if isinstance(t, int) else None


def select(
    records: list[dict[str, Any]],
    versions: Iterable[str] = (),
    since: str | None = None,
    until: str | None = None,
) -> list[dict[str, Any]]:
    """The records of a test period and of the given app versions (all versions when none)."""
    wanted = set(versions)
    low = _instant(since, end=False) if since else None
    high = _instant(until, end=True) if until else None
    out = []
    for r in records:
        if wanted and r.get("kind") == "app" and r.get("version") not in wanted:
            continue
        if low is not None or high is not None:
            t = _when(r)
            if t is None or (low is not None and t < low) or (high is not None and t > high):
                continue
        out.append(r)
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
    api = Counter()
    scanners = 0
    for route, c in by_route.items():
        if route.endswith(f" {UNMATCHED}"):
            scanners += sum(c.values())
        else:
            api.update(c)
    app_errors = Counter(e["name"] for e in app if e.get("status") == "error")
    app_errors.update(e["name"] for e in app if e["name"] == "player_error")
    return {
        "requests": routes,
        # The app's routes only; requests to paths outside the API are counted apart.
        "api_server_errors": _rate(api["server_error"], sum(api.values())),
        "unmatched_requests": scanners,
        "app": dict(app_errors),
    }


def _day(record: dict[str, Any]) -> str | None:
    t = _when(record)
    return datetime.fromtimestamp(t / 1000, UTC).date().isoformat() if t is not None else None


def crashes(app: list[dict[str, Any]]) -> dict[str, Any]:
    """Crash and ANR counts with their exposure, per app version; no rate is judged (a few
    testers for a week cannot bound a crash rate, so each crash bucket is read and fixed).

    Exposure: user-days = distinct (install, UTC day) with any app event, and sessions started.
    A crash or ANR is reported on the next launch, so it is counted on the day it arrived. Native
    crashes arrive as crash events with exception.type "native" and no place."""
    events = [e for e in app if e["name"] == "crash"]

    def n(e: dict[str, Any]) -> int:
        return int(e.get("count", 1))

    by_version: dict[str, Any] = {}
    for version in sorted({e.get("version", "missing") for e in app}):
        mine = [e for e in app if e.get("version", "missing") == version]
        crashed = [e for e in mine if e["name"] == "crash"]
        froze = [e for e in mine if e["name"] == "anr"]
        installs = {e["install"] for e in mine}
        user_days = {(e["install"], _day(e)) for e in mine}
        count = sum(n(e) for e in crashed)
        by_version[version] = {
            "crashes": count,
            "user_days": len(user_days),
            "sessions": sum(1 for e in mine if e["name"] == "session_start"),
            "crash_free_installs": {
                "k": len(installs - {e["install"] for e in crashed}),
                "n": len(installs),
            },
            # descriptive only: crashes per user-day of this version
            "crashes_per_user_day": round(count / len(user_days), 3) if user_days else None,
            # the app froze and Android closed it (API 30+ phones only), same exposure
            "anrs": len(froze),
            "anr_free_installs": {
                "k": len(installs - {e["install"] for e in froze}),
                "n": len(installs),
            },
            "anrs_per_user_day": round(len(froze) / len(user_days), 3) if user_days else None,
        }

    by_device: Counter = Counter()
    devices_installs: dict[str, set[str]] = defaultdict(set)
    for e in events:
        device = e.get("device.model.identifier", "missing")
        by_device[device] += n(e)
        devices_installs[device].add(e["install"])

    # A crash bucket: the thrown class and the first frame of the app's code.
    buckets: dict[tuple[str, str], dict[str, Any]] = {}
    for e in events:
        function = e.get("code.function.name")
        line = e.get("code.line.number")
        place = f"{function}:{line}" if function and line is not None else function or "?"
        key = (e.get("exception.type", "missing"), place)
        b = buckets.setdefault(
            key,
            {"type": key[0], "where": key[1], "crashes": 0, "installs": set(), "versions": set()},
        )
        b["crashes"] += n(e)
        b["installs"].add(e["install"])
        b["versions"].add(e.get("version", "missing"))
    ordered = sorted(buckets.values(), key=lambda b: (-b["crashes"], b["type"], b["where"]))
    return {
        "by_version": by_version,
        # Exposure per phone model is unknown: only crash events carry the model.
        "by_device": {
            d: {"crashes": c, "installs_with_crash": len(devices_installs[d])}
            for d, c in by_device.most_common()
        },
        "buckets": [
            b | {"installs": len(b["installs"]), "versions": sorted(b["versions"])} for b in ordered
        ],
    }


def task_cook(
    app: list[dict[str, Any]], sessions: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    """T4: sessions with a successful recipe_view in which cooking mode was finished
    (cook_complete), testers who finished at least once, and how cooking ended by recipe."""
    total = done = 0
    for events in sessions.values():
        if any(e["name"] == "recipe_view" and e.get("status") == "ok" for e in events):
            total += 1
            done += any(e["name"] == "cook_complete" for e in events)
    installs = {e["install"] for e in app}
    finished = {e["install"] for e in app if e["name"] == "cook_complete"}
    by_recipe: dict[str, Any] = {}
    for recipe in ("original", "revised"):
        starts = [e for e in app if e["name"] == "cook_start" and e.get("recipe") == recipe]
        ends = [e for e in app if e["name"] == "cook_complete" and e.get("recipe") == recipe]
        exits = [e for e in app if e["name"] == "cook_exit" and e.get("recipe") == recipe]
        by_recipe[recipe] = {
            "starts": len(starts),
            "completes": len(ends),
            "exits": len(exits),
            "time": _spread([e["duration_ms"] for e in ends if "duration_ms" in e]),
        }
    exits = [e for e in app if e["name"] == "cook_exit"]
    reached = Counter(f"{e.get('count', '?')}/{e.get('steps', '?')}" for e in exits)
    shares = [e["count"] / e["steps"] for e in exits if e.get("steps") and "count" in e]
    return {
        "completion": _rate(done, total),
        "testers_with_complete": {"k": len(finished), "n": len(installs)},
        "by_recipe": by_recipe,
        "exit_step_reached": dict(sorted(reached.items())),
        "exit_share_of_steps": {
            "n": len(shares),
            "median": round(statistics.median(shares), 3) if shares else None,
        },
    }


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
        "T4_recipe_to_cooked": task_cook(app, sessions),
        "errors": errors(app, requests),
        "crashes": crashes(app),
        "usage": usage(app, sessions),
    }


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("usage", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--version", action="append", default=[], help="app version to keep")
    parser.add_argument("--since", help="first day or ISO time (UTC unless given)")
    parser.add_argument("--until", help="last day or ISO time (UTC unless given)")
    args = parser.parse_args(argv)
    records = read(args.usage.read_text(encoding="utf-8").splitlines())
    result = summarize(select(records, args.version, args.since, args.until))
    result["filters"] = {"version": args.version, "since": args.since, "until": args.until}
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return result


if __name__ == "__main__":
    main()
