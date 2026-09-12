"""005 — CP1 definition, submission, and event persistence tables.

These tables back the public SQLModel CP1 reference stores. The migration is
kept separate from the test/demo ``create_control_plane_tables`` helper so
production deployments can provision the stores through the versioned schema
path.
"""

from __future__ import annotations

from sqlalchemy.engine import Engine

from etlantic_sqlmodel.control_plane.models import (
    DefinitionRow,
    EventRow,
    SubmissionRow,
)
from sqlmodel import SQLModel

TABLES = (DefinitionRow, SubmissionRow, EventRow)


def upgrade(engine: Engine) -> None:
    """Create the CP1 reference-store tables."""
    SQLModel.metadata.create_all(
        engine,
        tables=[cls.__table__ for cls in TABLES],  # type: ignore[list-item]
    )


def downgrade(engine: Engine) -> None:
    """Drop the CP1 reference-store tables."""
    SQLModel.metadata.drop_all(
        engine,
        tables=[cls.__table__ for cls in reversed(TABLES)],  # type: ignore[list-item]
    )


__all__ = ["downgrade", "upgrade"]
