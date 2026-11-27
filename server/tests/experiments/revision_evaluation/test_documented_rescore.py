# AI-assisted with Codex, 2026-11-22; reviewed by Soohyun An
"""Keep the documented offline preview executable without mutating historical data."""

import json
import sys
from pathlib import Path

from experiments.revision_evaluation.contract import RunSummary, fixture_root

from tests.experiments.revision_evaluation.test_cli import offline_guard as offline_guard


def test_readme_rescore_preview_is_offline_and_preserves_source(monkeypatch, capsys):
    """Execute the documented Python body under the existing strict offline guard."""
    root = fixture_root()
    before = {path: path.read_bytes() for path in root.rglob("*.json")}
    readme = (
        Path(__file__).resolve().parents[4] / "research/experiments/revision_evaluation/README.md"
    )
    body = readme.read_text(encoding="utf-8").split("@'\n", 1)[1].split("\n'@", 1)[0]
    monkeypatch.setattr(sys, "argv", ["-", str(root)])
    exec(compile(body, str(readme), "exec"), {})
    summary = RunSummary.model_validate(json.loads(capsys.readouterr().out))
    assert summary.complete and summary.totals.completed_repetitions == 8
    assert summary.totals.incomplete_attempts == 1
    assert summary.explanation_coverage.denominator == 3
    assert summary.totals.cost_usd.value is None
    assert summary.totals.cost_usd.confirmed_subtotal > 0
    assert before == {path: path.read_bytes() for path in before}
