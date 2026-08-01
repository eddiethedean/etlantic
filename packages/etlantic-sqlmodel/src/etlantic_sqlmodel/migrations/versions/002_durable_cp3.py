"""002 — CP3 durable work snapshot tables.

Production note: apply via ``etlantic_sqlmodel.migrations.upgrade``.
``create_all`` is for tests/demos only.
"""

from __future__ import annotations

from sqlalchemy.engine import Engine

from etlantic_sqlmodel.control_plane.models import DurableSnapshotRow
from sqlmodel import SQLModel

TABLES = (DurableSnapshotRow,)


def upgrade(engine: Engine) -> None:
    """Create CP3 durable tables."""
    SQLModel.metadata.create_all(
        engine,
        tables=[cls.__table__ for cls in TABLES],  # type: ignore[list-item]
    )


def downgrade(engine: Engine) -> None:
    """Drop CP3 durable tables."""
    SQLModel.metadata.drop_all(
        engine,
        tables=[cls.__table__ for cls in reversed(TABLES)],  # type: ignore[list-item]
    )


__all__ = ["downgrade", "upgrade"]
