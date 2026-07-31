"""Resumable Server-Sent Events for control-plane run observation (039-E).

History fallback (CP1 / ADR-016): unknown or expired resume cursors fail closed
with HTTP **410 Gone** and a hint to reconnect without ``cursor`` /
``Last-Event-ID`` to replay from the beginning. They do **not** silently skip
or invent a mid-stream position.

``follow=true`` is capped (default max polls / duration) so CP1 never blocks
unbounded on a sync sleep loop.

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
DEFAULT_FOLLOW_MAX_POLLS = 100
DEFAULT_FOLLOW_MAX_DURATION_S = 60.0


def event_matches_run(event: ControlPlaneEvent, run_id: str) -> bool:
    """True when the event envelope is associated with ``run_id``.

    Matches an explicit ``run_id`` in the payload (and optional host-set
    attribute). Does **not** treat ``acceptance_id`` / ``submission_id`` as
    run identifiers.
    """
    payload = event.payload or {}
    if str(payload.get("run_id") or "") == run_id:
        return True
    top = getattr(event, "run_id", None)
    return bool(top is not None and str(top) == run_id)


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
    max_duration_s: float | None = None,
) -> Iterator[str]:
    """Yield SSE frames for ``run_id`` after ``cursor``.

    When ``follow`` is False (default), emit matching history then close.
    When True, poll for new events with periodic heartbeat comments until
    ``max_polls`` or ``max_duration_s`` is reached. CP1 defaults cap follow at
    :data:`DEFAULT_FOLLOW_MAX_POLLS` polls and
    :data:`DEFAULT_FOLLOW_MAX_DURATION_S` seconds (unbounded follow is rejected
    by applying these defaults).
    """
    if follow:
        if max_polls is None:
            max_polls = DEFAULT_FOLLOW_MAX_POLLS
        if max_duration_s is None:
            max_duration_s = DEFAULT_FOLLOW_MAX_DURATION_S
    seen: set[str] = set()
    position = cursor
    polls = 0
    idle = 0
    deadline = (
        time.monotonic() + float(max_duration_s)
        if follow and max_duration_s is not None
        else None
    )
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
        if deadline is not None and time.monotonic() >= deadline:
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
    max_polls: int | None = None,
    max_duration_s: float | None = None,
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
        iter_run_sse(
            events,
            ctx,
            run_id,
            cursor=cursor,
            follow=follow,
            max_polls=max_polls,
            max_duration_s=max_duration_s,
        ),
        media_type=SSE_MEDIA_TYPE,
        headers=extra,
    )


__all__ = [
    "DEFAULT_FOLLOW_MAX_DURATION_S",
    "DEFAULT_FOLLOW_MAX_POLLS",
    "SSE_MEDIA_TYPE",
    "event_matches_run",
    "format_sse_message",
    "iter_run_sse",
    "resolve_resume_cursor",
    "sse_streaming_response",
    "validate_resume_cursor",
]
