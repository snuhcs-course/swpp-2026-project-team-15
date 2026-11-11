# Stage 1 acceptance tests

These are test-first contracts for tasks 1.1–1.4 of
`collect-tenkrecipes-quick-recipes`. No crawler implementation is included.
Missing modules, dependencies, discovery configuration, and the tool README are
expected RED results, not skipped or xfailed tests. Stage 1 remains unfinished.

## Proposed public test interface

The planning documents specify behavior but do not fix Python symbol names or a
plan serialization format. These tests establish the following small interface
for the future implementation; no internal classes or parser algorithms are prescribed:

- From `tools/`, run `python -m crawlers.tenkrecipes.cli` and `--help` for help.
- `python -m crawlers.tenkrecipes.cli plan --output-dir <path>` writes a JSON plan
  to stdout. It does not need network access, credentials, or server imports.
- The plan has `total: 500`, `output_dir`, and ordered `categories` records with
  `name`, `cat4`, `quota`, and `list_url` (the first page with both filters and
  recommendation order). `cat4` can be an integer or string.
- `crawlers.tenkrecipes.config.build_plan(output_dir=Path(...))` exposes the same
  plan fields through deeply read-only mappings/sequences. Updating a nested
  quota or top-level total raises `TypeError`.
- Plan independence and immutability are separate contracts. The independence
  test builds plans with different output paths and verifies that creating or
  rebuilding one does not change the other's output or category configuration.
  It allows safe sharing of immutable category values. The immutability test
  separately verifies rejection of top-level and nested mutations of one plan.
  This keeps the current built-run-plan interface; no draft/finalize API is added.
- Output directories cannot be existing files or production source/data paths.
- The future `tools/crawlers/tenkrecipes/README.md` includes a single-line fenced
  example `python -m crawlers.tenkrecipes.cli plan --output-dir {output_dir}`.
  The test substitutes a disposable path and executes it. Documentation of setup,
  source-ID identity versus pending semantic review, and integration exclusions
  still needs human review; executable examples cannot verify all prose.

## Coverage

| Task | Automated checks |
|---|---|
| 1.1 | Offline import/help/plan, tools-only parser dependency, protected output paths |
| 1.2 | Agreed category order/quotas, total 500, request filters, plan independence, nested immutability, existing data preservation |
| 1.3 | Real pytest discovery using copied configuration and two synthetic test trees; legacy bare-module coexistence |
| 1.4 | Execution of the future README plan example |

The discovery probe uses tiny synthetic test trees so it measures pytest's
configuration without importing optional crawler dependencies. It does not claim
that the complete existing Pixabay suite passes. The dependency check inspects
declarations only; installing the lockfile is a separate integration check.

CLI tests run in disposable working directories. Audit hooks stop DNS/connect,
child processes, and file access to production server/Android/recipe data, including
attempts caught by the application. A guard self-test proves that caught attempts
still fail. In-process config tests also block networking. No live site is queried.

## Run

```powershell
cd tools
uv run --locked pytest crawlers/tenkrecipes/tests -q
uv run --locked pytest --collect-only -q
```

Until task 1.3 is implemented, the second command will omit the new tests because
the current default testpaths only includes Pixabay. Use the explicit path above
to execute this RED suite. Do not change test discovery or add implementation
stubs merely to make a tests-only request pass.
