"""Filtering rule definitions and explainable deterministic decisions."""
# AI-generated initial implementation with Codex (GPT-6 Luna Medium),
# 2026-10-13; reviewed by Soohyun An.

from __future__ import annotations

from dataclasses import dataclass

from .metrics import RecipeMetrics


@dataclass(frozen=True)
class Rule:
    """One experimental candidate-selection rule.

    ``kind`` selects the evaluator branch; ``threshold`` is used only by D(t).
    These rules are experiment candidates, not finalized service policy.
    """

    rule_id: str
    description: str
    kind: str
    threshold: float | None = None


def build_rules(d_thresholds: tuple[float, ...] = (0.25, 0.5, 0.75)) -> tuple[Rule, ...]:
    """Build Baseline, A, B, C, and one D rule per supplied threshold.

    Thresholds must be in ``(0, 1]``. The values are evaluation parameters;
    choosing defaults here does not finalize a production filtering rule.
    """
    if any(not 0 < value <= 1 for value in d_thresholds):
        raise ValueError("D thresholds must be greater than 0 and at most 1")
    rules = [
        Rule("Baseline", "전체 일치 ≥ 2 AND 주재료 일치 ≥ 1", "baseline"),
        Rule("A", "전체 일치 ≥ 1", "any_match"),
        Rule("B", "일반 재료 일치 ≥ 1", "general_match"),
        Rule("C", "일반 재료 일치 ≥ 2 OR 주재료 일치 ≥ 1", "general_or_main"),
    ]
    rules.extend(
        Rule(f"D({threshold:g})", f"일반 재료 충족률 ≥ {threshold:g}", "general_coverage", threshold)
        for threshold in d_thresholds
    )
    return tuple(rules)


def evaluate_rule(rule: Rule, metrics: RecipeMetrics) -> tuple[bool, str]:
    """Return whether a rule passes and a concise explanation of its decision.

    For a D(t) rule, an undefined general-ingredient coverage (no classified
    general ingredients) fails explicitly instead of treating missing data as
    full coverage. The explanation is intended for CSV review, not an API
    contract.
    """
    if rule.kind == "baseline":
        passed = metrics.total_matches >= 2 and metrics.main_matches >= 1
        reasons = []
        if metrics.total_matches < 2:
            reasons.append("전체 일치 수 2 미만")
        if metrics.main_matches < 1:
            reasons.append("주재료 일치 수 1 미만")
        return passed, "조건 충족" if passed else "; ".join(reasons)
    if rule.kind == "any_match":
        passed = metrics.total_matches >= 1
        return passed, "전체 재료 1개 이상 일치" if passed else "전체 일치 수 0"
    if rule.kind == "general_match":
        passed = metrics.general_matches >= 1
        return passed, "일반 재료 1개 이상 일치" if passed else "일반 재료 일치 수 0"
    if rule.kind == "general_or_main":
        passed = metrics.general_matches >= 2 or metrics.main_matches >= 1
        reasons = []
        if metrics.general_matches < 2:
            reasons.append("일반 재료 일치 수 2 미만")
        if metrics.main_matches < 1:
            reasons.append("주재료 일치 수 0")
        return passed, "조건 충족" if passed else "; ".join(reasons)
    if rule.kind == "general_coverage":
        # A recipe with no classified general ingredients has no meaningful rate.
        rate = metrics.general_coverage
        passed = rate is not None and rate >= rule.threshold  # type: ignore[operator]
        if rate is None:
            return False, "일반 재료가 없어 충족률 계산 불가"
        return passed, (
            f"일반 재료 충족률 {rate:.4f} ≥ {rule.threshold:g}"
            if passed
            else f"일반 재료 충족률 {rate:.4f} < {rule.threshold:g}"
        )
    raise ValueError(f"Unknown rule kind: {rule.kind}")
