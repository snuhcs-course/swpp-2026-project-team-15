# AI-generated with Claude Code (Sonnet 5.5), 2026-11-03; reviewed by Jaehyuk Choi.
"""Revision options read from the environment."""

import pytest

from app.recipes.policy import (
    PRESCREEN_ENV,
    RETRY_ENV,
    WORKERS_ENV,
    RecommendationPolicy,
)
from recipe_revision.seasoning import ASSUME_ALL, SeasoningPolicy


def test_unset_environment_keeps_the_defaults():
    assert RecommendationPolicy.from_env({}) == RecommendationPolicy()


def test_environment_overrides_workers_prescreen_and_retry():
    policy = RecommendationPolicy.from_env(
        {WORKERS_ENV: "3", PRESCREEN_ENV: " Fill ", RETRY_ENV: "true"}
    )
    assert (policy.revision_workers, policy.prescreen, policy.retry_on_rejection) == (
        3,
        "fill",
        True,
    )
    assert RecommendationPolicy.from_env({RETRY_ENV: "0"}).retry_on_rejection is False


@pytest.mark.parametrize(
    ("env", "message"),
    [
        ({WORKERS_ENV: "many"}, "must be an integer"),
        ({WORKERS_ENV: "9"}, "between 1 and"),
        ({PRESCREEN_ENV: "always"}, "off, refuse or fill"),
        ({RETRY_ENV: "maybe"}, "true or false"),
    ],
)
def test_invalid_values_fail_with_a_clear_message(env, message):
    with pytest.raises(ValueError, match=message):
        RecommendationPolicy.from_env(env)


def test_explicit_arguments_are_kept_when_the_environment_is_silent():
    assert RecommendationPolicy.from_env({}, prescreen="off").prescreen == "off"


def test_assumed_ids_list_water_first_and_the_declared_seasonings_only_in_list_mode():
    listed = SeasoningPolicy("list", frozenset({284, 9, 204}), {})
    assert RecommendationPolicy(seasonings=listed).assumed_ids == [204, 9, 284]
    assert RecommendationPolicy(seasonings=ASSUME_ALL).assumed_ids == [204]
