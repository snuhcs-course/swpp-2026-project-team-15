# Revision Evaluation Artifact Contract

This package implements the research Runner against its frozen complete artifact contract.
The public v1 boundary is [`schema.json`](schema.json) plus the self-contained
[`fixtures/contract-v1`](fixtures/contract-v1) bundle. A consumer does not need to import this
package or the Runner implementation.

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
read metadata or observation files. `RunStore.write_summary(..., markdown=True)`
owns guarded output publication; CLI execution currently publishes JSON only.
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

From the repository root, preview the exact minimized payload for one eligible observation without
constructing a model or reading a credential:

```bash
PYTHONPATH=server:research uv run --project server --locked python \
  -m experiments.revision_evaluation.judge \
  research/experiments/revision_evaluation/fixtures/contract-v1/observations/revised-after-reask-429__r01/attempt-001.json
```

Add `--allow-live-api --model <model-id>` to make one logical Judge call through the existing
`DishLLM` client. After validating the observation, live mode automatically loads `server/.env`
using the module's location, regardless of the working directory. Existing environment variables
take precedence (`override=False`). Set `OPENROUTER_API_KEY` in that file or the process environment;
a missing file is allowed, but a missing or blank final key fails before model construction.
Offline preview does not load the file. Model selection uses `--model` or the existing default;
`DISH_LLM_MODEL` does not select the Judge model. This research command uses the server dev
environment, which already includes `python-dotenv`.

For example, with `OPENROUTER_API_KEY` already in `server/.env`, run from the repository root:

```bash
PYTHONPATH=server:research uv run --project server --locked python \
  -m experiments.revision_evaluation.judge \
  research/experiments/revision_evaluation/fixtures/contract-v1/observations/revised-after-reask-429__r01/attempt-001.json \
  --allow-live-api
```

This command can incur provider charges and sends the minimized recipe payload to the provider.
It prints one judgment linked to the exact source-byte hash, rubric, prompt and model, and does not
modify the observation or publish an aggregate pass/fail result. The client may retry HTTP attempts
inside that one logical call according to its existing policy.

## Regeneration and validation

### Offline command entry point

From the repository root, using the existing server environment:

```bash
PYTHONPATH=server:research uv run --project server --locked python -m experiments.revision_evaluation
PYTHONPATH=server:research uv run --project server --locked python \
  -m experiments.revision_evaluation --cases R02a R01a --repetitions 3
PYTHONPATH=server:research uv run --project server --locked python \
  -m experiments.revision_evaluation --validate-fixtures
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
and production time budgets can reduce the actual counts. Live execution requires
the separate explicit opt-in below.

### Live configuration and durable budget boundary

`--allow-live-api --max-http-attempts N` explicitly authorizes live execution
and requires a nonempty `OPENROUTER_API_KEY` environment variable. `N`
must be a positive integer. `--model` selects a production model ID; optional
`--input-per-million-usd` and `--output-per-million-usd` must be supplied together
as finite nonnegative values. Without prices, unavailable provider cost remains
missing rather than being invented as zero. No credential is printed.

The following commands can incur provider charges. Set the key in the process
environment beforehand; the runner does not discover or load `.env` files.

```bash
PYTHONPATH=server:research uv run --project server --locked python \
  -m experiments.revision_evaluation --allow-live-api --max-http-attempts 6 \
  --run-id revision-demo --cases R02a --repetitions 1
PYTHONPATH=server:research uv run --project server --locked python \
  -m experiments.revision_evaluation \
  --resume data/dish-revision-evaluation/revision-demo --allow-live-api
