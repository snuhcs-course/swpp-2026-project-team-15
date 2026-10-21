"""Django-independent recipe filtering primitives.

The package accepts plain recipe records and normalized inventory IDs. It
contains no persistence or web-framework integration, so a future Django
adapter can translate ORM objects and reuse the same metrics and rule logic.
"""
# AI-generated initial implementation with Codex (GPT-6 Luna Medium),
# 2026-10-13; reviewed by Soohyun An.

from .metrics import Recipe, RecipeMetrics, calculate_metrics
from .rules import Rule, build_rules, evaluate_rule

__all__ = ["Recipe", "RecipeMetrics", "Rule", "build_rules", "calculate_metrics", "evaluate_rule"]
