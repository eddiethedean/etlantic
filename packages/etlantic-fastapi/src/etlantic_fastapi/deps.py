"""FastAPI dependencies for server-derived ControlPlaneContext."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from etlantic.control_plane import ControlPlaneContext, ControlPlaneError, Principal
from etlantic_fastapi.auth import PrincipalDependency
from fastapi import Depends, Request

if TYPE_CHECKING:
    from etlantic_fastapi.api import ETLanticAPI


def make_principal_dependency(api: ETLanticAPI) -> PrincipalDependency:
    return api.principal_dependency


def make_context_dependency(
    api: ETLanticAPI,
) -> Callable[..., ControlPlaneContext]:
    """Build a dependency that constructs server-derived context.

    Path tenant/workspace segments are never treated as authority. When a
    route exposes those path params for routing, callers should verify them
    against the returned context via :func:`assert_path_scope`.
    """
    principal_dep = api.principal_dependency

    def get_context(
        request: Request,
        principal: Principal = Depends(principal_dep),
    ) -> ControlPlaneContext:
        return api.context_factory(principal, request)

    return get_context


def assert_path_scope(
    ctx: ControlPlaneContext,
    *,
    tenant_id: str | None = None,
    workspace_id: str | None = None,
) -> None:
    """Reject path scope that does not match server-derived context (404).

    Spoofed path tenants must not disclose existence — map to opaque not_found.
    """
    if tenant_id is not None and tenant_id != ctx.tenant.tenant_id:
        raise ControlPlaneError.not_found("Resource not found")
    if workspace_id is not None and workspace_id != ctx.workspace.workspace_id:
        raise ControlPlaneError.not_found("Resource not found")


__all__ = [
    "assert_path_scope",
    "make_context_dependency",
    "make_principal_dependency",
]
