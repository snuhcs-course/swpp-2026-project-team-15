# AI-generated with Claude Code (Opus 5.5), 2026-11-20; reviewed by Jaehyuk Choi.
# Modified with Claude Code (Opus 5.5), 2026-11-26: filters, crashes, scanner requests.
"""The beta-week summary on synthetic usage records whose answers are known."""

import json

from experiments.telemetry.summarize import main, read, select, summarize

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


def request(t, route, status):
    return {
        "kind": "request",
        "t": t,
        "http.request.method": "GET",
        "http.route": route,
        "http.response.status_code": status,
        "duration_ms": 5,
    }


DAY = 86_400_000
DEC7 = 1_796_601_600_000  # 2026-12-07T00:00:00Z


def test_scanner_requests_are_kept_apart_from_the_apps_error_rate():
    s = summarize(
        [request(1, "/dishes", 200), request(2, "/dishes", 503)]
        + [request(3, "unmatched", 404)] * 8
    )
    assert s["errors"]["api_server_errors"] == {"done": 1, "total": 2, "rate": 0.5}
    assert s["errors"]["unmatched_requests"] == 8
    assert s["errors"]["requests"]["GET unmatched"]["total"] == 8  # still visible


def test_crashes_with_exposure_buckets_and_no_rate_judgement():
    B_ = {"install": B}
    s = summarize(
        [
            app("s1", 0, "session_start"),
            app("s2", DAY, "session_start"),  # install A on two days
            app("s3", 0, "session_start") | B_,
            app(
                "s3",
                1,
                "crash",
                error="java.lang.IllegalStateException",
                where="a.B.c:3",
                device="SM-S918N",
                count=2,
            )
            | B_,
            app(
                "s2",
                DAY + 1,
                "crash",
                error="java.lang.IllegalStateException",
                where="a.B.c:3",
                device="Pixel 7",
            ),
            app("s2", DAY + 2, "crash", error="java.lang.NullPointerException", device="Pixel 7"),
            app("x", 0, "session_start") | {"version": "1.0.0-cloud-test"},
            app("s1", 5, "anr", device="SM-S918N"),
        ]
    )
    c = s["crashes"]
    v = c["by_version"]["1.0"]
    assert v["crashes"] == 4 and v["sessions"] == 3
    assert v["user_days"] == 3  # A on day 0 and day 1, B on day 0
    assert v["crash_free_installs"] == {"k": 0, "n": 2}
    assert v["crashes_per_user_day"] == 1.333
    assert v["anrs"] == 1 and v["anr_free_installs"] == {"k": 1, "n": 2}
    assert v["anrs_per_user_day"] == 0.333
    assert c["by_version"]["1.0.0-cloud-test"]["crash_free_installs"] == {"k": 1, "n": 1}
    assert c["by_device"]["SM-S918N"] == {"crashes": 2, "installs_with_crash": 1}
    first, second = c["buckets"]
    assert (first["error"], first["where"], first["crashes"], first["installs"]) == (
        "java.lang.IllegalStateException",
        "a.B.c:3",
        3,
        2,
    )
    assert second["where"] == "?" and second["crashes"] == 1
    assert "pass" not in json.dumps(c)


def test_version_and_period_filters():
    beta = app("b", DEC7 + 1_000, "session_start") | {"version": "1.0.1"}
    dev = app("d", DEC7 + 1_000, "session_start") | {"version": "1.0.0-cloud-test"}
    # a phone clock a day behind: the server's arrival time decides the period
    late_clock = app("c", DEC7 - DAY, "session_start") | {
        "version": "1.0.1",
        "received": "2026-12-07T09:00:00+00:00",
    }
    early = app("e", DEC7 - 1, "session_start") | {"version": "1.0.1"}
    after = app("f", DEC7 + 5 * DAY, "session_start") | {"version": "1.0.1"}
    inside, outside = request(DEC7 + 10, "/dishes", 200), request(DEC7 - 10, "/dishes", 200)
    records = [beta, dev, late_clock, early, after, inside, outside]

    kept = select(records, ["1.0.1"], "2026-12-07", "2026-12-11")
    assert kept == [beta, late_clock, inside]
    assert select(records, ["1.0.1"]) == [beta, late_clock, early, after, inside, outside]
    # midnight in Korea is 15:00 UTC the day before, so every record is on or after it
    assert len(select(records, since="2026-12-07T00:00:00+09:00")) == len(records)
    assert select(records, until="2026-12-06") == [early, outside]


def test_the_cli_applies_the_filters(tmp_path):
    usage = tmp_path / "usage.jsonl"
    usage.write_text("\n".join(json.dumps(r) for r in RECORDS), encoding="utf-8")
    result = main([str(usage), "--version", "2.0"])
    assert result["records"] == {"app": 0, "request": 2}
    assert result["filters"]["version"] == ["2.0"]
