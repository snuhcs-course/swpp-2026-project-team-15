"""Additive HE review endpoints; legacy /analyze responses remain unchanged.

AI-assisted, 2026-11-09; manual review pending. Model scores are not calibrated accuracy.
"""

import io
import math
import os
import warnings
from typing import Annotated, Literal

from fastapi import APIRouter, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel

from app.vision.dependencies import VisionProviderDep
from app.vision.exceptions import VisionError, VisionUnavailableError
from app.vision.gemini import GeminiVisionProvider
from app.vision.openrouter import OpenRouterVisionProvider
from app.vision.providers import FixtureVisionProvider
from app.vision.router import MAX_IMAGE_BYTES, MAX_TOTAL_BYTES, _read, _uploads
from app.vision.schemas import IngredientCandidate
from app.vision.service import detect_images, to_candidates, unique_raw_texts

router = APIRouter(tags=["vision"])
MAX_REVIEW_PIXELS = 32_000_000
REVIEW_IMAGE_TYPES = ("image/jpeg", "image/png", "image/webp")
FORMAT_MIME_TYPES = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


class ReviewCapabilities(BaseModel):
    review_supported: bool = True
    provider_mode: Literal["mock", "live", "unknown"]
    bbox_supported: bool = False
    review_image_types: tuple[str, ...] = REVIEW_IMAGE_TYPES


class ReviewInfo(BaseModel):
    provider_mode: Literal["mock", "live", "unknown"]
    status: Literal["review_required", "empty"]
    minimum_confidence: float | None = None
    bbox_supported: bool = False
    image_count: int


class ReviewedAnalysis(BaseModel):
    candidates: list[IngredientCandidate]
    review: ReviewInfo


def provider_mode(vision) -> Literal["mock", "live", "unknown"]:
    if isinstance(vision, FixtureVisionProvider):
        return "mock"
    if isinstance(vision, (GeminiVisionProvider, OpenRouterVisionProvider)):
        return "live"
    return "unknown"


def review_threshold() -> float | None:
    """Optional review marker only; unset until a separately recorded calibration exists."""
    raw = os.environ.get("VISION_REVIEW_MIN_CONFIDENCE", "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
        if math.isfinite(value) and 0 <= value <= 1:
            return value
    except ValueError:
        pass
    raise HTTPException(503, "Recognition review configuration is unavailable")


def validate_image(data: bytes, mime_type: str) -> None:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as picture:
                if FORMAT_MIME_TYPES.get(picture.format or "") != mime_type:
                    raise HTTPException(415, "Photo format does not match its declared media type")
                if picture.width * picture.height > MAX_REVIEW_PIXELS:
                    raise HTTPException(413, "Image dimensions exceed the review limit")
                picture.load()
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombWarning,
        Image.DecompressionBombError,
    ) as exc:
        raise HTTPException(422, "The uploaded file could not be read as a photo") from exc


@router.get("/vision/capabilities", response_model=ReviewCapabilities)
def capabilities(vision: VisionProviderDep) -> ReviewCapabilities:
    # Never expose credentials, model prompts or provider diagnostics.
    return ReviewCapabilities(provider_mode=provider_mode(vision))


@router.post("/analyze/review", response_model=ReviewedAnalysis)
def analyze_review(
    vision: VisionProviderDep,
    image: Annotated[UploadFile | None, File()] = None,
    images: Annotated[list[UploadFile] | None, File()] = None,
) -> ReviewedAnalysis:
    threshold = review_threshold()
    inputs = [_read(upload, MAX_IMAGE_BYTES) for upload in _uploads(image, images)]
    if sum(len(i.data) for i in inputs) > MAX_TOTAL_BYTES:
        raise HTTPException(413, "Images exceed 15 MiB in total")
    for photo in inputs:
        validate_image(photo.data, photo.mime_type)
    try:
        candidates = unique_raw_texts(to_candidates(detect_images(vision, inputs)))
    except VisionUnavailableError as exc:
        raise HTTPException(503, "Recognition is temporarily unavailable") from exc
    except VisionError as exc:
        raise HTTPException(502, "Recognition could not produce a usable result") from exc
    return ReviewedAnalysis(
        candidates=candidates,
        review=ReviewInfo(
            provider_mode=provider_mode(vision),
            status="review_required" if candidates else "empty",
            minimum_confidence=threshold,
            image_count=len(inputs),
        ),
    )
