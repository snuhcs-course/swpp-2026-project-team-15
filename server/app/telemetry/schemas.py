# AI-generated with Claude Code (Opus 5.5), 2026-11-20; reviewed by Jaehyuk Choi.
# Modified with Claude Code (Opus 5.5), 2026-11-26: crash and ANR events under OpenTelemetry names,
# cooking-mode events.
"""The only app events the server accepts. Closed names and narrow fields, so no free text
(ingredient names, photos, nicknames) can be sent, even by mistake."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

UUID = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
# Crash fields hold names from the code and the phone under OpenTelemetry attribute names
# (exception.type, code.function.name, code.line.number, device.model.identifier,
# android.os.api_level as an integer; ours: exception.cause.type). There is no exception.message or
# exception.stacktrace field: both can carry user data (ADR 007). The app cleans its values to
# these characters, so a crash cannot make a whole batch fail.
CLASS_NAME = r"^[A-Za-z_$][A-Za-z0-9_$.]{0,199}$"
FUNCTION = r"^[A-Za-z0-9_$.<>]{1,200}$"
DEVICE = r"^[A-Za-z0-9 ._()+-]{1,64}$"
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
    "crash",  # exception.*, code.*, device.model.identifier, android.os.api_level, count
    "anr",  # device.model.identifier, android.os.api_level: the app froze and Android closed it
    "cook_start",  # dish_id, recipe, steps: the cooking cards opened
    "cook_exit",  # dish_id, recipe, count = step reached, steps: "조리 종료" before the end
    "cook_complete",  # dish_id, recipe, steps, duration_ms since cook_start
]
Status = Literal["ok", "empty", "error", "revised", "refused", "failed"]
Source = Literal["photo", "manual", "suggestion", "pantry"]
Recipe = Literal["original", "revised"]
Screen = Literal["onboarding", "fridge", "dishes", "profile", "capture", "analyze", "manual_add"]


class AppEvent(BaseModel):
    # Dotted names arrive and are stored as aliases; the Python names are not accepted on the wire.
    model_config = ConfigDict(extra="forbid", serialize_by_alias=True)

    name: EventName
    t: int = Field(ge=0, description="Milliseconds since the epoch, on the phone")
    dish_id: str | None = Field(default=None, pattern=r"^[a-z0-9-]{1,80}$")
    count: int | None = Field(default=None, ge=0, le=10_000)
    duration_ms: int | None = Field(default=None, ge=0, le=86_400_000)
    status: Status | None = None
    source: Source | None = None
    screen: Screen | None = None
    code: int | None = Field(default=None, ge=0, le=999, description="HTTP status of a failure")
    recipe: Recipe | None = Field(default=None, description="Cooking: the recipe being cooked")
    steps: int | None = Field(default=None, ge=0, le=500, description="Cooking: number of steps")
    exception_type: str | None = Field(
        default=None, alias="exception.type", pattern=CLASS_NAME, description="Thrown class"
    )
    exception_cause_type: str | None = Field(
        default=None,
        alias="exception.cause.type",
        pattern=CLASS_NAME,
        description="Innermost cause's class, when it differs (not an OpenTelemetry name)",
    )
    code_function: str | None = Field(
        default=None,
        alias="code.function.name",
        pattern=FUNCTION,
        description="First frame of the app's code: Class.method",
    )
    code_line: int | None = Field(
        default=None, alias="code.line.number", ge=0, le=999_999, description="Its line"
    )
    device_model: str | None = Field(
        default=None, alias="device.model.identifier", pattern=DEVICE, description="Phone model"
    )
    api_level: int | None = Field(
        default=None,
        alias="android.os.api_level",
        ge=1,
        le=99,
        description="Android API level (not an OpenTelemetry name)",
    )


class EventBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    install_id: str = Field(pattern=UUID, description="Random per install; new after data reset")
    session_id: str = Field(pattern=UUID)
    app_version: str = Field(pattern=r"^[0-9A-Za-z.+-]{1,32}$")
    events: list[AppEvent] = Field(min_length=1, max_length=MAX_EVENTS)


class BatchAccepted(BaseModel):
    accepted: int
