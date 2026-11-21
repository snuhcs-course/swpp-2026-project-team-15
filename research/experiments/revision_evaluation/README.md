# Revision Evaluation Artifact Contract

This package freezes the complete Runner artifact contract before live execution code is added.
The public v1 boundary is [`schema.json`](schema.json) plus the self-contained
[`fixtures/contract-v1`](fixtures/contract-v1) bundle. A consumer does not need to import this
package or the future Runner.

## Artifact files

Each run directory contains:

```text
metadata.json
observations/<case-id>__rNN/attempt-NNN.json
summary.json
summary.md                         # optional human projection; JSON is authoritative
```

The fixture bundle omits only `summary.md`. Its `metadata.json` and `summary.json` contain relative
references to every observation. All paths are resolved relative to the run directory.

Schema IDs are explicit and unsupported values must be rejected:

- `revision-evaluation-metadata/v1`
- `revision-evaluation-observation/v1`
- `revision-evaluation-summary/v1`

## Observation fields

An observation identifies `run_id`, `case_id`, one-based `repetition`, and one-based
`execution_attempt`. The major sections are:

- `input`: supplied ingredient names, the immutable source recipe, computed availability, and the
  exact ordered and deduplicated `effective_assumed_staples` used for the run.
- `execution`: attempt state, checkpoint revision/stage, terminal outcome and source, final service
  response, or sanitized failure. Incomplete attempts have no terminal outcome.
- `model_calls`: ordered initial/re-ask calls, complete request content and hash, parsing result,
  decoded answer, and ordered HTTP attempts.
- `checks`: production check events. These are separate from parsing and deterministic findings.
- `deterministic_evaluation`: parsed-response structure/reference findings and explicit coverage
  numerator/denominator.
- `telemetry`: calls, 429 responses and actual retries, provider time, Revision time, checkpoint
  overhead, tokens and cost.

Run metadata also freezes code/working-tree identity and prompt, response-schema, input, and
fixture hashes. Each plan unit carries cumulative telemetry across all of its execution attempts,
including attempts superseded by resume. A completed plan unit's `selected_completed_attempt`
must identify exactly one completed observation for the same case and repetition.

Terminal outcomes are `unchanged`, `revised`, `refused`, `check_failed`, `response_error`, and
`api_error`. `outcome_source` independently identifies `no_change`, `prescreen`, `model`,
`production_check`, `response`, or `transport`.

## Checkpoints and HTTP budget

Every HTTP attempt is saved as `request_prepared` before sending. Such a record has unknown
delivery, usage, and cost but always has `counts_against_budget: true`. A prepared request consumes
one HTTP-attempt budget unit even if the process stops before a response is recorded. Resume keeps
that attempt unchanged and starts a new execution-attempt number.

`checkpoint_revision`, `repetition`, execution attempts, logical calls, and per-call HTTP attempts
are one-based. HTTP attempts are contiguous within each logical call. Completed executions use the
`terminal` checkpoint stage; incomplete executions never receive a fabricated terminal outcome.

## Null, zero, and applicability

Numeric measurements that may not exist use both `applicability` and `value`:

- `{"applicability": "value", "value": 0}` is a measured zero.
- `{"applicability": "unavailable", "value": null}` means the value could not be observed.
- `{"applicability": "not_applicable", "value": null}` means the metric does not apply.

Rates always retain numerator and denominator. A zero denominator has a null rate; it is not
reported as zero or one.

Costs additionally use `provenance`: `measured` for provider-supplied cost, `estimated` only with
the retained price inputs, `missing` when cost cannot be established, and `not_applicable` for a
zero-call path. Aggregate token categories and costs retain a `confirmed_subtotal` even when their
complete value is unavailable; zero-call aggregates are `not_applicable`, not missing. Summary
latency publishes p50/p95 with sample counts and its incomplete-attempt
policy. The summary also retains initial/final failure-code counts, per-case planned/completed
repetitions and outcome distributions. Semantic success is explicitly `not_applicable` until a
run names a versioned success definition.

## Markdown summary projection

`reporting.render_summary(RunSummary.model_validate_json(summary_json))` returns
deterministic Markdown for `summary.md`. It consumes only authoritative summary
JSON, performs no aggregation, rescoring, model calls or file writes, and does not
read metadata or observation files. The future Runner owns output publication.
The fixture bundle remains unchanged; a fixed fixture rendering is regression-tested
by its UTF-8 digest. Displayed numbers use up to 12 significant digits; JSON retains
the original precision.

The report preserves independent metric numerators/denominators, percentile sample
counts and incomplete-attempt policies, outcome distributions, repeat completion,
token/cost applicability, confirmed subtotals, provenance and estimate price inputs.
Missing measurements remain unavailable, while N/A and measured zero stay distinct.
An operational completion or valid JSON answer is not evidence of semantic quality.

