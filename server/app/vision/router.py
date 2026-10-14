# AI-generated with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.vision.dependencies import VisionProviderDep
from app.vision.exceptions import VisionError, VisionUnavailableError
from app.vision.schemas import AnalyzeResponse
from app.vision.service import to_candidates

SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic"}

router = APIRouter(tags=["vision"])


@router.post("/analyze")
def analyze(image: Annotated[UploadFile, File()], vision: VisionProviderDep) -> AnalyzeResponse:
    if image.content_type not in SUPPORTED_IMAGE_TYPES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"Unsupported image type: {image.content_type}"
        )
    data = image.file.read()
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Empty image")
    try:
        items = vision.detect(data, image.content_type)
    except VisionUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except VisionError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return AnalyzeResponse(candidates=to_candidates(items))
