# AI-generated with Claude Code (Opus 5.5), 2026-10-11 to 2026-10-14; reviewed by Jaehyuk Choi.
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.schemas import ErrorResponse
from app.vision.dependencies import VisionProviderDep
from app.vision.exceptions import VisionError, VisionUnavailableError
from app.vision.schemas import AnalyzeResponse
from app.vision.service import to_candidates

SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}

router = APIRouter(tags=["vision"])


@router.post(
    "/analyze",
    summary="Detect ingredients in a photo",
    operation_id="analyze_photo",
    responses={
        415: {"model": ErrorResponse, "description": "Not a JPEG, PNG, WebP, HEIC or HEIF image"},
        502: {"model": ErrorResponse, "description": "Recognition failed or returned bad output"},
        503: {"model": ErrorResponse, "description": "Recognition temporarily unavailable; retry"},
    },
)
def analyze(
    image: Annotated[UploadFile, File(description="Fridge or pantry photo, sent unchanged")],
    vision: VisionProviderDep,
) -> AnalyzeResponse:
    """Return ingredient candidates for the user to confirm; nothing is saved to the fridge."""
    if image.content_type not in SUPPORTED_IMAGE_TYPES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"Unsupported image type: {image.content_type}"
        )
    data = image.file.read(16 * 1024 * 1024 + 1)
    if len(data) > 16 * 1024 * 1024:
        raise HTTPException(413, "Image exceeds 16 MiB")
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Empty image")
    try:
        items = vision.detect(data, image.content_type)
    except VisionUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except VisionError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return AnalyzeResponse(candidates=to_candidates(items))
