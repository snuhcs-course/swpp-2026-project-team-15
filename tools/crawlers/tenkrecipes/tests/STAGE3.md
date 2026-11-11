# Stage 3 test-first contracts

These tests cover implemented tasks 3.1–3.5: fetching, storage, resume, and live
command gates. They were written RED first; no skip, xfail, stub production module,
or live source access is used. Existing stages 1–2 and Pixabay tests remain required.

## Inputs and isolation

`stage3_support.py` supplies a queued callable transport, synthetic response
objects, and a virtual monotonic/UTC clock. The clock advances only when asked;
tests do not wait in real time. The helper does not implement retries, pacing,
parsing, storage, or resume. The existing stage 2 list/detail fixtures are reused.
All response content and dates are synthetic. No site, image,
robots, or terms document is fetched by these tests.

Existing autouse socket guards and CLI subprocess audit hooks remain enabled.
Storage tests use disposable run paths. Live opt-in in an in-process test only
enables the fake transport, never an HTTP session. Actual live collection remains
a separate operator action after implementation and source-use review.

## Implemented interface

The implementation follows this test-first interface. Operator usage and saved
artifact details are documented in [RUNS.md](../RUNS.md).

### `crawlers.tenkrecipes.fetching`

`HttpClient(transport, sleep, monotonic, utcnow, live,
max_wait, run_budget)` exposes `get(url)`.

- Transport is callable `(url, *, timeout, headers)` and returns a response with
  `status_code`, `content`, `headers`, `url`, and `text`. It can raise requests
  timeout/connection exceptions. A default real transport is not used in tests.
- `sleep(seconds)`, `monotonic()`, and timezone-aware `utcnow()` are injectable.
- Missing live opt-in raises `NetworkDisabled` before transport access.
  `--live` is the only required execution opt-in; no source-use review file or
  record is required, validated, or passed to the client in this contract.
- Requests use 10/30-second connect/read timeouts, an identifying User-Agent,
  at least two seconds between starts, and at most three total attempts per GET.
  Transient 503, transport failures, and 429 are covered. Nonretryable 404 fails
  once. Retry-After seconds and HTTP dates are respected. No specific exponential
  backoff, jitter, or extra retryable status policy is invented by these tests.
- Test-selected budgets are `max_wait=60` and `run_budget=120`; these are injected
  test values, not new mandatory production defaults.
- Returns `status` (`ok`, `failed`, `blocked`, `deferred`), successful `body`
  bytes, and `attempts`. Tested reason codes are `retry_exhausted`, `http_error`,
  `access_denied`, `challenge`, `wait_budget_exceeded`, `run_budget_exceeded`.
- Response attempt metadata includes `source_url`, `final_url`, ISO `fetched_at`,
  `status_code`, and SHA-256 `sha256`. Transport failures must remain recorded,
  with response-only fields absent/null as appropriate. Cookies and secrets in
  exception strings must not appear in attempts or printed diagnostics.
- 401/403 and a synthetic challenge form stop without retries or identity
  rotation. Tests demonstrate a recognizable challenge, not exhaustive detection
  of every future challenge page. There is no bypass behavior.

### `crawlers.tenkrecipes.workflow`

`CollectionRun.create(plan, client, parser_version, schema_version,
utcnow)` initializes an independent run directory.
`CollectionRun.resume(...)` takes the same arguments and validates the saved run
before requesting anything or changing existing artifacts.

- `fetch_list(category_code, page)` fetches/saves/parses a list or reuses its
  previously saved snapshot. Successful results follow the stage 2 list format.
- `fetch_detail(source_id)` saves raw details and parsed JSON, returning
  `status: parsed` with `record`. It does not fetch image URLs.
- `resume_pending()` processes recorded candidates in source order, reuses
  completed details, and does not discover new pages. The caller can request new
  pages after pending work is drained. Automatic quota traversal is stage 5.
- `snapshot()` returns the current manifest: `state`, `network_policy`, `lists`,
  ordered `candidates`, and cumulative `attempts`. Extra fields are allowed.
  List entries expose relative `path`, `category_code`, `page`, `source_url`,
  `final_url`, `fetched_at`, `sha256`. Candidate observations expose source ID,
  category, page, and position; observations are not semantic deduplication.
- `run.json` records plan, parser/schema versions, run identity, and start time.
  The manifest records effective network policy including budgets.
  Source-use notes are optional operator records, not required run inputs.
- Raw list HTML lives under `lists/`, detail bytes under `details/<id>.html`,
  parsed records under `recipes/<id>.json`. Existing snapshots are immutable.
- Atomic raw/parsed/manifest publication uses a temporary file followed by `os.replace`.
  Injected replacement failures must leave the previous manifest readable and
  byte-identical, without publishing the interrupted target. The tests do not
  prescribe temporary filenames or claim
  filesystem power-loss guarantees beyond atomic replacement.
- Configuration/parser/schema drift raises `ResumeMismatch` without mutation or
  network; saved-source hash mismatch raises `IntegrityError` without overwrite.
  A missing parsed JSON output is recovered from valid saved detail HTML without
  refetching that source; other pending details are fetched normally.
- Denial/challenge yields blocked; filter/selector loss yields blocked with
  `structure_mismatch`; excessive wait yields deferred. Prior candidates/raw
  pages and attempt history remain. Failed response bodies are saved separately
  under `lists/` without being treated as successful parsed lists.

The tests do not require downloading images, validating quota completion, semantic
duplicate review, DB import, or recovery of every possible orphaned-file layout.
Those are separate stages or require additional specified scenarios.

### CLI and operator documentation

Commands: `collect --output-dir DIR --live`
and `resume --output-dir DIR --live`. Help works offline;
missing live opt-in fails before networking or run creation. Tests never
invoke a fully enabled real live command.

Task 3.5 also needs human review of future operator documentation: immutable cache
reuse, interrupted writes, blocked/deferred states, version mismatch, saved
optional source-use notes, pre-run source-use checks, and exact collect/resume examples. CLI help/gate tests verify
only the executable boundary, not the truth of prose or actual source-use rights.
The operator guide now describes these procedures; no live command was executed
as part of implementation or verification.

## Run

| Task area | Cases |
|---|---:|
| GET policy and live guards (3.1/3.2) | 17 |
| Saved snapshots, interruption, and resume (3.2–3.4) | 22 |
| CLI gates and offline help (3.2/3.5) | 4 |
| Total | 43 |

From `tools/`:

```powershell
uv run --locked pytest crawlers/tenkrecipes/tests/test_stage3_fetching.py crawlers/tenkrecipes/tests/test_stage3_storage_resume.py crawlers/tenkrecipes/tests/test_stage3_cli.py -q
```

Four implementation-time regressions address clear
resume defects: a raw list published before interrupted checkpoint replacement
must be recovered, and a deferred Retry-After deadline must survive restart.
The third ensures a failed pending detail stops processing instead of having its
failure status overwritten by a later successful candidate. The fourth reproduces
an exhausted final 429 attempt losing its Retry-After deadline across resume;
it failed before the fix and passed afterward. No other implementation-time
tests were added.
