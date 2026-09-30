"""008 — scoped idempotency for managed runtime lifecycle events."""

from __future__ import annotations

from typing import cast

from sqlalchemy import Table, inspect
from sqlalchemy.engine import Engine

from etlantic_sqlmodel.control_plane.models import EventIdempotencyRow


def _event_idempotency_table() -> Table:
    return cast(Table, vars(EventIdempotencyRow)["__table__"])


def upgrade(engine: Engine) -> None:
    """Create the event-key mapping without rewriting retained event history."""
    inspector = inspect(engine)
    if not inspector.has_table("cp_events"):
        raise RuntimeError("Cannot add event idempotency before cp_events exists")
    _event_idempotency_table().create(engine, checkfirst=True)


def downgrade(engine: Engine) -> None:
    """Remove key mappings; retained event rows remain available."""
    if inspect(engine).has_table("cp_event_idempotency"):
        _event_idempotency_table().drop(engine, checkfirst=True)


__all__ = ["downgrade", "upgrade"]
