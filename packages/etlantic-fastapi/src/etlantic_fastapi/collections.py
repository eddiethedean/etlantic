"""Concrete visibility checks for scoped control-plane collections."""

from collections.abc import Callable, Sequence
from typing import TypeVar

from etlantic.control_plane import ControlPlaneContext, ControlPlaneError
from etlantic.control_plane.protocols import Authorizer

T = TypeVar("T")


def visible_items(
    authorizer: Authorizer,
    ctx: ControlPlaneContext,
    action: str,
    items: Sequence[T],
    resource: Callable[[T], str],
) -> list[T]:
    """Filter concrete denies; service failure aborts the entire response.

    The caller must authorize the collection before repository access. Do not
    serialize denied records or expose authorizer exception text.
    """
    visible = []
    try:
        for item in items:
            decision = authorizer.authorize(ctx, action, resource(item))
            if decision.allowed is True:
                visible.append(item)
    except Exception:
        raise ControlPlaneError(
            "Authorization service unavailable",
            code="PMCP503",
            status=503,
            title="Service Unavailable",
        ) from None
    return visible


def visible_limited_items(
    authorizer: Authorizer,
    ctx: ControlPlaneContext,
    action: str,
    fetch: Callable[[int], Sequence[T]],
    resource: Callable[[T], str],
    limit: int,
) -> list[T]:
    """Apply an existing limit after visibility, without a new pagination API.

    Providers expose a limited prefix, not an authorization-aware query. Grow
    that prefix until enough visible records or exhaustion, checking every
    fetched record before returning any response.
    """
    if limit <= 0:
        return []
    size = max(100, limit)
    while True:
        records = fetch(size)
        visible = visible_items(authorizer, ctx, action, records, resource)
        if len(visible) >= limit or len(records) < size:
            return visible[:limit]
        size *= 2
