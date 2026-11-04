# Mapping free-text ingredient names to the recipe table

The app lets users type any name; the recipe table is a fixed set of ingredient names, and model-produced names are free text too. Today a name matches only if it equals a table name or belongs to a synonym group (`app.recipes.constants`); anything else is ignored silently. This topic asks whether a sentence-embedding step would close that gap well enough to belong in the server.

Hypothesis: embedding the names and taking the nearest table name, guarded by a similarity threshold and a lead over the runner-up, recovers names that exact and synonym matching miss without mapping wrong ingredients.

**Result: not supported.** The frozen criteria were not met; cheaper rules cover the same cases.

## Contents

| File | Purpose |
| --- | --- |
| `resolver.py` | Exact, then synonym, then optional embedding match with `tau` and `margin`; the typed-input suggestion rules; a wording-normalisation baseline. Imports `with_synonyms` from the server. |
| `run_experiment.py` | Scores a resolver against a hand-labelled gold file, weighted by how often each name occurred. No model API calls. |
| `../../../server/tests/experiments/name_mapping/` | Offline tests on a synthetic catalog and toy vectors. |

## Input needs

All private, none in the repository: the recipe database (`--db`, read-only), a JSON list of model-produced names with counts (`--names`) and a gold file mapping each name to the table name it should get, or `null` when the table has none (`--gold`). Label before looking at any resolver output. The embedding step needs `fastembed`, which is not a server dependency, and downloads a model once.

```sh
PYTHONPATH=server:research uv run --project server --locked \
  python -m experiments.name_mapping.run_experiment --db DB --names N.json --gold G.json
PYTHONPATH=server:research uv run --project server --locked --with fastembed \
  python -m experiments.name_mapping.run_experiment --db DB --names N.json --gold G.json \
  --embedder fastembed --tau 0.90 0.95 0.99
(cd server && uv run --locked pytest tests/experiments/name_mapping)
```

## Criteria (fixed before the results)

1. Recognition names: wrong mappings at most 2% of occurrences and at least 3 points more names resolved than exact + synonym, with thresholds chosen on one half of the names and judged on the other.
2. Revision steps and tips: catch at least half of the unavailable ingredients a person found named there, with at most 5% false alarms.

## Findings

Model: multilingual MiniLM (int8 ONNX); a larger model gave the same conclusion. Hand labels by one reviewer.

**Recognition names** (91 distinct names, 2,274 answers). Exact + synonym already resolves 77.0%. Of the rest, a few are spelling variants with a table counterpart; most are categories and containers with none (coffee, drink, fruit, bottle).

| Threshold on the chosen half (embedding after exact + synonym) | Wrong mappings |
| --- | --- |
| 0.90 | 15.4% |
| 0.95 | 6.8% |

No threshold on the grid reached 2%, so the frozen choice rejects everything and recovers nothing. Similarity does not separate related from unrelated names: pairs with no connection scored 0.97-0.99. A margin over the runner-up cuts wrong mappings from 4.0% to 0.35% at 0.95, but there is nothing left to recover.

**Typed input** (1,901 synthetic inputs built from table names). Share with the right ingredient among the top 5 suggestions:

| Input variant | App rule | Embedding | App rule, then embedding |
| --- | --- | --- | --- |
| Quantity suffix (n=560) | 0% | 70% | 70% |
| "다진 " prefix (n=549) | 0% | 64% | 64% |
| Inserted spaces (n=183) | 0% | 69% | 69% |
| First two characters (n=357) | 98% | 27% | 98% |
| All variants (n=1,901) | 19% | 53% | 66% |

Embedding helps only where the app rule shows nothing, and even there the right name is in the top 5 for 64-70%. A rule that strips a quantity suffix, a leading "다진 " and spaces (`strip_wording`) resolves most of those variants without a model; its score on these inputs is circular because the inputs were generated with the same patterns, so measure it on real typed input.

**Revision steps and tips** (50 delivered revisions, 13 mentions of an unavailable ingredient found by hand). The shipped check cannot see them by construction (0 of 13). Embedding at the frozen threshold also found 0. Finding every table name as text found 12 but flagged 35 of 50 outputs falsely; with word boundaries and common words excluded, 10 of 13 with 18 of 50; additionally ignoring names contained in allowed names, 10 of 13 with 3 of 50 (6%, built after looking at the false alarms, so in-sample). Embedding added three surface variants (olive oil, starch water, a suffixed name) and false alarms everywhere else. Revision requests already carry ingredient ids, so a resolver would only matter for the step that builds the ids sent to `/recipes/recommendations`; stored cases are unchanged.

**Determinism and cost** (x86 host, ARM not measured). Vectors were bit-identical across repeated runs, batch sizes 1, 20 and 560, two processes and thread counts (2,423 queries); six queries had a top-two gap below 1e-4 and could flip on another CPU. MiniLM: 252 MB of model files, 1.2 s to load, 3.1 ms per query (24 ms for a batch of 20), 763 MB peak memory; the larger model 1.1 GB, 8.6 ms, 1.9 GB.

## Alternatives the data supports

- A few synonym entries for spelling variants (e.g. egg yolk, a misspelt red-pepper-powder name, sausage, wine); together under 1% of answers.
- Keep categories and containers out of recognition (prompt or a "not an ingredient" chip) rather than mapping them.
- Strip quantity, state and spaces before suggesting; show table names from recipe wording variants.
- For steps and tips, the word-boundary rule above, re-measured on a larger sample first.

## Limits

About two independent scenes behind the recognition names; hand labels by one reviewer; 50 revisions, 13 mentions; the int8 model may differ from the original weights; candidate phrases were whitespace tokens and token pairs; the typed inputs are synthetic.
