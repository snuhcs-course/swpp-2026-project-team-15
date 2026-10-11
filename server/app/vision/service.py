# AI-generated with Claude Code (Opus 5.5), 2026-10-11; review pending by Jaehyuk Choi.
from app.vision.schemas import DetectedItem, IngredientCandidate


def to_candidates(items: list[DetectedItem]) -> list[IngredientCandidate]:
    """Merge items sharing a category, keeping the highest confidence and first-seen order."""
    merged: dict[str, IngredientCandidate] = {}
    for item in items:
        name = item.category.strip()
        if not name:
            continue
        if name in merged:
            existing = merged[name]
            existing.raw_texts.append(item.name_raw)
            existing.confidence = max(existing.confidence, item.confidence)
        else:
            merged[name] = IngredientCandidate(
                name=name, raw_texts=[item.name_raw], confidence=item.confidence
            )
    return list(merged.values())
