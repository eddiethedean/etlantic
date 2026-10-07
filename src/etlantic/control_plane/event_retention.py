"""Helpers for bounded event idempotency tombstone retention."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

DEFAULT_EVENT_IDEMPOTENCY_RETENTION_SECONDS = 90 * 24 * 60 * 60
MAX_EVENT_IDEMPOTENCY_PRUNE_BATCH = 1000


def normalize_event_time(value: datetime | None = None) -> datetime:
    """Return an aware UTC event-retention timestamp."""
    current = value or datetime.now(UTC)
    if current.tzinfo is None:
        return current.replace(tzinfo=UTC)
    return current.astimezone(UTC)


def event_expiry(created_at: datetime, retention_seconds: int | None) -> str | None:
    """Compute an ISO-8601 expiry, or ``None`` when expiry is disabled."""
    if retention_seconds is None:
        return None
    return (
        (normalize_event_time(created_at) + timedelta(seconds=retention_seconds))
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def event_time(value: str | None) -> datetime | None:
    """Parse an ISO-8601 retention timestamp as an aware UTC value."""
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return normalize_event_time(parsed)


def is_event_expired(value: str | None, *, now: datetime | None = None) -> bool:
    """Check whether a tombstone expiry has elapsed."""
    expires = event_time(value)
    return expires is not None and expires <= normalize_event_time(now)


__all__ = [
    "DEFAULT_EVENT_IDEMPOTENCY_RETENTION_SECONDS",
    "MAX_EVENT_IDEMPOTENCY_PRUNE_BATCH",
    "event_expiry",
    "event_time",
    "is_event_expired",
    "normalize_event_time",
]
