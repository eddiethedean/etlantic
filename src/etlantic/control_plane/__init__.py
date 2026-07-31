"""Control-plane identity, authorization, and scoped store protocols (CP1).

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
)
from etlantic.control_plane.errors import (
    CONTROL_PLANE_ERROR_SCHEMA,
    ControlPlaneError,
    ErrorDisclosure,
    ProblemDetails,
)
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

__all__ = [
    "ACCEPT_RECEIPT_SCHEMA",
    "CONTROL_PLANE_CONTEXT_SCHEMA",
    "CONTROL_PLANE_ERROR_SCHEMA",
    "CONTROL_PLANE_EVENT_SCHEMA",
    "REDACTED",
    "SSE_CURSOR_SCHEMA",
    "AcceptReceipt",
    "Authorizer",
    "AuthzDecision",
    "ControlPlaneContext",
    "ControlPlaneError",
    "ControlPlaneEvent",
    "CorrelationKey",
    "DefinitionRepository",
    "Disclosure",
    "EnvironmentRef",
    "ErrorDisclosure",
    "EventStore",
    "IdempotencyKey",
    "MemoryAuthorizer",
    "MemoryDefinitionRepository",
    "MemoryEventStore",
    "MemorySubmissionStore",
    "Principal",
    "ProblemDetails",
    "SecurityDomain",
    "SubmissionStore",
    "TenantRef",
    "WorkspaceRef",
    "assert_no_secrets",
    "authorized_get_definition",
    "map_deny_disclosure",
    "raise_for_deny",
    "redact_control_plane_payload",
    "redact_control_plane_text",
    "require_authorized",
]