```

A new run writes beneath `--output-parent` (default: repository-relative
`data/dish-revision-evaluation`) using `--run-id` or a UTC timestamp-based ID.
Existing run directories are never reused for a start. Resume writes only within
the original run directory and rejects `--run-id`/`--output-parent` redirection.
Successful execution reports `live_start` or `live_resume`, the output directory,
`summary_ref: summary.json`, operational completion and outcome counts. The
`http_attempts_cumulative` field includes prior attempts and unknown delivery; it
is not the number of HTTP requests sent by this invocation. Metadata, observations
and authoritative JSON summary are persisted by the existing sequential runner.
Markdown publication is a separate reporting operation.

Completed plan units are skipped on resume. An incomplete attempt stays unchanged;
continuation creates the next attempt number and retains its predecessor's usage,
including confirmed subtotals when complete usage/cost is unavailable. A request
whose response never reached durable storage retains unknown delivery/cost rather
than an invented zero. API/response errors are persisted outcomes and do not stop
later repetitions. Exit code 0 indicates operational completion, not semantic
recipe quality; configuration/storage/budget failures return 2, interruption 130.
Failure diagnostics are fixed messages without raw exception details.

The research `live.make_live_model` factory separately assembles an explicitly
authorized production model with a fresh logical-call recorder and a
`BudgetedRunStore`. The store requires the original metadata before any attempt;
every pre-send checkpoint checks the immutable run cap before delegating to atomic
storage. Scanning includes observations not yet indexed by lagging metadata, so
unknown delivery consumes a unit and cannot become a new resume allowance.
Response checkpoint replacement does not count an identity twice. Earlier usage
and confirmed cost/token subtotals remain retained. A budget or storage failure
escapes as the existing operational `CheckpointError`, stopping before a send,
retry or re-ask. Budget scanning stays inside the checkpointer's persistence timing
interval, excluded from production policy time. This is a sequential boundary,
not a concurrent reservation mechanism.

### Read-only resume compatibility check

Without `--allow-live-api`, `--resume <existing-run-directory>` checks compatibility
only. It never constructs a model, writes metadata, advances a checkpoint or
resumes execution. A match
prints `mode: resume_compatibility_check`, `compatible: true` and
`execution_resumed: false`; a mismatch returns exit code 2 with a fixed diagnostic
and leaves the existing run untouched. Completed runs and unsupported artifact
versions are rejected. `--resume` and `--validate-fixtures` are mutually exclusive.

When `--cases`/`--repetitions` are omitted, the stored selection and repetition
count are used; explicit selections must match the original ordered plan. Current
manifest/recipe files and effective availability/staples configuration are still
recomputed. Stored model/pricing settings are retained as the requested settings
when no override is supplied. Explicit model/pricing overrides must still match
the original fingerprint. A supplied `--max-http-attempts` must equal the original
maximum; live resume recomputes consumption from durable observations
and rejects an exhausted budget without modifying the run when unfinished plan
units remain. If every observation is already completed and only run finalization
was interrupted, opt-in resume can finalize at zero remaining budget without
constructing a model/transport or sending a request. The runner reconciles durable
observations even when the metadata index lags behind them; the cap is never reset.

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
fingerprint, and are not resumable runs. The read-only compatibility command checks
configuration compatibility, not the consistency of every saved observation.
Opt-in execution additionally delegates durable observation validation and attempt
selection to `run_resume()`. Mock-run and offline-rescore CLI commands are not yet
implemented as dedicated options; use the existing test/API commands below instead.

### Mock execution without live access

From the repository root, run the end-to-end CLI tests with disposable local Git
inputs and `httpx.MockTransport`:

```bash
uv run --project server --locked python -m pytest \
  server/tests/experiments/revision_evaluation/test_cli_execution.py \
  -q -p no:cacheprovider
```

These tests replace only the HTTP transport and source/configuration location;
the real runner, Revision, checkpoints, budgeting and persistence execute. They
exercise interruption/resume, immutable earlier attempts, cumulative usage/cost,
budget exhaustion, changed-source rejection and existing-directory protection.
Real sockets/DNS are blocked and the key is synthetic. Artifacts are temporary
pytest data, not a new run in the repository. Passing mocks establish execution
and artifact behavior, not culinary quality or live provider compatibility.

### Offline deterministic rescore preview

This Bash command prints a fresh JSON
summary using the current deterministic evaluator and the stored raw observations.
It does not construct a model, read an API key, run production checks or invoke a
Judge. The committed bundle provides a reproducible example:

```bash
PYTHONPATH=server:research uv run --project server --locked python - \
  research/experiments/revision_evaluation/fixtures/contract-v1 <<'PY'
import json
import sys
from pathlib import Path

from experiments.revision_evaluation.contract import validate_fixture_bundle
from experiments.revision_evaluation.evaluation import evaluate_observation
from experiments.revision_evaluation.summary import summarize_run

metadata, observations, stored = validate_fixture_bundle(Path(sys.argv[1]))
refs = list(dict.fromkeys(stored.observation_refs))
rescored = {
    ref: evaluate_observation(observation)
    for ref, observation in zip(refs, observations, strict=True)
}
summary = summarize_run(metadata, rescored, generated_at=stored.generated_at)
print(json.dumps(summary.model_dump(by_alias=True), ensure_ascii=True, indent=2))
PY
```

Replace the final path with an existing self-contained run directory containing
metadata, every referenced observation and a matching summary. This validates the
stored bundle, recomputes parsing/structure/reference/coverage findings on copies,
and aggregates without replacing any file. Production outcomes, check decisions,
requests, decoded answers, timing and usage remain historical evidence. All
retained attempts contribute cumulative metrics, not only completed attempts.
An index lagging behind durable checkpoints must first be reconciled by compatible
resume; this preview does not discover, repair or silently discard orphan files.

The preview reuses the stored generation timestamp for deterministic output; it
does not claim a new execution or change the stored provenance. If evaluator code
has changed, keep the current code identity alongside any separately saved preview
for interpretation. It neither overwrites authoritative `summary.json` nor bypasses
completed-attempt immutability. For Markdown display, the existing pure
`reporting.render_summary(summary)` can project that returned summary without
rescoring it again. Unknown in-flight usage/cost stays unknown; only a previously
recorded confirmed subtotal is retained.

### Contract asset generation

From the repository root:

```bash
PYTHONPATH=server:research uv run --project server --locked python \
  -m experiments.revision_evaluation.generate_contract
```

Generation is deterministic. Contract tests compare the generated in-memory values with every
committed JSON file and validate relative references, versions, outcome coverage, numbering,
applicability, and HTTP-attempt budget accounting. No network access is used.
