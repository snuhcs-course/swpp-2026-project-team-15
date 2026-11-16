# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
from typing import Annotated

from fastapi import Depends, Request

from app.dishes.service import DishService


def get_dish_service(request: Request) -> DishService:
    return request.app.state.dish_service


DishServiceDep = Annotated[DishService, Depends(get_dish_service)]
