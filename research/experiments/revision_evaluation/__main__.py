# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Expose the offline-by-default CLI through python -m experiments.revision_evaluation."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
