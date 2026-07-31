"""Authentication adapters for the control-plane FastAPI package.

Apps inject a principal dependency. Path/header tenant claims are never
authority — only the server-derived :class:`ControlPlaneContext` is.

Optional OAuth2/OIDC: install ``fastapi`` security dependencies in the host
application and pass the resulting principal into
:func:`principal_dependency_from_callable`. This package does not bundle an
IdP client; the hook shape is documented for host composition.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any
from uuid import uuid4

from etlantic.control_plane import (
    ControlPlaneContext,
    ControlPlaneError,
    CorrelationKey,
    EnvironmentRef,
    IdempotencyKey,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from fastapi import Request

PrincipalDependency = Callable[..., Principal]
ContextFactory = Callable[[Principal, Request], ControlPlaneContext]

# Membership map: subject -> (tenant_id, workspace_id, environment, security_domain)
MembershipMap = Mapping[str, tuple[str, str, str, str]]


def principal_from_header(request: Request) -> Principal:
    """Demo/test principal adapter reading an opaque ``X-Principal`` header.

    Production hosts should replace this with OAuth2/OIDC or mTLS mapping.
    """
    subject = request.headers.get("X-Principal")
    if not subject:
        raise ControlPlaneError.unauthorized(
            "Missing authenticated principal (X-Principal)"
        )
    issuer = request.headers.get("X-Principal-Issuer")
    kind_raw = request.headers.get("X-Principal-Kind", "human")
    kind = kind_raw if kind_raw in ("human", "workload", "service") else "human"
    return Principal(subject=subject, issuer=issuer, kind=kind)  # type: ignore[arg-type]


def make_principal_from_header(*, header: str = "X-Principal") -> PrincipalDependency:
    """Build a principal dependency that reads ``header`` from the request."""

    def dependency(request: Request) -> Principal:
        subject = request.headers.get(header)
        if not subject:
            raise ControlPlaneError.unauthorized(
                f"Missing authenticated principal ({header})"
            )
        issuer = request.headers.get("X-Principal-Issuer")
        kind_raw = request.headers.get("X-Principal-Kind", "human")
        kind = kind_raw if kind_raw in ("human", "workload", "service") else "human"
        return Principal(subject=subject, issuer=issuer, kind=kind)  # type: ignore[arg-type]

    return dependency


def principal_dependency_from_callable(
    resolver: Callable[[Request], Principal],
) -> PrincipalDependency:
    """Wrap a host-defined principal resolver as a FastAPI dependency."""

    def dependency(request: Request) -> Principal:
        return resolver(request)

    return dependency


def oauth2_oidc_principal_hook(
    *,
    token_claims: Mapping[str, Any],
    subject_claim: str = "sub",
    issuer_claim: str = "iss",
) -> Principal:
    """Placeholder OAuth2/OIDC claim → Principal mapping for host adapters.

    Hosts that validate JWTs (or introspect tokens) via FastAPI security
    dependencies can call this after claims are verified. This function does
    not validate signatures or contact an IdP.
    """
    subject = token_claims.get(subject_claim)
    if not subject:
        raise ControlPlaneError.unauthorized("OIDC token missing subject claim")
    issuer = token_claims.get(issuer_claim)
    return Principal(
        subject=str(subject),
        issuer=str(issuer) if issuer is not None else None,
        kind="human",
    )


def membership_context_factory(
    membership: MembershipMap,
) -> ContextFactory:
    """Build a context factory that maps principal subjects via membership."""

    def factory(principal: Principal, request: Request) -> ControlPlaneContext:
        try:
            tenant_id, workspace_id, environment, domain = membership[principal.subject]
        except KeyError as exc:
            raise ControlPlaneError.unauthorized(
                "Principal is not mapped to a tenant/workspace"
            ) from exc
        corr = request.headers.get("X-Correlation-ID") or str(uuid4())
        idem = request.headers.get("Idempotency-Key")
        return ControlPlaneContext(
            principal=principal,
            tenant=TenantRef(tenant_id=tenant_id),
            workspace=WorkspaceRef(tenant_id=tenant_id, workspace_id=workspace_id),
            environment=EnvironmentRef(name=environment),
            security_domain=SecurityDomain(domain_id=domain),
            correlation_key=CorrelationKey(value=corr),
            idempotency_key=IdempotencyKey(value=idem) if idem else None,
            request_id=request.headers.get("X-Request-ID"),
        )

    return factory


def static_context_factory(
    *,
    tenant_id: str,
    workspace_id: str,
    environment: str = "development",
    security_domain: str = "default",
) -> ContextFactory:
    """Fixed-scope context factory for single-tenant demos and unit tests."""

    def factory(principal: Principal, request: Request) -> ControlPlaneContext:
        corr = request.headers.get("X-Correlation-ID") or str(uuid4())
        idem = request.headers.get("Idempotency-Key")
        return ControlPlaneContext(
            principal=principal,
            tenant=TenantRef(tenant_id=tenant_id),
            workspace=WorkspaceRef(tenant_id=tenant_id, workspace_id=workspace_id),
            environment=EnvironmentRef(name=environment),
            security_domain=SecurityDomain(domain_id=security_domain),
            correlation_key=CorrelationKey(value=corr),
            idempotency_key=IdempotencyKey(value=idem) if idem else None,
            request_id=request.headers.get("X-Request-ID"),
        )

    return factory


__all__ = [
    "ContextFactory",
    "MembershipMap",
    "PrincipalDependency",
    "make_principal_from_header",
    "membership_context_factory",
    "oauth2_oidc_principal_hook",
    "principal_dependency_from_callable",
    "principal_from_header",
    "static_context_factory",
]
