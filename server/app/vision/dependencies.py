# AI-generated with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.
from typing import Annotated

from fastapi import Depends, Request

from app.vision.providers import VisionProvider


def get_vision_provider(request: Request) -> VisionProvider:
    return request.app.state.vision_provider


VisionProviderDep = Annotated[VisionProvider, Depends(get_vision_provider)]
