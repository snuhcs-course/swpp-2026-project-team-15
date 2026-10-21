# Feature research

Use this directory to explore a feature before integrating it into the Android app or server. Keep a topic's hypothesis, executable prototype, input requirements and reproduction command together. Reuse production modules rather than maintaining copies. Once adopted, put the implementation in the app/server and its assertions in the appropriate test suite; keep useful comparison baselines here.

Current tools retain their original Python package names to preserve contributor imports and tests:

- `evaluation/`: real-photo ingredient benchmark, accepted-name ground truth and alternative prompts.
- `experiments/filtering/`: read-only comparisons of ingredient filtering/ranking rules.
- `experiments/revision/`: fixed revision cases, mock/provider adapters and observation reports.

New topics can use their own descriptive directory; the existing package layout is not a template requirement. Historical P0–P5 simulations remain in Git history. This directory is an active development workspace, not an archive of generated results.

## Run from repository root

Use the locked server development environment; no separate environment or dependency copy is needed for the current tools:

```sh
uv sync --project server --locked
uv run --project server --locked python research/experiments/filtering/run_experiment.py --help
PYTHONPATH=research uv run --project server --locked python -m experiments.revision.run_experiment --help
PYTHONPATH=server:research uv run --project server --locked python -m evaluation.vision_benchmark --help
# All Python assertions, including research-tool regressions:
(cd server && uv run --locked pytest)
```

`--help` does not call external providers. Revision experiments default to a labeled mock refusal; see each runner's README for the matching private DB and invocation options. The photo benchmark calls the selected server, or Gemini directly with `--model`; it is not a mock-only test. Review the selected provider before running a live measurement.

Private photos, recipe data, credentials and generated reports stay outside tracked source; existing runners write under ignored data/ or an explicitly supplied output path. Do not check in a second runtime implementation or generated environment. If a new topic actually needs additional dependencies, declare them explicitly without expanding the server runtime requirements. Research and test code are excluded from the server runtime archive. Dependency declarations and the full lockfile are included; `uv sync --locked --no-dev` omits development dependencies.
