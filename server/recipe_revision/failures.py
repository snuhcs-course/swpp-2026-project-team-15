"""Allowlisted operational failure metadata shared by adapters and callers."""

from dataclasses import dataclass
from typing import Literal

FailureCode = Literal[
    "authentication",
    "permission",
    "configuration",
    "rate_limit",
    "quota_exceeded",
    "provider_unavailable",
    "timeout",
    "connection",
    "response_format",
    "api_error",
    "internal",
]
FailureStage = Literal[
    "configuration",
    "api_request",
    "provider_response",
    "response_parsing",
    "revision",
]
SHARED_CODES = frozenset(
    {
        "authentication",
        "permission",
        "configuration",
        "rate_limit",
        "quota_exceeded",
        "provider_unavailable",
    }
)


@dataclass(frozen=True)
class Failure:
    """Non-secret classification; messages are generated from codes, never upstream text."""

    code: FailureCode
    stage: FailureStage
    http_status: int | None = None

    @property
    def scope(self) -> Literal["individual", "shared"]:
        return "shared" if self.code in SHARED_CODES else "individual"

    @property
    def message(self) -> str:
        return f"Recipe revision failed ({self.code})."
