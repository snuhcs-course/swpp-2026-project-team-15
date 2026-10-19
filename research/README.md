# Vision-to-Recipe research archive

This directory preserves the Iteration 1 P0–P5 comparison. It is included in main through PR #6, but is separate from the Android/FastAPI runtime.

## What the results mean

`benchmark_suite.py` runs six diagnostic scenarios over supplied ingredient strings. Vision is simulated; token counts and several utility/accuracy values are fixed or constructed by the pipelines. Some embedding computations use FastEmbed. `benchmark_results.json` contains the output of that mixed simulation, not measured real-photo recognition, real-VLM latency/cost, or verified cooking/allergy safety. A successful simulated scenario does not validate production deployment.

`common/recipe_db.py` has a small reference vocabulary (31 canonical ingredients and about 11 example recipes), distinct from the main SQLite dataset. P2–P5 names and diagrams describe experimental ideas, not evidence that learned training, calibrated statistical gating or safe recipe adaptation is deployed.

## Files

| Path | Purpose |
| --- | --- |
| `benchmark_suite.py` | Scenario runner; actual location of the script cited in old Wiki research |
| `benchmark_results.json` | Archived scenario output with the limitations above |
| `common/` | Research schemas and small example catalog |
| `pipelines/` | P0 baseline and P1–P5 candidate experiments |

The historical [pipeline comparison](https://github.com/snuhcs-course/swpp-2026-project-team-15/wiki/Pipeline-Candidate-Comparative-Evaluation) and [research design](https://github.com/snuhcs-course/swpp-2026-project-team-15/wiki/Vision-to-Recipe-Research-Design) retain their dated proposal context. Follow runtime code and current design documentation for the implemented API.

## Reproducing the historical experiment

The runner imports FastEmbed, which is not supplied by the server environment, and initializing its embedding model may download model files. Prepare a separate research environment and confirm dependency/download authorization first. The archived entry command, from the repository root, is:

```sh
(cd research && python benchmark_suite.py)
```

It writes `research/benchmark_results.json`; preserve original output before any authorized rerun. This is not required to launch the local demo. No research dependencies were installed and no benchmark was rerun during the October 20 documentation refresh.
