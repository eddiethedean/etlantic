"""Optional SQLModel control-plane reference stores (CP1/CP2).

Persistence models are separate from HTTP response models. Sessions are
request-scoped helpers and must not be passed into pipeline runtimes.
``create_control_plane_tables`` / ``create_registry_tables`` are for
tests/demos — production must apply versioned migrations under
``etlantic_sqlmodel.migrations``.
"""

from __future__ import annotations

from etlantic_sqlmodel.control_plane.cp4_stores import (
    CP4_TABLES,
    SQLModelApprovalStore,
    SQLModelAttestationStore,
    SQLModelAuditEvidenceStore,
    SQLModelErasureStore,
    SQLModelObjectiveStore,
    SQLModelPolicyProvider,
    SQLModelQuotaProvider,
    create_cp4_tables,
)
from etlantic_sqlmodel.control_plane.durable_stores import (
    DURABLE_TABLES,
    SQLModelDurableWorkStore,
    create_durable_tables,
)
from etlantic_sqlmodel.control_plane.models import (
    AliasRow,
    Cp4GovernanceSnapshotRow,
    DefinitionRow,
    DurableOutboxEntityRow,
    DurableSnapshotRow,
    DurableSubmissionEntityRow,
    EnvironmentRow,
    EventRow,
    LogicalIdentityRow,
    PromotionRow,
    RevisionRow,
    ScheduleSnapshotRow,
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
from etlantic_sqlmodel.control_plane.schedule_stores import (
    SCHEDULE_TABLES,
    SQLModelScheduleStore,
    create_schedule_tables,
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
    "CP4_TABLES",
    "DURABLE_TABLES",
    "REGISTRY_TABLES",
    "SCHEDULE_TABLES",
    "AliasRow",
    "BackupTranscript",
    "Cp4GovernanceSnapshotRow",
    "DefinitionRow",
    "DurableOutboxEntityRow",
    "DurableSnapshotRow",
    "DurableSubmissionEntityRow",
    "EnvironmentRow",
    "EventRow",
    "LogicalIdentityRow",
    "PromotionRow",
    "RevisionRow",
    "SQLModelApprovalStore",
    "SQLModelAttestationStore",
    "SQLModelAuditEvidenceStore",
    "SQLModelDefinitionRepository",
    "SQLModelDurableWorkStore",
    "SQLModelErasureStore",
    "SQLModelObjectiveStore",
    "SQLModelPolicyProvider",
    "SQLModelQuotaProvider",
    "SQLModelScheduleStore",
    "SQLModelSubmissionStore",
    "ScheduleSnapshotRow",
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
    "create_cp4_tables",
    "create_durable_tables",
    "create_registry_tables",
    "create_schedule_tables",
    "create_sqlite_engine",
    "dump_registry_sqlite",
    "load_registry_sqlite",
    "make_session_factory",
    "read_backup_transcript",
    "request_scoped_session",
    "session_scope",
    "write_backup_transcript",
]
