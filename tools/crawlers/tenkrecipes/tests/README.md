# Recipe collection tests

Tests are organized by current responsibility, not implementation stage. All
ordinary tests use synthetic HTML, generated images and fake transports. Socket
access is blocked by conftest.py. No live collection is needed.

## Layout

| Area | Tests |
|---|---|
| Plan, quotas, preview paths, environment isolation | test_plan_contract.py |
| DOM/JSON-LD extraction and source preservation | test_list_parsing.py, test_detail_parsing.py |
| CLI argument/output boundaries | test_parse_cli.py, test_live_cli.py, test_category_quota.py |
| HTTP pacing, finite retries and response evidence | test_http_client.py |
| Atomic source storage and interrupted recovery | test_source_storage_resume.py, test_resume_consistency.py |
| Thumbnail bounds, bytes, provenance and recovery | test_images.py |
| Content errors, network streaks and operator stops | test_error_policy.py, test_detail_structure_failures.py |
| 429 deadlines across restart | test_rate_limit_resume.py |
| Candidate errors through pilot and quota workflows | test_simple_candidate_errors.py |
| Category allocation, exhaustion and historical selections | test_allocation.py, test_allocation_resume.py |
| Completeness, review findings and legacy CSV statuses | test_reporting.py, test_review_csv_status.py |
| Explicit low-level compatibility APIs | test_legacy_api.py |
| Full 500-ID pipeline and small exhausted-category pipeline | test_pipeline.py |

support_http.py provides the fake clock, queued responses and requests.
support_images.py provides generated image bytes, streams and downloader setup.
support_runs.py provides source fixtures and run constructors. Test modules do
not import other test modules for helpers. Fixtures list.html and detail.html are
hand-authored synthetic source structures, not downloaded material.

## Current policy boundaries

The CLI and quota/pilot candidate workflows skip terminal candidate errors and
log them once. 429 deadlines and run budgets pause collection. Denial/challenge,
list errors, disallowed image hosts/redirect limits and three consecutive recipe
network failures keep their stop behavior. Success resets the outage streak;
content errors do not. New A-to-B replacement links are not generated. Compatible
historical links and original evidence remain preserved.

The legacy detail-only resume_pending() and direct fetch_thumbnail() APIs have
different retry/stop boundaries. Their tests live in test_legacy_api.py and do not
define the CLI's terminal-candidate policy. These APIs have not been removed.

Parser tests preserve blank source rows and findings. Acquisition tests exclude
recipes without essential content. These are different contracts. Likewise,
plan independence and immutability, downloader validation and operator stops,
and source-ID uniqueness and pending semantic review are separate checks.

The complete pipeline collects 500 IDs through real parsing/storage/allocation,
interrupts and resumes acquisition, and checks CLI reports and stable repeated
resume. The former second 499-ID acquisition is replaced by a small real
exhaustion/report/resume pipeline. Exactly 499 IDs and exit 1 remain covered in
test_reporting.py. This preserves exhaustion coverage without collecting another
499 near-identical synthetic recipes.

## Run

From tools/:

```powershell
uv run --locked --offline pytest -q -p no:cacheprovider
uv run --locked --offline pytest crawlers/tenkrecipes/tests -q
uv run --locked --offline pytest crawlers/tenkrecipes/tests/test_pipeline.py -q
uv run --locked --offline ruff check crawlers
uv run --locked --offline ruff format --check crawlers
```

Use a fresh workspace --basetemp when Windows temporary-directory access is
restricted. Do not inspect working checkpoints while tests replace them. Report
any PermissionError and its rerun separately; do not mask it with automatic test
retries, skips or weakened assertions.

## Historical stage records

STAGE2.md through STAGE6.md retain dated test-first and verification history.
Their counts, old filenames and interfaces describe those historical executions,
not the current discovery count or authoritative current behavior. Use this
README, the source tests and the approved specification for current contracts.

| Earlier name | Current name |
|---|---|
| test_stage1_contract.py | test_plan_contract.py |
| test_stage2_lists.py / test_stage2_details.py | test_list_parsing.py / test_detail_parsing.py |
| test_stage2_parse_cli.py / test_stage3_cli.py | test_parse_cli.py / test_live_cli.py |
| test_stage3_fetching.py | test_http_client.py |
| test_stage3_storage_resume.py | test_source_storage_resume.py and test_legacy_api.py |
| test_stage4_images.py | test_images.py, test_legacy_api.py and support_images.py |
| test_stage5_allocation.py / test_stage5_regressions.py | test_allocation.py / test_allocation_resume.py |
| test_stage5_reports.py / test_stage6_pipeline.py | test_reporting.py / test_pipeline.py |
| stage3_support.py / stage5_support.py | support_http.py / support_runs.py |
