"""Control-plane identity, authorization, and scoped store protocols (CP1/CP2).

Public FastAPI-optional core surface. Import via::

    import etlantic as etl

    ctx = etl.control_plane.ControlPlaneContext(...)

or ``from etlantic.control_plane import ControlPlaneContext``.

FastAPI and SQLModel remain optional adapters; this package imports neither.
"""

from __future__ import annotations

from etlantic.control_plane.authz import (
    Disclosure,
    authorized_get_definition,
    map_deny_disclosure,
    raise_for_deny,
    require_authorized,
    require_authorized_run,
)
from etlantic.control_plane.errors import (
    CONTROL_PLANE_ERROR_SCHEMA,
    ControlPlaneError,
    ErrorDisclosure,
    ProblemDetails,
)
from etlantic.control_plane.history_memory import MemoryHistoryStore, MemoryImpactIndex
from etlantic.control_plane.history_models import (
    CACHE_INVALIDATION_EVENT_SCHEMA,
    IMPACT_EDGE_SCHEMA,
    PLAN_OBSERVATION_RECORD_SCHEMA,
    RELIABILITY_OBSERVATION_RECORD_SCHEMA,
    SCHEMA_OBSERVATION_RECORD_SCHEMA,
    CacheInvalidationEvent,
    ImpactEdge,
    ObservationKind,
    PlanObservationRecord,
    ReliabilityObservationRecord,
    SchemaObservationRecord,
    assert_history_metadata_only,
)
from etlantic.control_plane.history_protocols import HistoryStore, ImpactIndex
from etlantic.control_plane.memory import (
    MemoryAuthorizer,
    MemoryDefinitionRepository,
    MemoryEventStore,
    MemorySubmissionStore,
)
from etlantic.control_plane.models import (
    ACCEPT_RECEIPT_SCHEMA,
    CONTROL_PLANE_CONTEXT_SCHEMA,
    CONTROL_PLANE_EVENT_SCHEMA,
    SSE_CURSOR_SCHEMA,
    AcceptReceipt,
    AcceptResult,
    ControlPlaneContext,
    ControlPlaneEvent,
    CorrelationKey,
    EnvironmentRef,
    IdempotencyKey,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic.control_plane.protocols import (
    Authorizer,
    AuthzDecision,
    DefinitionRepository,
    EventStore,
    SubmissionStore,
)
from etlantic.control_plane.redaction import (
    REDACTED,
    assert_no_secrets,
    redact_control_plane_payload,
    redact_control_plane_text,
)
from etlantic.control_plane.registry_definitions import (
    DEFINITION_KIND,
    RegistryDefinitionRepository,
)
from etlantic.control_plane.registry_memory import (
    MemoryRegistryProvider,
    MemoryRevisionRegistry,
    MemoryTenantDirectory,
    MemoryWorkspaceDirectory,
    content_fingerprint,
)
from etlantic.control_plane.registry_models import (
    ALIAS_RECORD_SCHEMA,
    ENVIRONMENT_RECORD_SCHEMA,
    LOGICAL_IDENTITY_SCHEMA,
    PROMOTION_RECORD_SCHEMA,
    REGISTRY_REVISION_SCHEMA,
    SECURITY_DOMAIN_RECORD_SCHEMA,
    TENANT_RECORD_SCHEMA,
    WORKSPACE_RECORD_SCHEMA,
    AliasRecord,
    EnvironmentRecord,
    LifecycleState,
    LogicalIdentity,
    PromotionRecord,
    RegistryRevision,
    SecurityDomainRecord,
    TenantRecord,
    WorkspaceRecord,
)
from etlantic.control_plane.registry_ops import (
    MemoryRetentionHook,
    RetentionHook,
    RevisionSearchHit,
    RevisionSearchPage,
    search_revisions,
)
from etlantic.control_plane.registry_protocols import (
    RegistryProvider,
    RevisionRegistry,
    TenantDirectory,
    WorkspaceDirectory,
)
from etlantic.control_plane.workspace_resources import (
    WORKSPACE_RESOURCE_RECORD_SCHEMA,
    MemoryWorkspaceResourceStore,
    WorkspaceResourceRecord,
    WorkspaceResourceStore,
    is_absolute_root_ref,
    reject_absolute_root_ref,
    reject_symlink_or_traversal,
    resolve_safe_root,
    validate_workspace_resource_record,
)

__all__ = [
    "ACCEPT_RECEIPT_SCHEMA",
    "ALIAS_RECORD_SCHEMA",
    "CACHE_INVALIDATION_EVENT_SCHEMA",
    "CONTROL_PLANE_CONTEXT_SCHEMA",
    "CONTROL_PLANE_ERROR_SCHEMA",
    "CONTROL_PLANE_EVENT_SCHEMA",
    "DEFINITION_KIND",
    "ENVIRONMENT_RECORD_SCHEMA",
    "IMPACT_EDGE_SCHEMA",
    "LOGICAL_IDENTITY_SCHEMA",
    "PLAN_OBSERVATION_RECORD_SCHEMA",
    "PROMOTION_RECORD_SCHEMA",
    "REDACTED",
    "REGISTRY_REVISION_SCHEMA",
    "RELIABILITY_OBSERVATION_RECORD_SCHEMA",
    "SCHEMA_OBSERVATION_RECORD_SCHEMA",
    "SECURITY_DOMAIN_RECORD_SCHEMA",
    "SSE_CURSOR_SCHEMA",
    "TENANT_RECORD_SCHEMA",
    "WORKSPACE_RECORD_SCHEMA",
    "WORKSPACE_RESOURCE_RECORD_SCHEMA",
    "AcceptReceipt",
    "AcceptResult",
    "AliasRecord",
    "Authorizer",
    "AuthzDecision",
    "CacheInvalidationEvent",
    "ControlPlaneContext",
    "ControlPlaneError",
    "ControlPlaneEvent",
    "CorrelationKey",
    "DefinitionRepository",
    "Disclosure",
    "EnvironmentRecord",
    "EnvironmentRef",
    "ErrorDisclosure",
    "EventStore",
    "HistoryStore",
    "IdempotencyKey",
    "ImpactEdge",
    "ImpactIndex",
    "LifecycleState",
    "LogicalIdentity",
    "MemoryAuthorizer",
    "MemoryDefinitionRepository",
    "MemoryEventStore",
    "MemoryHistoryStore",
    "MemoryImpactIndex",
    "MemoryRegistryProvider",
    "MemoryRetentionHook",
    "MemoryRevisionRegistry",
    "MemorySubmissionStore",
    "MemoryTenantDirectory",
    "MemoryWorkspaceDirectory",
    "MemoryWorkspaceResourceStore",
    "ObservationKind",
    "PlanObservationRecord",
    "Principal",
    "ProblemDetails",
    "PromotionRecord",
    "RegistryDefinitionRepository",
    "RegistryProvider",
    "RegistryRevision",
    "ReliabilityObservationRecord",
    "RetentionHook",
    "RevisionRegistry",
    "RevisionSearchHit",
    "RevisionSearchPage",
    "SchemaObservationRecord",
    "SecurityDomain",
    "SecurityDomainRecord",
    "SubmissionStore",
    "TenantDirectory",
    "TenantRecord",
    "TenantRef",
    "WorkspaceDirectory",
    "WorkspaceRecord",
    "WorkspaceRef",
    "WorkspaceResourceRecord",
    "WorkspaceResourceStore",
    "assert_history_metadata_only",
    "assert_no_secrets",
    "authorized_get_definition",
    "content_fingerprint",
    "is_absolute_root_ref",
    "map_deny_disclosure",
    "raise_for_deny",
    "redact_control_plane_payload",
    "redact_control_plane_text",
    "reject_absolute_root_ref",
    "reject_symlink_or_traversal",
    "require_authorized",
    "require_authorized_run",
    "resolve_safe_root",
    "search_revisions",
    "validate_workspace_resource_record",
]
