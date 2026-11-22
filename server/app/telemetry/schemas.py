# AI-generated with Claude Code (Opus 5.5), 2026-11-20; reviewed by Jaehyuk Choi.
"""The only app events the server accepts. Closed names and narrow fields, so no free text
(ingredient names, photos, nicknames) can be sent, even by mistake."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

UUID = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
MAX_EVENTS = 100  # one batch; the app sends at most 20 at a time

EventName = Literal[
    "session_start",  # the app came to the foreground
    "session_end",  # it went to the background; duration_ms = time in the foreground
    "screen_view",  # screen
    "fridge_add",  # source, count
    "recognition",  # status ok|empty|error, count, duration_ms, code
    "dish_list",  # status ok|empty|error, count, duration_ms, code
    "dish_open",  # dish_id
    "recipe_view",  # dish_id, status ok|error, code
    "revise",  # dish_id, status revised|refused|failed|error, duration_ms, code
    "player_error",  # dish_id
]
Status = Literal["ok", "empty", "error", "revised", "refused", "failed"]
Source = Literal["photo", "manual", "suggestion", "pantry"]
Screen = Literal["onboarding", "fridge", "dishes", "profile", "capture", "analyze", "manual_add"]


class AppEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: EventName
    t: int = Field(ge=0, description="Milliseconds since the epoch, on the phone")
    dish_id: str | None = Field(default=None, pattern=r"^[a-z0-9-]{1,80}$")
    count: int | None = Field(default=None, ge=0, le=10_000)
    duration_ms: int | None = Field(default=None, ge=0, le=86_400_000)
    status: Status | None = None
    source: Source | None = None
    screen: Screen | None = None
    code: int | None = Field(default=None, ge=0, le=999, description="HTTP status of a failure")


class EventBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    install_id: str = Field(pattern=UUID, description="Random per install; new after data reset")
    session_id: str = Field(pattern=UUID)
    app_version: str = Field(pattern=r"^[0-9A-Za-z.+-]{1,32}$")
    events: list[AppEvent] = Field(min_length=1, max_length=MAX_EVENTS)


class BatchAccepted(BaseModel):
    accepted: int
