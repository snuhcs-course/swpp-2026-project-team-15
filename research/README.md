# Feature research

Use this directory to explore a feature before integrating it into the Android app or server. Keep a topic's hypothesis, executable prototype, input requirements and reproduction command together. Reuse production modules rather than maintaining copies. Once adopted, put the implementation in the app/server and its assertions in the appropriate test suite; keep useful comparison baselines here.

Current tools retain their original Python package names to preserve contributor imports and tests:

- `evaluation/`: real-photo ingredient benchmark, accepted-name ground truth and alternative prompts.
- `experiments/filtering/`: read-only comparisons of ingredient filtering/ranking rules.
- `experiments/revision/`: fixed revision cases, mock/provider adapters and observation reports.
- `experiments/capture/`: frame-selection rules for a short fridge sweep, the Android demo app that measures them on a phone, and the multi-frame recognition evaluation.
- `experiments/name_mapping/`: resolving free-text ingredient names to recipe-table ingredients (exact, synonym, embedding), with the scorer and the typed-input rules. Embedding is optional.
- `experiments/revision_input/`: id-only revision cases, frozen criteria and a mock-by-default harness for the revision request's size and reliability. Needs the revision pipeline from the server.

## Dish-suggestion version

The decision record [decisions/dish-list-and-video-discovery.md](decisions/dish-list-and-video-discovery.md) links the studies behind this version in order:

- `experiments/dish_eval/`: frozen cases and thresholds for suggestions and substitutes (first, rules-based design).
- `experiments/dish_naive/`: the naive design (model sees dish names and the user's ingredients) against that reference, plus prompt and output-cap rounds.
- `experiments/dish_tokens/` and `experiments/dish_pipeline/`: token cost of the selection call, the arrangement of the model calls for videos, and the wording of the video request (round 3).
- `experiments/dish_output_formats/`: answer formats constrained by closed lists (enums), function calls and a LangChain helper, compared with free text; round 2 compared per-request choices and a model mapping of unmatched ingredients (per-request choices adopted); rounds 3–4 measured list length and structure ("cook now" wording, fewest-missing order, staples out of the missing choices adopted; a split by category not adopted); round 5 found that some inputs (계란 + 밥, the app's own preset) make the model walk the whole dish list and adopted a server limit of 36 dishes with an output limit sized for it.
- `experiments/youtube_discovery/` (superseded) and `experiments/youtube_discovery_v2/`: how to find videos; v2 validates a relevance judge against 60 hand-labelled videos before using it.
- `experiments/dish_revision/`: adapting a stored recipe to the user's ingredients (36 synthetic cases, one model call plus a rule check); round 2 added a refusal before the call and a main-ingredient rule, measured also on 29 fridges for the recipes made from captions (adopted). Round 3 matched recipe rows to fridge names with a reviewed table and added one more call after a rejected answer (both adopted); a rule about references to removed steps changed nothing.
- `experiments/dish_recipes/`: tools that snapshot the video lists, fetch captions through an unofficial route (stopped), write recipes from the videos themselves with Gemini (study and build), and validate the recipes. Their outputs are third-party derived and are never committed.

Architecture decisions (roles and the composition root, the factory, the video store policy, the revision check) are in [decisions/](decisions/), as ADRs 001 to 004.

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

Note: on the dish-suggestion version the recipe database and its server code are absent, so the experiment tests that import them (`filtering`, `revision`, `name_mapping`) skip; the research files are kept as the record of how decisions were made.
