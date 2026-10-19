"""Regression tests for optional numerator-only match exclusions."""
# AI-generated initial implementation with Codex (GPT-6 Luna Medium),
# 2026-10-13; reviewed by Soohyun An.

import unittest

from experiments.filtering.run_experiment import _ingredient_match_details
from server.recipe_filtering.metrics import (
    MAIN, SECONDARY, SEASONING, Recipe, calculate_metrics,
)
from server.recipe_filtering.rules import build_rules, evaluate_rule


class MatchExclusionTests(unittest.TestCase):
    """Keep classification, denominators, and inventory independent of exclusions."""

    def setUp(self):
        self.recipe = Recipe(1, "fixture", {
            1: frozenset({MAIN}),
            2: frozenset({MAIN, SEASONING}),
            3: frozenset({SECONDARY}),
            4: frozenset({SEASONING}),
            5: frozenset(),
        }, {})
        self.available = frozenset({1, 2, 3, 4, 5})

    def test_exclusion_keeps_denominators_and_conflicts(self):
        before = calculate_metrics(self.recipe, self.available)
        after = calculate_metrics(self.recipe, self.available, frozenset({2, 3, 4}))
        self.assertEqual((after.total_matches, after.general_matches,
                          after.main_matches, after.seasoning_matches), (2, 1, 1, 0))
        self.assertEqual((after.total_coverage, after.general_coverage,
                          after.main_coverage), (2 / 5, 1 / 3, 1 / 2))
        for field in ("total_ingredients", "general_ingredients", "main_ingredients",
                      "seasoning_ingredients", "conflicting_ingredient_ids",
                      "main_seasoning_conflict_ids"):
            self.assertEqual(getattr(before, field), getattr(after, field))
        self.assertEqual(_ingredient_match_details(self.recipe, self.available),
                         ([1, 2, 3, 4, 5], [], [1, 2], []))

    def test_empty_and_absent_exclusions_preserve_default_decisions(self):
        before = calculate_metrics(self.recipe, self.available)
        for exclusions in (frozenset(), frozenset({999})):
            after = calculate_metrics(self.recipe, self.available, exclusions)
            self.assertEqual(before, after)
            for rule in build_rules():
                self.assertEqual(evaluate_rule(rule, before), evaluate_rule(rule, after))

    def test_all_excluded_and_undefined_rates(self):
        after = calculate_metrics(self.recipe, self.available, self.available)
        self.assertEqual((after.total_matches, after.general_matches,
                          after.main_matches, after.seasoning_matches), (0, 0, 0, 0))
        for rule in build_rules():
            self.assertFalse(evaluate_rule(rule, after)[0])
        unclassified = Recipe(2, "unclassified", {1: frozenset()}, {})
        metrics = calculate_metrics(unclassified, frozenset({1}), frozenset({1}))
        self.assertEqual(metrics.total_coverage, 0)
        self.assertIsNone(metrics.general_coverage)
        self.assertIsNone(metrics.main_coverage)


if __name__ == "__main__":
    unittest.main()
