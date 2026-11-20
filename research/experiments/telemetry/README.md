# Beta-week usage data: metrics

What is collected and why: [ADR 007](../../decisions/adr-007-telemetry.md). Summary: `uv run python ../research/experiments/telemetry/summarize.py <usage.jsonl> --out summary.json` (from `server/`). Every rate is reported with its counts; there are no pass/fail thresholds.

| Metric | Definition (per session, events in phone time order) |
|---|---|
| T1 fill the fridge → dish list | Start: first `fridge_add` (photo, manual, suggestion or pantry). Done: the next `dish_list` has `status=ok` and at least one dish. Time: done − start. A list error or an empty list counts as not done. |
| T2 dish list → recipe | Start: first `dish_list` with `status=ok`. Done: a later `recipe_view` with `status=ok`. Time: done − start. |
| T3 내 재료로 바꾸기 | Each `revise` event; outcomes revised / refused / failed / error; completion = revised share; time = `duration_ms` (request time on the phone). |
| Errors | Requests per route (server lines): server errors (5xx) and client errors (4xx) with totals. App side: events with `status=error` per name, and `player_error`. |
| Usage | Installs, sessions, sessions per install, session length (`session_end.duration_ms`), screen views, sources of added items. |

Limits: sessions without a `fridge_add` (the fridge filled earlier) do not enter T1; usage before the first-run notice is answered is not collected; a phone offline at the end of a session loses that session's last batch.

Checked on synthetic records with known answers (`server/tests/experiments/telemetry/test_summarize.py`).
