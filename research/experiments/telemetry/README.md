# Beta-week usage data: metrics

What is collected and why: [ADR 007](../../decisions/adr-007-telemetry.md). Summary: `uv run python ../research/experiments/telemetry/summarize.py <usage.jsonl> --out summary.json` (from `server/`); for the beta add `--version 1.0.1 --since 2026-12-07 --until 2026-12-11` (app versions apply to app events; the period to both kinds of record, app events by server arrival time). Every rate is reported with its counts; there are no pass/fail thresholds.

| Metric | Definition (per session, events in phone time order) |
|---|---|
| T1 fill the fridge → dish list | Start: first `fridge_add` (photo, manual, suggestion or pantry). Done: the next `dish_list` has `status=ok` and at least one dish. Time: done − start. A list error or an empty list counts as not done. |
| T2 dish list → recipe | Start: first `dish_list` with `status=ok`. Done: a later `recipe_view` with `status=ok`. Time: done − start. |
| T3 내 재료로 바꾸기 | Each `revise` event; outcomes revised / refused / failed / error; completion = revised share; time = `duration_ms` (request time on the phone). |
| Errors | Requests per route (server lines): server errors (5xx) and client errors (4xx) with totals. `api_server_errors`: 5xx ÷ all requests to the app's routes; requests to paths outside the API (`unmatched`, internet scanners on the open port) are counted apart. App side: events with `status=error` per name, and `player_error`. |
| Crashes | Per app version: crash count (with each event's `count`), exposure as user-days (distinct install × UTC day with any app event) and sessions started, crash-free installs k of n, and crashes ÷ user-days as a description only. Per phone model: crashes and installs with a crash (exposure per model is unknown, only crash events carry it). ANRs (`anr` events, API 30+ phones): count, ANR-free installs and ANRs ÷ user-days with the same exposure; native crashes are `crash` events with `error=native`. Crash buckets: `error` + `where`, by frequency, with installs and versions. No crash-rate threshold: a few testers for a week cannot bound a rate (no crash in 30 user-days still allows ~10%), so every bucket is read and fixed. A crash is reported on the next launch, so a tester who never reopens the app is not counted. |
| Usage | Installs, sessions, sessions per install, session length (`session_end.duration_ms`), screen views, sources of added items. |

Limits: sessions without a `fridge_add` (the fridge filled earlier) do not enter T1; usage before the first-run notice is answered is not collected; a phone offline at the end of a session loses that session's last batch.

Checked on synthetic records with known answers (`server/tests/experiments/telemetry/test_summarize.py`).
