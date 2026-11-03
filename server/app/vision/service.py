# AI-generated with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.
from collections.abc import Sequence

from app.vision.providers import ImageInput, VisionProvider
from app.vision.schemas import DetectedItem, IngredientCandidate


def detect_images(vision: VisionProvider, images: Sequence[ImageInput]) -> list[DetectedItem]:
    """One image takes the unchanged single-image path; several go out as one request when the
    provider supports it, otherwise one request per image."""
    if len(images) == 1:
        return vision.detect(images[0].data, images[0].mime_type)
    detect_many = getattr(vision, "detect_many", None)
    if detect_many is not None:
        return detect_many(images)
    return [item for image in images for item in vision.detect(image.data, image.mime_type)]


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


def unique_raw_texts(candidates: list[IngredientCandidate]) -> list[IngredientCandidate]:
    """Drop repeated labels that several views of the same item produce, keeping order."""
    for candidate in candidates:
        candidate.raw_texts = list(dict.fromkeys(candidate.raw_texts))
    return candidates
