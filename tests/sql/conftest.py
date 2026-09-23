# pyright: reportAttributeAccessIssue=false, reportMissingTypeStubs=false, reportUnknownParameterType=false, reportUnknownVariableType=false
"""Shared SQL pytest fixtures — honor ETLANTIC_SQL_URL when set."""

from __future__ import annotations

import os

import pytest


@pytest.fixture
def sql_plugin():
    """Create the reference SQL plugin using env URL (SQLite fallback)."""
    pytest.importorskip("sqlalchemy")
    os.environ.setdefault("ETLANTIC_SQL_URL", "sqlite+pysqlite:///:memory:")
    from etlantic_sql import create_plugin

    return create_plugin()
