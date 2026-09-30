"""007 — durable, scope-isolated run report storage for managed execution."""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import Table
from sqlalchemy.engine import Engine

from etlantic_sqlmodel.control_plane.models import RunReportRow


def upgrade(engine: Engine) -> None:
    """Create the managed report table without rewriting earlier evidence."""
    _report_table().create(engine, checkfirst=True)


def downgrade(engine: Engine) -> None:
    """Drop only this migration's table."""
    _report_table().drop(engine, checkfirst=True)


def _report_table() -> Table:
    return cast(Table, cast(Any, RunReportRow).__table__)


__all__ = ["downgrade", "upgrade"]
