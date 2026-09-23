# pyright: reportUnknownVariableType=false
"""Spark session provider protocol (secrets resolved only at acquire)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from etlantic.capabilities import PluginCapabilities


class SessionOwnership(StrEnum):
    """Who owns the SparkSession lifecycle."""

    PROVIDER = "provider"
    SHARED = "shared"
    EXTERNAL = "external"


@dataclass(frozen=True, slots=True)
class SparkSessionRequest:
    """Secret-free request for a Spark session.

    Credentials and secret values are resolved by the provider at acquire time
    via ``secret_refs`` / runtime secret providers — never embedded here.
    """

    app_name: str = "etlantic"
    master: str | None = None  # e.g. local[*]; None → provider default
    execution_mode: str = "batch"  # batch | streaming
    required_capabilities: tuple[str, ...] = ()
    config_refs: Mapping[str, str] = field(default_factory=dict)
    secret_refs: Mapping[str, str] = field(default_factory=dict)
    enable_delta: bool = False
    checkpoint_root: str | None = None
    ownership: SessionOwnership = SessionOwnership.PROVIDER
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "app_name": self.app_name,
            "master": self.master,
            "execution_mode": self.execution_mode,
            "required_capabilities": list(self.required_capabilities),
            "config_refs": dict(self.config_refs),
            "secret_refs": dict(self.secret_refs),
            "enable_delta": self.enable_delta,
            "checkpoint_root": self.checkpoint_root,
            "ownership": self.ownership.value,
            "metadata": dict(self.metadata),
        }


@dataclass
class SparkSessionHandle:
    """Opaque handle for an acquired session (no credentials)."""

    identity: str
    ownership: SessionOwnership = SessionOwnership.PROVIDER
    app_name: str = "etlantic"
    master: str | None = None
    delta_enabled: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    # Live session object — plugin-private; never serialize.
    _session: Any = field(default=None, repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity,
            "ownership": self.ownership.value,
            "app_name": self.app_name,
            "master": self.master,
            "delta_enabled": self.delta_enabled,
            "metadata": dict(self.metadata),
        }

    @property
    def session(self) -> Any:
        return self._session


@dataclass(frozen=True, slots=True)
class SparkProviderInfo:
    """Discoverable provider metadata."""

    name: str
    version: str
    capabilities: PluginCapabilities | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "capabilities": (
                self.capabilities.to_dict() if self.capabilities is not None else None
            ),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class ResourceContext:
    """Runtime context for acquire/release (may carry secret resolvers)."""

    run_id: str
    pipeline_id: str
    plan_id: str
    security_domain: str = "default"
    resolve_secret: Any | None = None  # Callable[[str], str] | None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class SparkProvider(Protocol):
    """Supplies SparkSession lifecycle without embedding secrets in plans."""

    @property
    def info(self) -> SparkProviderInfo: ...

    def capabilities(self) -> PluginCapabilities: ...

    def acquire(
        self,
        request: SparkSessionRequest,
        context: ResourceContext,
    ) -> SparkSessionHandle: ...

    def release(
        self,
        handle: SparkSessionHandle,
        context: ResourceContext,
    ) -> None: ...
