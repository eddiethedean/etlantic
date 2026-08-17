"""Discoverable resource-provider protocol (`etlantic.resource/1`)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from etlantic.capabilities import PluginCapabilities

RESOURCE_SCHEMA = "etlantic.resource/1"


@dataclass(frozen=True, slots=True)
class ResourceRequest:
    """Secret-free request for a compute/runtime resource."""

    kind: str
    identity: str = "default"
    required_capabilities: tuple[str, ...] = ()
    config_refs: Mapping[str, str] = field(default_factory=dict)
    secret_refs: Mapping[str, str] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": RESOURCE_SCHEMA,
            "kind": self.kind,
            "identity": self.identity,
            "required_capabilities": list(self.required_capabilities),
            "config_refs": dict(self.config_refs),
            "secret_refs": dict(self.secret_refs),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class ResourceHandle:
    identity: str
    kind: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity,
            "kind": self.kind,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class ResourceProviderInfo:
    name: str
    version: str
    package: str
    capabilities: PluginCapabilities | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "package": self.package,
            "capabilities": (
                self.capabilities.to_dict() if self.capabilities is not None else None
            ),
            "metadata": dict(self.metadata),
        }


@runtime_checkable
class ResourceProvider(Protocol):
    @property
    def info(self) -> ResourceProviderInfo: ...

    def capabilities(self) -> PluginCapabilities: ...

    def acquire(self, request: ResourceRequest) -> ResourceHandle: ...

    def release(self, handle: ResourceHandle) -> None: ...
