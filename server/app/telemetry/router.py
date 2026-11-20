# AI-generated with Claude Code (Opus 5.5), 2026-11-20; reviewed by Jaehyuk Choi.
from datetime import UTC, datetime

from fastapi import APIRouter, Request, status

from app.telemetry.schemas import BatchAccepted, EventBatch

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.post(
    "/events",
    summary="Usage events from the app (beta week)",
    operation_id="telemetry_events",
    status_code=status.HTTP_202_ACCEPTED,
)
def events(batch: EventBatch, request: Request) -> BatchAccepted:
    """Accepted and dropped when collection is off on this server."""
    sink = request.app.state.telemetry
    if sink is None:
        return BatchAccepted(accepted=0)
    received = datetime.now(UTC).isoformat(timespec="seconds")
    head = {
        "kind": "app",
        "received": received,
        "install": batch.install_id,
        "session": batch.session_id,
        "version": batch.app_version,
    }
    sink.write([head | e.model_dump(exclude_none=True) for e in batch.events])
    return BatchAccepted(accepted=len(batch.events))
