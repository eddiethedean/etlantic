"""Thin FastAPI adapter: control-plane API (CP1) + non-CP reference app.

Package version is **0.39.0** (CP1 gate-ready).
"""

from __future__ import annotations

from etlantic.service import AuthoringService, PolicyContext

__version__ = "0.41.0"
from etlantic_fastapi.api import ETLanticAPI, create_app, include_router
from etlantic_fastapi.auth import (
    ContextFactory,
    MembershipMap,
    PrincipalDependency,
    make_principal_from_header,
    membership_context_factory,
    oauth2_oidc_principal_hook,
    principal_dependency_from_callable,
    principal_from_header,
    static_context_factory,
)
from etlantic_fastapi.deps import assert_path_scope, make_context_dependency
from etlantic_fastapi.errors import (
    control_plane_error_handler,
    install_exception_handlers,
)
from etlantic_fastapi.landing_sensor import (
    LandingWatchSubmitter,
    local_files_binding_ref,
    make_testclient_submit_run,
)
from etlantic_fastapi.reference import create_reference_app
from etlantic_fastapi.schemas import (
    AcceptReceiptResponse,
    HealthResponse,
    ReadyResponse,
)
from etlantic_fastapi.sse import format_sse_message, sse_streaming_response

__all__ = [
    "AcceptReceiptResponse",
    "AuthoringService",
    "ContextFactory",
    "ETLanticAPI",
    "HealthResponse",
    "LandingWatchSubmitter",
    "MembershipMap",
    "PolicyContext",
    "PrincipalDependency",
    "ReadyResponse",
    "__version__",
    "assert_path_scope",
    "control_plane_error_handler",
    "create_app",
    "create_reference_app",
    "format_sse_message",
    "include_router",
    "install_exception_handlers",
    "local_files_binding_ref",
    "make_context_dependency",
    "make_principal_from_header",
    "make_testclient_submit_run",
    "membership_context_factory",
    "oauth2_oidc_principal_hook",
    "principal_dependency_from_callable",
    "principal_from_header",
    "sse_streaming_response",
    "static_context_factory",
]
