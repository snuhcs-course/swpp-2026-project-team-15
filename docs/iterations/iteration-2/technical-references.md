# Official technical references checked

Checked2026-10-20. Latest SWPP PDFs remain the source of course obligations. The following primary references inform technical behavior, not extra course requirements.

| Reference | Applied decision |
| --- | --- |
| [Android DataStore](https://developer.android.com/topic/libraries/architecture/datastore) | Keep Hyeokjun's single application store and immutable profile transformations; new persistence test closes/joins the old store before creating a replacement |
| [Kotlin cancellation](https://kotlinlang.org/docs/cancellation-and-timeouts.html) | Rethrow cancellation, separate error from empty, and guard old results with generation IDs |
| [Compose testing APIs](https://developer.android.com/develop/ui/compose/testing/apis) | Assert observable semantics and explicit user actions; original/suggestion toggle tests and precise status assertions |
| [pre-commit](https://pre-commit.com/) | Explicit install/config; quick local hooks reuse the same cwd/commands as CI. allow-missing-config supports the repository's older branches without disabling checks where config exists |
| [Coverage source scope](https://coverage.readthedocs.io/en/latest/source.html) | Include app/filtering/revision rather than reporting app-only coverage as whole server coverage |
| [GitHub workflow artifacts](https://docs.github.com/en/actions/tutorials/store-and-share-data) | Save test/coverage reports and APK separately from source; no private CSV/DB/credentials in artifacts |
| [Gemini compatibility](https://ai.google.dev/gemini-api/docs/openai) / [structured output](https://ai.google.dev/gemini-api/docs/structured-output) | Reuse existing Gemini key/model through the existing Chat Completions adapter with provider configuration; validate actual structured response instead of assuming format compatibility |

User authorized autonomous live verification within the existing free quota. Stop on quota exhaustion, record actual call/outcome and do not interpret retries/fallback providers as free authorization. Keep mock default for regular development/CI. Docker/nginx operational stack remains Iteration3 planning.

For the final fresh clone, rechecked [uv locking/sync](https://docs.astral.sh/uv/concepts/projects/sync/), [AndroidJUnitRunner](https://developer.android.com/training/testing/instrumented-tests/androidx-test-libraries/runner) and [gh pr create](https://cli.github.com/manual/gh_pr_create). Use locked dependency synchronization, distinguish local and device tests, and specify PR base/head explicitly. These do not authorize publication of separate external Wiki/Sheet records.
