# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Attach deterministic findings to v1 observations without rewriting source evidence."""

import json

from .contract import AnswerEvaluation, DeterministicEvaluation, Observation, Rate
from .coverage import deleted_ingredient_coverage
from .parsing import classify_json_response
from .references import evaluate_references
from .structure import evaluate_structure


def evaluate_observation(observation: Observation) -> Observation:
    """Return an independently evaluated copy, retaining production decisions and evidence.

    Raw assistant text owns parsing and structure/reference findings. Recorded
    decoded answers remain unchanged, including any production-decoded result
    that differs from raw text. Coverage uses only the terminal call's decoded
    revising answer (or its parsed raw answer when no decoded answer was stored).
    No earlier answer substitutes for a missing or invalid terminal answer.
    """
    result = observation.model_copy(deep=True)
    recipe = result.input.original_recipe
    findings: list[AnswerEvaluation] = []
    terminal_answer = None
    for call in result.model_calls:
        texts = [
            attempt.safe_response_text
            for attempt in call.http_attempts
            if attempt.state == "response_received"
            and attempt.status_code == 200
            and attempt.safe_response_text is not None
        ]
        # Production retries only 429s, so each logical call can return at most
        # one assistant text. Reject ambiguous imported data instead of losing it.
        if len(texts) > 1:
            raise ValueError("logical call contains multiple assistant response texts")
        text = texts[0] if texts else None
        call.parsing = classify_json_response(text)
        parsed = json.loads(text) if call.parsing.succeeded is True else None
        terminal_answer = call.decoded_answer if call.decoded_answer is not None else parsed
        if call.parsing.succeeded is not True:
            findings.append(
                AnswerEvaluation(
                    logical_call_index=call.index,
                    structure_valid=None,
                    reference_valid=None,
                    issues=[],
                )
            )
            continue
        structure = evaluate_structure(parsed)
        references = evaluate_references(
            parsed,
            ingredient_count=len(recipe.ingredients),
            step_count=len(recipe.steps),
        )
        findings.append(
            AnswerEvaluation(
                logical_call_index=call.index,
                structure_valid=structure.valid,
                reference_valid=references.valid,
                issues=list(dict.fromkeys((*structure.issues, *references.issues))),
            )
        )

    coverage = Rate(numerator=0, denominator=0, value=None)
    # Incomplete attempts have no terminal answer. Missing/malformed ingredient
    # lists cannot establish deletions; their shape finding remains visible.
    if result.execution.state == "completed" and isinstance(terminal_answer, dict):
        rows = terminal_answer.get("ingredients")
        if (
            terminal_answer.get("can_revise") is True
            and isinstance(rows, list)
            and all(isinstance(row, dict) and isinstance(row.get("name"), str) for row in rows)
        ):
            coverage = deleted_ingredient_coverage(recipe, terminal_answer)
    result.deterministic_evaluation = DeterministicEvaluation(
        answers=findings,
        deleted_ingredient_explanation=coverage,
    )
    # Revalidate the copy against the frozen public contract before returning it.
    return Observation.model_validate(result.model_dump(by_alias=True))
