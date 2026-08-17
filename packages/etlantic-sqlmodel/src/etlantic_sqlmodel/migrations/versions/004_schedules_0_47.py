"""004 — schedule snapshot storage for 0.47 ScheduleStore."""

from __future__ import annotations

from sqlalchemy.engine import Engine

from etlantic_sqlmodel.control_plane.models import ScheduleSnapshotRow
from sqlmodel import SQLModel

TABLES = (ScheduleSnapshotRow,)


def upgrade(engine: Engine) -> None:
    """Create schedule snapshot tables."""
    SQLModel.metadata.create_all(
        engine,
        tables=[cls.__table__ for cls in TABLES],  # type: ignore[list-item]
    )


def downgrade(engine: Engine) -> None:
    """Drop schedule snapshot tables."""
    SQLModel.metadata.drop_all(
        engine,
        tables=[cls.__table__ for cls in reversed(TABLES)],  # type: ignore[list-item]
    )


__all__ = ["downgrade", "upgrade"]
