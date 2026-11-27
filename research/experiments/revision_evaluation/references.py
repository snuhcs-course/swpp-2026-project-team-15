# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Pure change-kind and original-recipe reference findings for parsed answers."""

from dataclasses import dataclass

from app.dishes.prompts import CHANGE_KINDS


@dataclass(frozen=True)
class ReferenceEvaluation:
    """A reference-validity decision with diagnostics that omit response values."""

    valid: bool
    issues: tuple[str, ...]


def evaluate_references(
    answer: object, *, ingredient_count: int, step_count: int
) -> ReferenceEvaluation:
    """Check change kinds and references without repairing or mutating the answer.

    Counts describe the preserved source recipe, not the revised ingredient list
    or steps. Like production, references are one-based row positions bounded by
    these counts. Empty lists are permitted by the prompt; coverage is a separate
    metric. Duplicate references remain unchanged and do not invalidate a change.
    """
    if any(type(count) is not int or count < 0 for count in (ingredient_count, step_count)):
        raise ValueError("source counts must be nonnegative integers")
    if not isinstance(answer, dict):
        return ReferenceEvaluation(valid=False, issues=("$: expected object",))
    changes = answer.get("changes")
    if not isinstance(changes, list):
        return ReferenceEvaluation(valid=False, issues=("$.changes: expected array",))
    issues: list[str] = []
    for index, change in enumerate(changes):
        path = f"$.changes[{index}]"
        if not isinstance(change, dict):
            issues.append(f"{path}: expected object")
            continue
        if change.get("kind") not in CHANGE_KINDS:
            issues.append(f"{path}.kind: unsupported change kind")
        for field, limit in (("ingredient_refs", ingredient_count), ("step_refs", step_count)):
            refs = change.get(field)
            if not isinstance(refs, list):
                issues.append(f"{path}.{field}: expected array")
                continue
            for position, ref in enumerate(refs):
                # bool is an int subclass, but true/false are not source row IDs.
                if type(ref) is not int:
                    issues.append(f"{path}.{field}[{position}]: expected integer")
                elif not 1 <= ref <= limit:
                    issues.append(f"{path}.{field}[{position}]: outside source range 1..{limit}")
    return ReferenceEvaluation(valid=not issues, issues=tuple(issues))
