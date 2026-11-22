# AI-generated with Claude Code (Opus 5.5), 2026-11-20; reviewed by Jaehyuk Choi.
"""The beta-week summary on synthetic usage records whose answers are known."""

import json

from experiments.telemetry.summarize import main, read, summarize

A, B = "11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222"


def app(session, t, name, **fields):
    return {
        "kind": "app",
        "install": A,
        "session": session,
        "version": "1.0",
        "t": t,
        "name": name,
        **fields,
    }


RECORDS = [
    # session 1: fills the fridge, gets dishes after 3 s, opens a recipe 2 s later, revises once
    app("s1", 0, "session_start"),
    app("s1", 1_000, "fridge_add", source="photo", count=4),
    app("s1", 4_000, "dish_list", status="ok", count=12, duration_ms=2_500),
    app("s1", 6_000, "recipe_view", status="ok", dish_id="tofu-soup"),
    app("s1", 9_000, "revise", status="revised", duration_ms=3_000, dish_id="tofu-soup"),
    app("s1", 20_000, "session_end", duration_ms=20_000),
    # session 2: fills the fridge, the list fails; a refused revision; a player error
    app("s2", 0, "fridge_add", source="manual", count=1),
    app("s2", 2_000, "dish_list", status="error", code=502),
    app("s2", 3_000, "revise", status="refused", duration_ms=100),
    app("s2", 4_000, "player_error", dish_id="tofu-soup"),
    {  # a record written before the switch to OpenTelemetry names
        "kind": "request",
        "t": 1,
        "method": "POST",
        "route": "/dishes/suggest",
        "status": 200,
        "ms": 2400,
    },
    {
        "kind": "request",
        "t": 2,
        "http.request.method": "POST",
        "http.route": "/dishes/suggest",
        "http.response.status_code": 502,
        "duration_ms": 90000,
    },
]


def test_tasks_errors_and_usage_from_known_records():
    s = summarize(RECORDS)
    assert s["T1_fill_fridge_to_dish_list"]["completion"] == {"done": 1, "total": 2, "rate": 0.5}
    assert s["T1_fill_fridge_to_dish_list"]["time"]["median_ms"] == 3_000
    assert s["T2_dish_list_to_recipe"]["completion"]["rate"] == 1.0
    assert s["T2_dish_list_to_recipe"]["time"]["median_ms"] == 2_000
    assert s["T3_revise"]["outcomes"] == {"revised": 1, "refused": 1}
    assert s["T3_revise"]["completion"]["rate"] == 0.5
    assert s["errors"]["requests"]["POST /dishes/suggest"]["server_error_rate"] == 0.5
    assert s["errors"]["app"] == {"dish_list": 1, "player_error": 1}
    assert s["usage"]["installs"] == 1 and s["usage"]["sessions"] == 2
    assert s["usage"]["fridge_add_sources"] == {"photo": 1, "manual": 1}


def test_cut_lines_are_skipped_and_the_cli_writes_json(tmp_path):
    usage = tmp_path / "usage.jsonl"
    usage.write_text(
        "\n".join(json.dumps(r) for r in RECORDS) + '\n{"kind": "app", "na', encoding="utf-8"
    )
    assert len(read(usage.read_text().splitlines())) == len(RECORDS)
    main([str(usage), "--out", str(tmp_path / "s.json")])
    assert json.loads((tmp_path / "s.json").read_text())["records"]["app"] == 10


def test_empty_file_gives_empty_rates():
    s = summarize([])
    assert s["T1_fill_fridge_to_dish_list"]["completion"]["rate"] is None
    assert s["T3_revise"]["time"]["median_ms"] is None
