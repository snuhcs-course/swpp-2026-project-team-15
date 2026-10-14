# AI-generated with Claude Code (Opus 5.5), 2026-10-14; review pending by Jaehyuk Choi.
"""Schemas shared across domains."""

from sqlmodel import SQLModel


class ErrorResponse(SQLModel):
    detail: str
