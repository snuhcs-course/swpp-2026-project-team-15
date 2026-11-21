# AI-assisted with Codex, 2026-11-21; human review pending.
"""Pure response-shape findings, independent of production checks and recipe quality."""

import json
from collections.abc import Iterable
from dataclasses import dataclass

from app.dishes.prompts import REVISE_SCHEMA

from .contract import Rate
from .parsing import classify_json_response


@dataclass(frozen=True)
class StructureEvaluation:
    """A shape decision and stable diagnostics that never include response values."""

    valid: bool
    issues: tuple[str, ...]


def _shape_issues(value: object, schema: dict, path: str, issues: list[str]) -> None:
    """Check the type/field subset used by REVISE_SCHEMA without coercing data.

    Enum membership and source-reference bounds belong to reference evaluation,
    not this structural metric. This is not a general JSON Schema implementation.
    """
    expected = schema["type"]
    expected_type = {
        "object": dict,
        "array": list,
        "string": str,
        "integer": int,
        "boolean": bool,
    }[expected]
    # bool is an int subclass in Python but is not an integer response field.
    if type(value) is not expected_type:
        issues.append(f"{path}: expected {expected}")
        return
    if expected == "object":
        properties = schema["properties"]
        for key in schema.get("required", []):
            if key not in value:
                issues.append(f"{path}.{key}: required field missing")
        if schema.get("additionalProperties") is False and value.keys() - properties.keys():
            issues.append(f"{path}: unexpected fields")
        for key, field_schema in properties.items():
            if key in value:
                _shape_issues(value[key], field_schema, f"{path}.{key}", issues)
    elif expected == "array":
        for index, item in enumerate(value):
            _shape_issues(item, schema["items"], f"{path}[{index}]", issues)


def evaluate_structure(answer: object) -> StructureEvaluation:
    """Evaluate a parsed answer's shape and feasible/refused consistency, without mutation.

    Required fields and types come from the served response schema. Branch
    consistency follows REVISE_SYSTEM: revisions have an empty refusal reason and
    ingredients/steps; refusals have a specific reason and empty response lists.
    No availability, ingredient content, change-kind, or source-reference rules
    are inferred here, and no production check or model is invoked.
    """
    issues: list[str] = []
    _shape_issues(answer, REVISE_SCHEMA, "$", issues)
    if not isinstance(answer, dict):
        return StructureEvaluation(valid=False, issues=tuple(issues))
    if answer.get("can_revise") is True:
        if isinstance(answer.get("refusal_reason"), str) and answer["refusal_reason"] != "":
            issues.append("$.refusal_reason: revision requires an empty reason")
        for key in ("ingredients", "steps"):
            if isinstance(answer.get(key), list) and not answer[key]:
                issues.append(f"$.{key}: revision requires a nonempty list")
    elif answer.get("can_revise") is False:
        if isinstance(answer.get("refusal_reason"), str) and not answer["refusal_reason"].strip():
            issues.append("$.refusal_reason: refusal requires a nonblank reason")
        for key in ("ingredients", "steps", "tips", "changes"):
            if isinstance(answer.get(key), list) and answer[key]:
                issues.append(f"$.{key}: refusal requires an empty list")
    return StructureEvaluation(valid=not issues, issues=tuple(issues))


def aggregate_structural_validity(texts: Iterable[str | None]) -> Rate:
    """Count valid shapes over JSON-parsed responses, including parsed null or arrays."""
    numerator = denominator = 0
    for text in texts:
        if classify_json_response(text).succeeded is not True:
            continue
        # Parsing success, not the decoded value's truthiness, owns this denominator.
        # In particular, parsed null must be counted as a structural failure.
        denominator += 1
        numerator += int(evaluate_structure(json.loads(text)).valid)
    return Rate(
        numerator=numerator,
        denominator=denominator,
        value=numerator / denominator if denominator else None,
    )
