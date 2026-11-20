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
    catalog = request.app.state.dishes.service.catalog
    records = []
    for e in batch.events:
        record = e.model_dump(exclude_none=True)
        if "dish_id" in record and catalog.get(record["dish_id"]) is None:
            del record["dish_id"]  # only ids from the dish list are kept: no free text
        records.append(head | record)
    sink.write(records)
    return BatchAccepted(accepted=len(batch.events))