Revision latency excludes measured checkpoint persistence; observed wall time includes
it. Checkpoint overhead covers the measured Revision-call window, not all setup or
final publication I/O. The non-HTTP remainder can include retry waits and unobserved
work and must not be interpreted as pure application processing. A prepared request
may have reached the provider without a durable response, so unknown in-flight usage
and cost are not zero or assumed free. Confirmed subtotals are not complete totals.

## Judge boundary

Runner artifacts deliberately preserve the complete source recipe, requests, responses, checks,
and telemetry. They contain no Judge prompt, score, latency, token, or cost fields. The Judge branch
owns selection of rubric-relevant fields and construction of its minimized model payload. It should
store the source observation identity so a Judge result remains auditable.

## Regeneration and validation

### Offline command entry point

From the repository root in PowerShell, using the existing server environment:

```powershell
$env:PYTHONPATH = "$PWD\server;$PWD\research"
.\server\.venv\Scripts\python.exe -m experiments.revision_evaluation
.\server\.venv\Scripts\python.exe -m experiments.revision_evaluation --cases R02a R01a --repetitions 3
.\server\.venv\Scripts\python.exe -m experiments.revision_evaluation --validate-fixtures
```

Default invocation validates the committed contract bundle and prints a dry-run plan
for all 36 frozen cases with one repetition each. `--cases` retains explicit input
order. `--manifest` and `--recipes` accept alternate local schema-1 files; invalid,
duplicate or unknown selections fail instead of silently filtering the manifest.
`--fixture-root` selects a local contract bundle. Validation-only mode does not load
the recipe/catalog configuration.

These commands send no HTTP requests, construct no model, read no API key and
create no run directory or artifacts. Printed bounds are conservative for a single
execution of each planned repetition: zero to two logical calls, each with at most
`1 + len(RETRY_WAITS)` HTTP attempts (currently three). They are not predictions or
an enforced spending budget, and do not include resumed attempts. No-call branches
and production time budgets can reduce the actual counts. Live execution is not
enabled in this implementation step and live opt-in options are rejected.

### Read-only resume compatibility check

`--resume <existing-run-directory>` checks compatibility only. It never constructs
a model, writes metadata, advances a checkpoint or resumes execution. A match
prints `mode: resume_compatibility_check`, `compatible: true` and
`execution_resumed: false`; a mismatch returns exit code 2 with a fixed diagnostic
and leaves the existing run untouched. Completed runs and unsupported artifact
versions are rejected. `--resume` and `--validate-fixtures` are mutually exclusive.

When `--cases`/`--repetitions` are omitted, the stored selection and repetition
count are used; explicit selections must match the original ordered plan. Current
manifest/recipe files and effective availability/staples configuration are still
recomputed. Stored model/pricing settings are retained as the requested settings
when no override is supplied (CLI model/pricing overrides belong to the live step).

The internal `revision-evaluation-compatibility/v1` fingerprint uses canonical
finite JSON and SHA-256. It covers artifact versions, ordered case/repetition
identities, per-case input snapshots, exact manifest/recipe bytes, production
prompt-module bytes (including re-ask wording), the canonical Revision response
schema, ordered effective staples, model settings, prices, code identity and the
maximum HTTP-attempt budget. Progress states, observation references, consumed
budget, timestamps and resume history are excluded; changing progress cannot reset
the original maximum. The check recomputes both the stored immutable settings and
the current configuration against the original fingerprint.

Code identity includes HEAD plus a Git-format digest of actual tracked and
nonignored untracked working files, so two dirty checkouts are not treated as the
same code. This is computed without updating the index or writing Git objects.
Raw working bytes are used without clean filters; line-ending conversion therefore
invalidates compatibility too. Keep run outputs ignored (as under `data/`) or
outside the source repository so outputs do not change code identity. Unmerged
entries, submodules, Git warnings and unreadable source files fail closed rather
than publishing a partial identity. No Git fetch or other network operation runs.

The committed contract fixtures use illustrative hashes, not a real Runner
fingerprint, and are not resumable runs. Actual continuation and attempt selection
remain later integration tasks; this boundary checks configuration compatibility,
not the consistency of every saved observation.

### Contract asset generation

From `research/`:

```powershell
..\server\.venv\Scripts\python.exe -m experiments.revision_evaluation.generate_contract
```

Generation is deterministic. Contract tests compare the generated in-memory values with every
committed JSON file and validate relative references, versions, outcome coverage, numbering,
applicability, and HTTP-attempt budget accounting. No network access is used.
