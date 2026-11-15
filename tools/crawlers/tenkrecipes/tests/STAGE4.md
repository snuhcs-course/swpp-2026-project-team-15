> Historical implementation-stage record. Counts, filenames and contract notes
> below describe past executions. See [README.md](README.md) for current tests,
> policy boundaries and the old-to-current filename map.

# Stage 4 thumbnail acceptance tests

No stage 4 test file existed when implementation was requested. Fourteen cases
were written directly from tasks 4.1–4.3 before implementation and failed RED.
One additional regression reproduces a demonstrated state-loss bug after
rebuilding missing parsed JSON and reusing an already validated image.
It failed before the state restoration fix. Other implementation-time test
expansion was not performed; stages 1–3 expectations were not weakened.

All images are generated locally with Pillow. Tests use the existing virtual
clock and a stream-only fake response that rejects eager `.content` access.
No real recipe/image URL is requested, and no production files are modified.

| Coverage | Cases |
|---|---:|
| Original bytes, actual format/hash and 300×300 dimensions | 1 |
| HTTP 200 HTML or corrupt image | 2 |
| Declared/actual byte limits and pixel bound | 3 |
| Allowed/disallowed redirects, redirect cap and initial host rejection | 4 |
| Selected thumbnail only, same-ID reuse and distinct IDs with identical bytes | 1 |
| Interrupted image recovery, interrupted manifest recovery and corrupted-file rejection | 3 |
| Verified image state restored after parsed JSON recovery | 1 |
| Total | 15 |

`ImageDownloader` shares the source HttpClient for pacing/budgets and accepts an
injected streaming transport. `CollectionRun.create/resume` accept an optional
`image_downloader`; `fetch_thumbnail(id)` uses only a recorded candidate URL.
`resume_pending(include_images=True)` acquires/reuses thumbnails. The default
source-only `resume_pending()` API keeps the previous stage 3 behavior.

Tests validate policy behavior on synthetic streams, not completeness for every
live source host, image format, or animated frame. See [RUNS.md](../RUNS.md) for
configured defaults, first-frame decoding, schema version and operator limits.

From `tools/`:

```powershell
uv run --locked pytest crawlers/tenkrecipes/tests/test_stage4_images.py -q
```
