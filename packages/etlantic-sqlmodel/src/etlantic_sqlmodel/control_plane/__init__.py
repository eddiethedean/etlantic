"""Optional SQLModel control-plane reference stores (CP1).

Persistence models are separate from HTTP response models. Sessions are
request-scoped helpers and must not be passed into pipeline runtimes.
``create_control_plane_tables`` is for tests/demos — not production migrations.
"""

from __future__ import annotations

from etlantic_sqlmodel.control_plane.models import DefinitionRow, SubmissionRow
from etlantic_sqlmodel.control_plane.session import (
    create_sqlite_engine,
    make_session_factory,
    request_scoped_session,
    session_scope,
)
from etlantic_sqlmodel.control_plane.stores import (
    SQLModelDefinitionRepository,
    SQLModelSubmissionStore,
    create_control_plane_tables,
)

__all__ = [
    "DefinitionRow",
    "SQLModelDefinitionRepository",
    "SQLModelSubmissionStore",
    "SubmissionRow",
    "create_control_plane_tables",
    "create_sqlite_engine",
    "make_session_factory",
    "request_scoped_session",
    "session_scope",
]
