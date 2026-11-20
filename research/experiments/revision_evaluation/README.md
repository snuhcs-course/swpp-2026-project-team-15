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
including attempts superseded by resume.

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

## Judge boundary

Runner artifacts deliberately preserve the complete source recipe, requests, responses, checks,
and telemetry. They contain no Judge prompt, score, latency, token, or cost fields. The Judge branch
owns selection of rubric-relevant fields and construction of its minimized model payload. It should
store the source observation identity so a Judge result remains auditable.

## Regeneration and validation

From `research/`:

```powershell
..\server\.venv\Scripts\python.exe -m experiments.revision_evaluation.generate_contract
```

Generation is deterministic. Contract tests compare the generated in-memory values with every
committed JSON file and validate relative references, versions, outcome coverage, numbering,
applicability, and HTTP-attempt budget accounting. No network access is used.
