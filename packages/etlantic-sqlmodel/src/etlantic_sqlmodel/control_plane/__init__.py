"""Optional SQLModel control-plane reference stores (CP1/CP2).

Persistence models are separate from HTTP response models. Sessions are
request-scoped helpers and must not be passed into pipeline runtimes.
``create_control_plane_tables`` / ``create_registry_tables`` are for
tests/demos — production must apply versioned migrations under
``etlantic_sqlmodel.migrations``.
"""

from __future__ import annotations

from etlantic_sqlmodel.control_plane.models import (
    AliasRow,
    DefinitionRow,
    EnvironmentRow,
    EventRow,
    LogicalIdentityRow,
    PromotionRow,
    RevisionRow,
    SecurityDomainRow,
    SubmissionRow,
    TenantRow,
    WorkspaceRow,
)
from etlantic_sqlmodel.control_plane.registry_backup import (
    BACKUP_SCHEMA,
    BackupTranscript,
    backup_round_trip,
    dump_registry_sqlite,
    load_registry_sqlite,
    read_backup_transcript,
    write_backup_transcript,
)
from etlantic_sqlmodel.control_plane.registry_search import collect_revision_hits
from etlantic_sqlmodel.control_plane.registry_stores import (
    REGISTRY_TABLES,
    SqlModelRegistryProvider,
    SqlModelRevisionRegistry,
    SqlModelTenantDirectory,
    SqlModelWorkspaceDirectory,
    create_registry_tables,
)
from etlantic_sqlmodel.control_plane.session import (
    create_sqlite_engine,
    make_session_factory,
    request_scoped_session,
    session_scope,
)
from etlantic_sqlmodel.control_plane.stores import (
    SQLModelDefinitionRepository,
    SqlModelEventStore,
    SQLModelSubmissionStore,
    create_control_plane_tables,
)

__all__ = [
    "BACKUP_SCHEMA",
    "REGISTRY_TABLES",
    "AliasRow",
    "BackupTranscript",
    "DefinitionRow",
    "EnvironmentRow",
    "EventRow",
    "LogicalIdentityRow",
    "PromotionRow",
    "RevisionRow",
    "SQLModelDefinitionRepository",
    "SQLModelSubmissionStore",
    "SecurityDomainRow",
    "SqlModelEventStore",
    "SqlModelRegistryProvider",
    "SqlModelRevisionRegistry",
    "SqlModelTenantDirectory",
    "SqlModelWorkspaceDirectory",
    "SubmissionRow",
    "TenantRow",
    "WorkspaceRow",
    "backup_round_trip",
    "collect_revision_hits",
    "create_control_plane_tables",
    "create_registry_tables",
    "create_sqlite_engine",
    "dump_registry_sqlite",
    "load_registry_sqlite",
    "make_session_factory",
    "read_backup_transcript",
    "request_scoped_session",
    "session_scope",
    "write_backup_transcript",
]
