# ADR 002: One factory picks the concrete provider classes

- **Status:** Accepted (2026-11-19)

## Context

The dish model and the video lookup are configured from the environment (`DISH_LLM_API_KEY`, `DISH_LLM_MODEL`, `YOUTUBE_API_KEY`, `DISH_VIDEOS`, `DISH_RECIPES`). A second model provider is plausible (the study of answer formats found that behaviour differs between providers), and a missing key must degrade in a known way: the suggest and adapt routes answer 502, stored videos are still served without a model key, recipes are absent without a file.

## Decision

`dependencies.py` has one function per role family (`build_chat_model`, `build_video_finder`) and `build_dish_service`, which calls them. They read the settings once and return the concrete classes or `None`. Callers (the app factory, tests, the research runners) never write their own `if provider == ...` chain. A new provider is one class that satisfies the role plus one line in the matching `build_*` function (OCP).

## Consequences

- One place decides what runs in which configuration; the configuration table in `server/README.md` maps to these functions.
- Tests of the factory (`tests/dishes/test_composition.py`) pin the degradation rules: no keys, model key only, YouTube key only, bad data file stops the server at startup.

## Not now

- No registry or plugin loading by name: with one provider a registry would hide a likely change that does not exist yet.
- No `Abstract Factory` for "families" of parts: model, video and recipe parts are chosen independently.
- The vision providers (`app/vision`) keep their own small selection in `app/main.py`; moving it is separate cleanup.
