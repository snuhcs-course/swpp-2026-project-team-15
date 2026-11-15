> Historical implementation-stage record. Counts, filenames and contract notes
> below describe past executions. See [README.md](README.md) for current tests,
> policy boundaries and the old-to-current filename map.

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
- preserve an empty-title error and continue to a same-category candidate without new replacement links;
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

## Verification record: 2026-11-14

- Locked offline sync: 25 packages resolved, 23 checked; no lockfile changes.
- Integration cases above: **2 passed in 643.57s**.
- Existing combined Pixabay/Stage 1–5 regression: **245 passed in 450.59s**.
- Final discovery: **247 tests**; all were executed across these two groups,
  with no skips or xfails. To avoid repeating the expensive integration cases,
  the second invocation used the following explicit partition:

```powershell
uv run --locked --offline pytest -q --tb=short -p no:cacheprovider --ignore=crawlers/tenkrecipes/tests/test_stage6_pipeline.py --basetemp=../output/stage6-locked-regression
```

The integration invocation used the explicit test path above with
`--tb=short -p no:cacheprovider --basetemp=../output/stage6-integration`.
This is partitioned verification, not a claim that one pytest invocation ran
all 247 cases. Ruff check and format check passed for all 49 crawler Python files.
OpenSpec strict and Git whitespace/scope checks passed. Windows sandbox access
to the uv cache lock and test temporary directories required normal permissions;
all package operations remained offline. Source acquisition code, dependencies,
DB schema, and production datasets were unchanged in Stage 6.
