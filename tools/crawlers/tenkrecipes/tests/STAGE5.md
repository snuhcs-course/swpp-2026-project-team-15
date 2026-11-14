# Stage 5 test-first contracts

These offline acceptance tests verify implemented tasks 5.1–5.5. Allocation and
reports use the same candidate error policy as the one-page pilot. No skip/xfail,
stub production module, or live requests are used. Operator procedures for 5.6
are in [RUNS.md](../RUNS.md) and still require human operational review.

## Implemented interface

The specification defines behavior, not Python names or report serialization.
The implementation follows these interfaces originally proposed by the tests.

- `CollectionRun.collect_quotas()` traverses the saved plan in category order,
  using recorded work before unseen pages. It returns `status` and
  `acquisition_complete`. Incomplete collection returns `incomplete`; global
  access/structure barriers return `blocked`, and retry-budget interruption
  returns `deferred`. It records `allocations`, `failures`, `replacements`, and
  `category_outcomes` in the manifest. Existing single-page methods remain usable.
- Allocation rows expose `source_id` and `category_code`. Failure rows expose
  those fields plus `reason`. Replacement rows expose `failed_source_id`,
  `replacement_source_id`, and `category_code`. Category outcomes expose
  `category_code`, `reason`, and `deficit`; tested traversal reasons are
  `exhausted` and `repeated_page`. Additional diagnostic fields are allowed.
- `crawlers.tenkrecipes.reporting.validate_run(root)` reads existing local
  artifacts and returns a report without changing files or requiring live opt-in.
- `write_report(root)` returns that report and writes `report.json` and
  `review.csv`. Repeating it against unchanged inputs preserves the result.
- The report exposes `status` (`complete`/`incomplete`),
  `acquisition_complete`, `target`, `unique_success_count`, ordered `categories`
  with `category_code`/`target`/`selected`/`deficit`, `errors`, `failures`,
  `replacements`, and `findings`. Failure/replacement records retain the
  manifest's causal links separately from quality findings.
  Findings expose `source_id`, `code`, `status: review_pending`, and original
  `observations` when applicable. `tools_not_listed` is a proposed reporting code
  for `listed_tools: null`, not an instruction to change parser output.
- `review_status: review_pending`, `count_basis: source_id`,
  `semantic_duplicate_review: {status: pending, required_before_production: true}`,
  and `semantic_uniqueness_guaranteed: false` distinguish acquisition from review.
  The report must not assert production readiness. Different IDs and identical
  content deliberately remain separate originals.
- CSV rows expose `source_id`, `code`, `source_url`, `raw_path`, `record_path`,
  and `image_path`; title mismatch rows expose both original observations in a
  JSON-encoded `observations` cell. This supports commas and non-ASCII content
  without losing representation identities or URLs.
- CLI `validate --output-dir DIR` and `report --output-dir DIR` emit report JSON
  offline, return exit code 1 for incomplete acquisition, and need no `--live`.
  Only `report` writes report files. Existing subprocess isolation remains active.

## Coverage and fixture boundaries

`stage5_support.py` supplies URL-routed synthetic HTML/image transports using
the real parser, HTTP policy, workflow and image downloader. It does not perform
allocation, candidate eligibility, page traversal, replacement or reporting.
Tests retain the approved nine quotas; no miniature production plan or new
recipe filtering criteria are introduced. The virtual budget is enlarged only
to avoid incidental timeout while exercising deterministic fake requests.

Allocation cases cover source order, duplicate observations, first successful
category allocation, same-title variants, same-category replacements, empty
content, image failures, exhaustion, repeated pagination, global stop conditions,
and reuse of saved work across resume. Overshoot candidates stay in observations.

Report inputs are explicitly saved synthetic manifests containing 500 declared
allocations, with local original HTML, structured records, and decoded PNGs.
They are inputs to the validator, not outputs from a substitute collection
algorithm. All records intentionally have identical recipe/image content.
Negative cases change one count, allocation, essential field, or artifact.
Corrupt-image bytes have a matching updated hash to require real decoding rather
than trust an `image_validated` label. The full fake-transport 500-item collection
and integrated CLI collection path remain stage 6 work.

The parser now distinguishes an empty title (`MissingTitleError`) from missing
DOM structure. Collection preserves an empty-title failure and proceeds through
recorded same-category candidates. Raw HTML is retained; a parsed JSON is not
required when parsing fails. Quota traversal uses this same classification,
retains all observed cards, and connects same-category replacement relations.

## Operator documentation requires human review (5.6)

No keyword-count test can establish that operational instructions are correct.
Implementation must document source-use/robots/terms checks, a small live pilot,
the approved nine quotas, full collection/resume, exhaustion and anomaly handling,
artifact/report locations, explicit `--live` examples, and review handoff. It must
state that source-ID uniqueness does not establish semantic uniqueness and that
semantic duplicate review is mandatory before production. Source-use notes remain
optional; no source-use-review execution gate may return. Service import and
deployment remain excluded. Live execution requires a separate user request.

## Run

From `tools/`:

```powershell
uv run --locked pytest crawlers/tenkrecipes/tests/test_stage5_allocation.py crawlers/tenkrecipes/tests/test_stage5_reports.py -q
```

The original 29 tests now pass, alongside Pixabay and stages 1–4. Three additional
confirmed implementation defects are covered by `test_stage5_regressions.py`:
missing selected JSON/image files must be repaired even in an exhausted category,
and a recovered blocked recipe must not be recorded as replacing itself. All
three failed before their fixes. No other stage 5 implementation-time tests were
added. Full 500-recipe fake-transport pipeline integration remains stage 6 work.
