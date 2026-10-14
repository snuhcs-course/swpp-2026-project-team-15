# AI-generated with Claude Code (Opus 5.5), 2026-10-11 to 2026-10-14; review pending by Jaehyuk Choi.
class VisionError(RuntimeError):
    """The provider could not produce a result for the image."""


class VisionUnavailableError(VisionError):
    """The provider is temporarily unavailable (rate limit, timeout, server error); retry later."""
