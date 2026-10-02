# Vision-to-Recipe AI Pipeline Benchmarks

This directory contains the comparative evaluation suite and reference pipeline implementations (P0 to P5) for the My Little Chef recommendation engine.

> **Full Documentation & Architectural Decision Records**:  
> See the team's GitHub Wiki for comprehensive research findings, failure mode analysis, and trade-off matrices:  
> - [[Design Documentation]](https://github.com/snuhcs-course/swpp-2026-project-team-15/wiki/Design-Documentation)
> - [[Pipeline Candidate Comparative Evaluation]](https://github.com/snuhcs-course/swpp-2026-project-team-15/wiki/Pipeline-Candidate-Comparative-Evaluation)

---

## Directory Structure

```text
research/
├── benchmark_suite.py         # Diagnostic benchmark runner across 6 stress scenarios
├── benchmark_results.json     # Measured quantitative metrics (latency, recall, utility)
├── common/
│   ├── models.py              # Pydantic data schemas (Recipe, RawDetection, Metric)
│   └── recipe_db.py           # Standard canonical ingredient dictionary & verified recipes
└── pipelines/
    ├── baseline_closed_bbox.py        # P0: Closed-vocabulary detector baseline
    ├── p1_open_vocab_embedding.py     # P1: Open-tag VLM + FastEmbed baseline
    ├── p2_hypothesis_driven_vision.py # P2: Learned metric adapter (contrastive loss)
    ├── p3_role_gated_recommender.py   # P3: Dynamic ROC-AUC statistical gating
    ├── p4_constraint_action_dag.py    # P4: Lexicographical structural DAG ranking
    └── p5_integrated_metric_dag.py    # P5: Practical Fusion stack (Proposed for MVP)
```

## Running the Benchmark Suite

```bash
# Execute evaluation across all 6 diagnostic scenarios
python benchmark_suite.py
```
