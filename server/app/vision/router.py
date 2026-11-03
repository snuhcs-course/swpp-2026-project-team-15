# AI-generated with Claude Code (Opus 5.5), 2026-10-11 to 2026-10-14; reviewed by Jaehyuk Choi.
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.schemas import ErrorResponse
from app.vision.dependencies import VisionProviderDep
from app.vision.exceptions import VisionError, VisionUnavailableError
from app.vision.providers import ImageInput
from app.vision.schemas import AnalyzeResponse
from app.vision.service import detect_images, to_candidates, unique_raw_texts

SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
MAX_IMAGE_BYTES = 16 * 1024 * 1024
# Several views are one request body; keep their total below the 16 MiB proxy limit.
MAX_TOTAL_BYTES = 15 * 1024 * 1024
MAX_IMAGES = 15

router = APIRouter(tags=["vision"])


@router.post(
    "/analyze",
    summary="Detect ingredients in a photo or in several views of the same fridge",
    operation_id="analyze_photo",
    responses={
        413: {"model": ErrorResponse, "description": "An image or the total upload is too large"},
        415: {"model": ErrorResponse, "description": "Not a JPEG, PNG, WebP, HEIC or HEIF image"},
        422: {"model": ErrorResponse, "description": "No image, empty image or too many images"},
        502: {"model": ErrorResponse, "description": "Recognition failed or returned bad output"},
        503: {"model": ErrorResponse, "description": "Recognition temporarily unavailable; retry"},
    },
)
def analyze(
    vision: VisionProviderDep,
    image: Annotated[
        UploadFile | None, File(description="Fridge or pantry photo, sent unchanged")
    ] = None,
    images: Annotated[
        list[UploadFile] | None,
        File(description=f"2 to {MAX_IMAGES} views of the same fridge, recognised in one request"),
    ] = None,
) -> AnalyzeResponse:
    """Return ingredient candidates for the user to confirm; nothing is saved to the fridge.

    Send `image` (one photo) or `images` (2 to 15 views of the same fridge)."""
    uploads = _uploads(image, images)  # one `images` part is handled like `image`
    inputs = [_read(upload, MAX_IMAGE_BYTES) for upload in uploads]
    if len(inputs) > 1 and sum(len(i.data) for i in inputs) > MAX_TOTAL_BYTES:
        raise HTTPException(413, "Images exceed 15 MiB in total")
    try:
        items = detect_images(vision, inputs)
    except VisionUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except VisionError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    candidates = to_candidates(items)
    return AnalyzeResponse(
        candidates=unique_raw_texts(candidates) if len(inputs) > 1 else candidates
    )


def _uploads(image: UploadFile | None, images: list[UploadFile] | None) -> list[UploadFile]:
    if image is not None and images:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Send image or images, not both")
    uploads = [image] if image is not None else list(images or [])
    if not uploads:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "No image")
    if len(uploads) > MAX_IMAGES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"At most {MAX_IMAGES} images per request"
        )
    return uploads


def _read(upload: UploadFile, limit: int) -> ImageInput:
    if upload.content_type not in SUPPORTED_IMAGE_TYPES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"Unsupported image type: {upload.content_type}"
        )
    data = upload.file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, "Image exceeds 16 MiB")
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Empty image")
    return ImageInput(data, upload.content_type)
