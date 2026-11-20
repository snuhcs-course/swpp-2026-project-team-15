# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Particles chosen from the final syllable of the word they follow."""

import pytest

from app.dishes.korean import attach, particle


@pytest.mark.parametrize(
    ("word", "kind", "expected"),
    [
        ("김치", "이", "가"),
        ("밥", "이", "이"),
        ("두부", "이", "가"),
        ("닭", "이", "이"),
        ("egg", "이", "가"),
        ("밥", "을", "을"),
        ("두부", "을", "를"),
        ("달걀", "은", "은"),
        ("우유", "은", "는"),
        ("파", "과", "와"),
        ("밥", "과", "과"),
        ("양파", "으로", "로"),
        ("물", "으로", "로"),
        ("밥", "으로", "으로"),
        ("B12", "으로", "로"),
        ("김치 ", "이", "가"),
    ],
)
def test_particle(word, kind, expected):
    assert particle(word, kind) == expected


def test_attach_and_empty():
    assert attach("김치", "이") == "김치가"
    assert particle("", "이") == "가"
