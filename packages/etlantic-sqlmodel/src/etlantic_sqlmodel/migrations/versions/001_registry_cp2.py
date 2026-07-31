"""001 — CP2 registry directory and revision tables.

Production note: apply via ``etlantic_sqlmodel.migrations.upgrade`` (or an
equivalent Alembic revision). ``create_all`` is for tests/demos only.
"""

from __future__ import annotations

from sqlalchemy.engine import Engine

from etlantic_sqlmodel.control_plane.models import (
    AliasRow,
    EnvironmentRow,
    LogicalIdentityRow,
    PromotionRow,
    RevisionRow,
    SecurityDomainRow,
    TenantRow,
    WorkspaceRow,
)
from sqlmodel import SQLModel

TABLES = (
    TenantRow,
    WorkspaceRow,
    LogicalIdentityRow,
    RevisionRow,
    AliasRow,
    PromotionRow,
    EnvironmentRow,
    SecurityDomainRow,
)


def upgrade(engine: Engine) -> None:
    """Create CP2 registry tables."""
    SQLModel.metadata.create_all(
        engine,
        tables=[cls.__table__ for cls in TABLES],  # type: ignore[list-item]
    )


def downgrade(engine: Engine) -> None:
    """Drop CP2 registry tables (reverse of upgrade)."""
    SQLModel.metadata.drop_all(
        engine,
        tables=[cls.__table__ for cls in reversed(TABLES)],  # type: ignore[list-item]
    )


__all__ = ["downgrade", "upgrade"]
