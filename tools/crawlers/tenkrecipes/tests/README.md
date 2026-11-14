# Stage 1 acceptance tests

Stage 2 test-first contracts and synthetic fixture provenance are documented
separately in [STAGE2.md](STAGE2.md). Stage 2 parsing is now implemented and those
cases must pass; stage 1 remains independently testable.

Stage 3 tests and their implemented interfaces are documented in [STAGE3.md](STAGE3.md).
They were written test-first and now verify fetching/storage/resume with fake I/O.

Stage 4 thumbnail acceptance cases are documented in [STAGE4.md](STAGE4.md).

[test_error_policy.py](test_error_policy.py) covers the approved empty-title,
operator-stop, three-recipe network-failure, reset, and resume policies. The
pilot and full quota CLI apply these policies.

Additional confirmed resume defects are covered by
[test_resume_consistency.py](test_resume_consistency.py): interrupted failure
checkpoints, retry deadlines during local recovery, retry-response references,
and consistent states across repeated source observations. These ten cases were
each observed failing before their respective fixes.

Stage 5 allocation/report tests and implemented interfaces are documented in
[STAGE5.md](STAGE5.md). The original 29 cases pass; implementation-time regression
tests are limited to four reproduced resume/replacement defects.

Stage 6 full synthetic pipeline checks and locked-environment commands are
documented in [STAGE6.md](STAGE6.md). They collect 500/499 records through the real
workflow, interrupt and resume an unfinished asset, and verify offline reports.

These are acceptance contracts for tasks 1.1–1.4 of
`collect-tenkrecipes-quick-recipes`. Stage 1 covers offline plan generation;
later stages cover collection and reporting. The initial test-only run was RED because
the CLI, configuration, dependency, discovery setup, and tool README did not yet
exist. Missing behavior is never hidden behind skipped or xfailed tests.

## Public test interface

The approved 2026-11-15 policy treats missing detail structure as a preserved
candidate failure, while list structure and access barriers still stop the run.
`test_detail_structure_failures.py` covers replacement, unchanged network-failure
streaks, raw preservation, and deferred conversion of older blocked snapshots
without re-fetching or losing their failure/replacement relationship. The two
earlier direct-detail expectations and the global-stop list fixture were updated
only for this explicitly approved policy change. No live collection is needed.

`test_category_quota.py` covers the subsequently approved `--only-category`
extension: stop at 100 then 90 in one run, preserve global ID identity, remember
the scope, reject conflicting/invalid scopes before I/O, retain ordered category
priority, and distinguish category exit success from global incompleteness.
The 16 acceptance cases were first run RED without changing earlier tests.
One additional confirmed preflight regression checks that a rejected later
category leaves a pending failure checkpoint and the published manifest intact;
it failed before moving scope validation ahead of resume recovery writes.

The planning documents specify behavior but do not fix Python symbol names or a
plan serialization format. These tests establish the following small interface
for the implementation; no internal classes or parser algorithms are prescribed:

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
- The `tools/crawlers/tenkrecipes/README.md` includes a single-line fenced
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
| 1.4 | Execution of the README plan example |

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

The default testpaths now includes both crawlers. The explicit path runs only
the tenkrecipes contracts; the second command checks the combined discovery.
