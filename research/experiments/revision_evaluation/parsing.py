# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Pure JSON parsing measurements for preserved assistant response texts."""

import json
from collections.abc import Iterable

from .contract import ParsingResult, Rate


def classify_json_response(text: str | None) -> ParsingResult:
    """Classify one response independently of structure and production outcomes.

    None means no assistant text was returned. An empty string is a returned
    response and therefore counts as a parse failure. Valid JSON arrays, scalars,
    and null all count as parse successes; later evaluators assess their structure.
    """
    if text is None:
        return ParsingResult(attempted=False, succeeded=None, error=None)
    try:
        json.loads(text)
    except ValueError:
        # Decoder exception strings can contain response fragments. Persist a
        # fixed diagnostic while keeping the original response in its source trace.
        return ParsingResult(attempted=True, succeeded=False, error="invalid JSON")
    return ParsingResult(attempted=True, succeeded=True, error=None)


def aggregate_json_parse_success(texts: Iterable[str | None]) -> Rate:
    """Count successful parses over returned texts, excluding no-response paths.

    Each supplied text represents one observed assistant response, including
    initial and re-ask answers. The caller supplies the complete response sequence
    rather than only the selected final answer. No requests or repairs are made.
    """
    numerator = denominator = 0
    for text in texts:
        result = classify_json_response(text)
        denominator += int(result.attempted)
        numerator += int(result.succeeded is True)
    return Rate(
        numerator=numerator,
        denominator=denominator,
        value=numerator / denominator if denominator else None,
    )
