"""Resumable Server-Sent Events for control-plane run observation (039-E).

History fallback (CP1 / ADR-016): unknown or expired resume cursors fail closed
with HTTP **410 Gone** and a hint to reconnect without ``cursor`` /
``Last-Event-ID`` to replay from the beginning. They do **not** silently skip
or invent a mid-stream position.

Optional WebSocket adapters are experimental and not required for the 0.39
exit gate — they are intentionally omitted here.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator, Mapping
from typing import Any

from starlette.responses import StreamingResponse

from etlantic.control_plane import (
    CONTROL_PLANE_EVENT_SCHEMA,
    ControlPlaneContext,
    ControlPlaneEvent,
    EventStore,
)

SSE_MEDIA_TYPE = "text/event-stream"


def event_matches_run(event: ControlPlaneEvent, run_id: str) -> bool:
    """True when the event envelope is associated with ``run_id``."""
    payload = event.payload or {}
    if str(payload.get("run_id") or "") == run_id:
        return True
    # Accept receipts may key the run as submission/resource id.
    for key in ("submission_id", "resource_id", "acceptance_id"):
        if str(payload.get(key) or "") == run_id:
            return True
    return False


def format_sse_message(event: ControlPlaneEvent) -> str:
    """Encode one ``ControlPlaneEvent`` as an SSE message (id = resume cursor)."""
    body = event.to_dict()
    if body.get("schema") != CONTROL_PLANE_EVENT_SCHEMA:
        body["schema"] = CONTROL_PLANE_EVENT_SCHEMA
    data = json.dumps(body, separators=(",", ":"), sort_keys=True)
    return f"id: {event.cursor}\nevent: {event.kind}\ndata: {data}\n\n"


def resolve_resume_cursor(
    *,
    cursor: str | None,
    last_event_id: str | None,
) -> str | None:
    """Prefer explicit ``cursor`` query param over ``Last-Event-ID`` header."""
    if cursor is not None and cursor != "":
        return cursor
    if last_event_id is not None and last_event_id != "":
        return last_event_id
    return None


def validate_resume_cursor(
    events: EventStore,
    ctx: ControlPlaneContext,
    cursor: str | None,
) -> None:
    """Fail closed with 410 when ``cursor`` is unknown in scope."""
    if cursor is None:
        return
    # Probe: unknown cursors raise ControlPlaneError.gone from conforming stores.
    events.list_after_cursor(ctx, cursor, limit=1)


def iter_run_sse(
    events: EventStore,
    ctx: ControlPlaneContext,
    run_id: str,
    *,
    cursor: str | None,
    follow: bool = False,
    poll_interval: float = 0.25,
    heartbeat_every: int = 4,
    max_polls: int | None = None,
) -> Iterator[str]:
    """Yield SSE frames for ``run_id`` after ``cursor``.

    When ``follow`` is False (default), emit matching history then close.
    When True, poll for new events with periodic heartbeat comments until
    ``max_polls`` is reached (None = unbounded; tests should bound).
    """
    seen: set[str] = set()
    position = cursor
    polls = 0
    idle = 0
    while True:
        batch = events.list_after_cursor(ctx, position, limit=200)
        emitted = 0
        for event in batch:
            position = event.cursor
            if not event_matches_run(event, run_id):
                continue
            if event.event_id in seen:
                continue
            seen.add(event.event_id)
            emitted += 1
            yield format_sse_message(event)
        if not follow:
            break
        polls += 1
        if max_polls is not None and polls >= max_polls:
            break
        if emitted == 0:
            idle += 1
            if idle % heartbeat_every == 0:
                yield ": heartbeat\n\n"
        else:
            idle = 0
        time.sleep(poll_interval)


def sse_streaming_response(
    events: EventStore,
    ctx: ControlPlaneContext,
    run_id: str,
    *,
    cursor: str | None,
    follow: bool = False,
    headers: Mapping[str, str] | None = None,
) -> StreamingResponse:
    """Build a ``text/event-stream`` response for run events."""
    validate_resume_cursor(events, ctx, cursor)
    extra: dict[str, Any] = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    if headers:
        extra.update(dict(headers))
    return StreamingResponse(
        iter_run_sse(events, ctx, run_id, cursor=cursor, follow=follow),
        media_type=SSE_MEDIA_TYPE,
        headers=extra,
    )


__all__ = [
    "SSE_MEDIA_TYPE",
    "event_matches_run",
    "format_sse_message",
    "iter_run_sse",
    "resolve_resume_cursor",
    "sse_streaming_response",
    "validate_resume_cursor",
]
