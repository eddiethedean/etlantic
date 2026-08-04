"""003 — CP4 governance + durable entity normalization.

Adds normalized submission/outbox entity tables (041-P1-01) and CP4
governance snapshot storage.
"""

from __future__ import annotations

from sqlalchemy.engine import Engine

from etlantic_sqlmodel.control_plane.models import (
    Cp4GovernanceSnapshotRow,
    DurableOutboxEntityRow,
    DurableSubmissionEntityRow,
)
from sqlmodel import SQLModel

TABLES = (
    DurableSubmissionEntityRow,
    DurableOutboxEntityRow,
    Cp4GovernanceSnapshotRow,
)


def upgrade(engine: Engine) -> None:
    """Create CP4 / durable-entity tables."""
    SQLModel.metadata.create_all(
        engine,
        tables=[cls.__table__ for cls in TABLES],  # type: ignore[list-item]
    )


def downgrade(engine: Engine) -> None:
    """Drop CP4 / durable-entity tables."""
    SQLModel.metadata.drop_all(
        engine,
        tables=[cls.__table__ for cls in reversed(TABLES)],  # type: ignore[list-item]
    )


__all__ = ["downgrade", "upgrade"]
