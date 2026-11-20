# AI-generated with Claude Code (Sonnet 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Failures of the outside services. The messages are safe to show to the user."""

MODEL_NOT_CONFIGURED = "The model service is not configured"


class DishLLMError(Exception):
    """The model call failed or returned unusable output."""


class VideoError(Exception):
    """The model or YouTube call that finds videos failed."""
