# pyright: reportUnknownVariableType=false
"""Secret provider protocol and resolution context."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from etlantic.runtime.context import TrustedExecutionScope
from etlantic.secrets.ref import SecretRef
from etlantic.secrets.value import SecretValue


@dataclass(frozen=True, slots=True)
class SecretProviderCapabilities:
    """Declared secret-provider capabilities."""

    versions: bool = False
    aliases: bool = False
    binary_values: bool = False
    structured_values: bool = False
    dynamic_credentials: bool = False
    leases: bool = False
    renewal: bool = False
    revocation: bool = False
    in_memory_cache: bool = True
    async_native: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "versions": self.versions,
            "aliases": self.aliases,
            "binary_values": self.binary_values,
            "structured_values": self.structured_values,
            "dynamic_credentials": self.dynamic_credentials,
            "leases": self.leases,
            "renewal": self.renewal,
            "revocation": self.revocation,
            "in_memory_cache": self.in_memory_cache,
            "async_native": self.async_native,
        }


@dataclass(frozen=True, slots=True)
class SecretProviderDescriptor:
    """Installed secret provider metadata."""

    name: str
    engine: str
    version: str = "0.4.0"
    capabilities: SecretProviderCapabilities = field(
        default_factory=SecretProviderCapabilities
    )


@dataclass(frozen=True, slots=True)
class SecretResolutionContext:
    """Caller identity for a secret resolution (no values)."""

    run_id: str
    pipeline_id: str
    step_name: str | None = None
    attempt: int = 1
    purpose: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    trusted_scope: TrustedExecutionScope | None = None
    late_binding_authorized: bool = False


@dataclass(frozen=True, slots=True)
class SecretLease:
    """Provider-issued runtime value with a renewable, revocable lifetime."""

    lease_id: str
    value: SecretValue
    expires_at: datetime

    def __post_init__(self) -> None:
        if not self.lease_id.strip():
            raise ValueError("secret lease ID must be non-empty")
        if self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None:
            raise ValueError("secret lease expiry must include a timezone")


@runtime_checkable
class LeasedSecretProvider(Protocol):
    """Secret provider contract for short-lived credential leases."""

    async def acquire_lease(
        self, reference: SecretRef, context: SecretResolutionContext
    ) -> SecretLease: ...

    async def renew_lease(
        self, lease_id: str, context: SecretResolutionContext
    ) -> SecretLease:
        """Extend a lease, preserving its ID and credential version."""
        ...

    async def revoke_lease(
        self, lease_id: str, context: SecretResolutionContext
    ) -> None: ...


@runtime_checkable
class SecretAliasAuthorizer(Protocol):
    """Worker policy that approves runtime resolution of a moving alias.

    Implementations must evaluate the authenticated scope and reference on
    every call. The decision is deliberately made before the runtime cache is
    consulted, so a revoked grant cannot reuse an earlier cached value.
    """

    async def authorize_late_binding(
        self,
        reference: SecretRef,
        context: SecretResolutionContext,
    ) -> bool:
        """Return whether ``reference.version == 'current'`` may be resolved."""
        ...


@dataclass(frozen=True, slots=True)
class ProviderContext:
    """Context for provider lifespan."""

    run_id: str
    pipeline_id: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class SecretProvider(Protocol):
    """Protocol for runtime secret resolution."""

    @property
    def descriptor(self) -> SecretProviderDescriptor: ...

    async def resolve(
        self,
        reference: SecretRef,
        context: SecretResolutionContext,
    ) -> SecretValue: ...

    def lifespan(
        self, context: ProviderContext
    ) -> AbstractAsyncContextManager[None]: ...
