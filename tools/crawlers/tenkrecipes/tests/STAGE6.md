# Stage 6 integration and isolation

`test_stage6_pipeline.py` exercises task 6.1 with synthetic HTML and locally
generated PNG bytes. It uses the real plan CLI, parser, request policy, storage,
quota allocation, resume, validation CLI, and report CLI. Only the HTML/image
transports and clock are injected; no completed manifest or parsed recipe is
provided to the collector. The existing test network guards remain active.

Two cases cover exact completion (500 source IDs with all nine approved quotas)
and exhaustion of the last category (499 IDs, a deficit of one). Both cases:

- traverse multiple pages, preserving duplicate observations without duplicate
  detail/image requests or cross-category quota inflation;
- preserve an empty-title failure and its same-category replacement;
- interrupt the 206th thumbnail with `KeyboardInterrupt`, reopen the saved run,
  and reuse earlier source responses, parsed records, images, and allocations;
- check retained artifact hashes and independently generated JSON/CSV reports;
- retain identical content under different source IDs and keep semantic duplicate
  review pending and mandatory before production adoption;
- resume once more without any additional transport requests or report drift.

These are approved end-to-end acceptance checks for Stage 6, not additional
implementation-driven feature rules. Existing Stage 1–5 expectations are unchanged.
They establish compatibility with synthetic source structure, not the current
live site, actual data availability, source-use permission, or service readiness.

From `tools/`, run the focused integration cases with:

```powershell
uv run --locked --offline pytest crawlers/tenkrecipes/tests/test_stage6_pipeline.py -q
```

Run the final combined checks with:

```powershell
uv sync --locked --offline
uv run --locked --offline pytest
uv run --locked --offline ruff check crawlers
uv run --locked --offline ruff format --check crawlers
```

`--offline` restricts uv to installed packages/local cache; it does not disable
application networking. Tenkrecipes tests block socket DNS/connect, offline CLI
subprocesses have an audit guard, and Pixabay search tests inject fake sessions.
The full suite must pass without live requests. Windows file tests may need a
writable workspace `--basetemp` and normal file permissions. No live collection,
database import, service-data update, or deployment is part of these checks.
