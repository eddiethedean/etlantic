"""Secret provider protocol and resolution context."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from pipelantic.secrets.ref import SecretRef
from pipelantic.secrets.value import SecretValue


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

    async def lifespan(self, context: ProviderContext) -> AsyncIterator[None]: ...
