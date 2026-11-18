# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
import pytest
from experiments.dish_revision import run_round2b

from app.dishes import prompts


def test_keep_variant_adds_one_sentence_after_rule_2():
    text = run_round2b.keep_variant(prompts.REVISE_SYSTEM)
    assert text.count(run_round2b.KEEP_SENTENCE.strip()) == 1
    assert text.replace(run_round2b.KEEP_SENTENCE, "", 1) == prompts.REVISE_SYSTEM


def test_keep_variant_refuses_an_unknown_prompt():
    with pytest.raises(ValueError):
        run_round2b.keep_variant("no anchor here")


def test_dry_run_makes_no_call(capsys):
    assert run_round2b.main([]) == 0
    assert "dry run" in capsys.readouterr().out
