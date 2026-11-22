# ADR 007: Beta-week usage data (telemetry)

- **Status:** Accepted (2026-11-20)

## Context

Iteration 5 asks for a week of beta testing in the wild: "instrument your app to collect basic usage data" and "track meaningful metrics (e.g., task completion, time on task, errors)", read together with short interviews; the evaluation then summarises telemetry and usage data for the Wiki and the poster (Week 2-2 Project Overview, p.28–29, p.31). Week 12-2 shows analytics as the classic thing that spreads through every file (MiniShop `Analytics.kt`, p.4) and recommends separating what varies behind a role, depending on the interface and creating once and injecting instead of a global instance (p.29 and the Singleton slide). The server has no database and the API container's file system is read-only.

## Decision

- **What is sent.** A closed set of ten event names (`session_start`, `session_end`, `screen_view`, `fridge_add`, `recognition`, `dish_list`, `dish_open`, `recipe_view`, `revise`, `player_error`) with narrow fields only: time, dish id, count, duration, status, source of added items, screen, HTTP status. The server schema forbids any other field and checks patterns, so there is no field for ingredient names, photos or nicknames. *Corrected 2026-11-20 (integrity review):* the earlier wording "free text cannot be sent" was too strong — `dish_id` accepted any short lowercase id and `app_version` any short version string; a `dish_id` not in the dish list is now dropped before storage, and `app_version` stays a short pattern-checked string. Each batch carries a random install id (new after a data reset), a session id and the app version.
- **Consent.** Nothing is sent until the first-run notice is answered; a switch in 내 정보 turns it off at any time (off: nothing is buffered or sent). The ⓘ dialog repeats what is and is not sent.
- **App.** `Telemetry` is the role (`track`, `flush`); `RemoteTelemetry` buffers in memory and posts batches of 20 and when the app goes to the background, best effort (a failed post is dropped); `NoTelemetry` is the default for tests. One instance is created for the whole app process with its own scope and handed to the ViewModels that own the events (fridge, dish list, recipe session); screens only report which screen is shown and player errors through those ViewModels. *Amended 2026-11-20 (integrity review):* it was first created inside `AppNavHost` on a screen-bound scope, so after a rotation the surviving ViewModels kept a sender whose scope was cancelled and their events were lost; a session now also survives configuration changes, and a `session_start` before the stored consent has loaded is held until it has.
- **Server.** `POST /telemetry/events` appends the events as JSON lines to `TELEMETRY_FILE`. One line per request (route template, status, time; never the body or the query) is added so server errors count for every app build. *Amended 2026-11-20:* this line now comes from OpenTelemetry's FastAPI instrumentation (`opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi`) with the standard HTTP names (`http.request.method`, `http.route`, `http.response.status_code`, `duration_ms`) instead of a hand-written middleware (`method`, `route`, `status`, `ms`; the summary reads both). The tracer provider is private to the app and its only exporter writes to the same local file; no network exporter package is installed, so `OTEL_*` variables cannot send data anywhere (tested). The sink is a one-method role (`TelemetrySink`) created once in `main.py`; unset `TELEMETRY_FILE` turns collection off. Compose mounts a writable `TELEMETRY_DIR` at `/telemetry`; the rest stays read-only.
- **Summary.** `research/experiments/telemetry/summarize.py` turns the file into the task metrics of `research/experiments/telemetry/README.md`, each rate with its counts.

## Consequences

- Task metrics are derived from event order within a session on the server side; the app needs no task bookkeeping, and the definitions can change after the week without a new app build.
- Usage before the notice is answered (most of onboarding) is not counted.
- The phone's clock times the events; durations are differences on one phone, so clock offsets cancel, but times across phones are not comparable.
- No authentication: anyone can post well-formed events to the team server. Acceptable for a one-week demo; the file can be filtered by install id and app version. *Added 2026-11-20 (integrity review):* so that a loop of posts cannot fill the disk, the file stops growing at 200 MB (a beta week of ~20 testers × 7 days × ~600 lines a day × ~250 bytes is ~21 MB; the limit is ten times that) and logs once when it is reached, and nginx limits `/telemetry/events` to 60 requests a minute per address with a burst of 60 (one phone sends a few batches a minute at most; the headroom covers ~20 testers behind one campus address).
- The request lines skip `/health`, `/ready` and the usage upload by anchored patterns (an unanchored `ready` once also skipped `/dishes/already-ready/recipe`). The app refuses to start under `opentelemetry-instrument`, whose global provider would take exporters from `OTEL_*` variables.

## Not now

- No third-party analytics SDK or hosted backend (another data processor to disclose, and a dependency for ten events). No OpenTelemetry collector or OTLP exporter: the data stays in the server's file.
- No retry queue or on-device storage of unsent events.
- No per-screen dwell time or tap-level tracking.
