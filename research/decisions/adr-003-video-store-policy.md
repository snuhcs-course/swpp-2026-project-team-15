# ADR 003: Stored video lists are served only after they are checked again

- **Status:** Accepted (2026-11-19)

## Context

Finding videos with a web-search model costs about $0.0075 and 3 to 13 s per dish (study: `research/experiments/dish_pipeline`). A demo and a user test open the same few dishes again and again. A list found once can go stale: a video can be deleted, made private or have embedding switched off. The YouTube API terms do not allow keeping API data for long; this project treats 30 days as the hard limit.

## Decision

- A snapshot file (`DISH_VIDEOS`, written by `research/experiments/dish_recipes/collect_videos.py`) keeps video ids per dish with a fetch time. The server reads it at startup; an invalid file stops the server.
- On a request for a dish: if the entry is younger than 30 days, one batched `videos.list` call (about 1 quota unit) confirms that each video still exists, is public and can be embedded. The rest are dropped, the stored order is kept, and the title and thumbnail come from that fresh response. Nothing unverified is ever served.
- If the entry is missing, 30 days old or older, or nothing is left after the check, the web-search model proposes videos (request wording D0) and the same check keeps the usable ones; the result is kept in memory for 24 hours.
- A YouTube failure while checking is an error (502); the server does not serve unchecked ids as a fallback.
- The response carries `source` (`stored` or `discovered`).
- Amended 2026-11-19: the same `videos.list` call asks for the player size (`part=player`, `maxWidth`); a video taller than wide (a Short) is dropped, for stored and discovered lists alike, at no extra quota. The stored lists were rebuilt with landscape videos only (`research/experiments/shorts_removal`). Reason: on the phone a vertical video filled 31.6% of the 16:9 player area.

## Consequences

- A user test makes no model call for dishes in the snapshot, and a deleted or private video disappears from the list at the next request.
- The player can still fail between the check and the play; the app shows "can't play here, open in YouTube" for that case.
- Refreshing the snapshot is a manual step (run the collector before the 30 days end).

## Not now

- No scheduled refresh job and no database for videos.
- No refilling of a list that lost some videos; the user sees what is left, and an empty list triggers a new search.
- No ranking by views or title filter (see the decision record on video discovery).
