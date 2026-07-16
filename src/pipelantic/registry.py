"""Scoped registries for plugins, implementations, bindings, and providers.

Registries belong to a PlanningContext instance (ADR-004), never process globals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pipelantic.capabilities import PluginCapabilities
from pipelantic.profile import Profile, resolve_profile
from pipelantic.secrets import SecretRef


@dataclass(frozen=True, slots=True)
class PluginDescriptor:
    """Installed plugin metadata for planning (no live handles)."""

    name: str
    kind: str
    version: str = "0.0.0"
    engine: str | None = None
    capabilities: PluginCapabilities | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize plugin descriptor."""
        return {
            "name": self.name,
            "kind": self.kind,
            "version": self.version,
            "engine": self.engine,
            "capabilities": (
                self.capabilities.to_dict() if self.capabilities else None
            ),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class ImplementationDescriptor:
    """Resolved implementation selection for a transformation/engine."""

    transformation_id: str
    engine: str
    identity: str
    is_async: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize implementation descriptor."""
        return {
            "transformation_id": self.transformation_id,
            "engine": self.engine,
            "identity": self.identity,
            "is_async": self.is_async,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImplementationDescriptor:
        """Deserialize implementation descriptor."""
        return cls(
            transformation_id=str(data["transformation_id"]),
            engine=str(data["engine"]),
            identity=str(data["identity"]),
            is_async=bool(data.get("is_async", False)),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True, slots=True)
class BindingDescriptor:
    """Logical binding resolved to a provider descriptor (not credentials)."""

    binding: str
    provider: str
    kind: str = "resource"
    location: str | None = None
    secret_ref: SecretRef | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize binding descriptor."""
        return {
            "binding": self.binding,
            "provider": self.provider,
            "kind": self.kind,
            "location": self.location,
            "secret_ref": self.secret_ref.to_dict() if self.secret_ref else None,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BindingDescriptor:
        """Deserialize binding descriptor."""
        secret_raw = data.get("secret_ref")
        return cls(
            binding=str(data["binding"]),
            provider=str(data["provider"]),
            kind=str(data.get("kind") or "resource"),
            location=data.get("location"),
            secret_ref=(
                SecretRef.from_dict(secret_raw)
                if isinstance(secret_raw, dict)
                else None
            ),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass
class RegistryBundle:
    """Mutable, scoped registries used during planning."""

    plugins: dict[str, PluginDescriptor] = field(default_factory=dict)
    implementations: dict[str, ImplementationDescriptor] = field(default_factory=dict)
    bindings: dict[str, BindingDescriptor] = field(default_factory=dict)
    secret_providers: dict[str, PluginDescriptor] = field(default_factory=dict)
    engines: dict[str, PluginCapabilities] = field(default_factory=dict)

    def register_plugin(self, descriptor: PluginDescriptor) -> None:
        """Register a plugin descriptor."""
        self.plugins[descriptor.name] = descriptor
        if descriptor.capabilities is not None and descriptor.engine:
            self.engines[descriptor.engine] = descriptor.capabilities
        if descriptor.kind == "secret_provider":
            self.secret_providers[descriptor.name] = descriptor

    def register_binding(self, descriptor: BindingDescriptor) -> None:
        """Register a binding descriptor."""
        self.bindings[descriptor.binding] = descriptor

    def register_implementation(self, descriptor: ImplementationDescriptor) -> None:
        """Register an implementation descriptor keyed by transform+engine."""
        key = f"{descriptor.transformation_id}::{descriptor.engine}"
        self.implementations[key] = descriptor


def builtin_stub_registry() -> RegistryBundle:
    """Return a registry with in-tree stub plugins for local planning tests.

    ``local`` is the in-process Python-records path (not a dataframe engine).
    Polars/Pandas plugins register themselves via entry points or explicit
    ``register_plugin`` calls when installed.
    """
    registry = RegistryBundle()
    local_caps = PluginCapabilities(
        engine="local",
        async_execution=True,
        dataframe=False,
        eager=True,
        lazy=False,
        schema_inspection=True,
        cancellation=True,
        extras=frozenset({"python", "records"}),
    )
    null_caps = PluginCapabilities(
        engine="null",
        dataframe=False,
        eager=True,
        extras=frozenset({"noop"}),
    )
    registry.register_plugin(
        PluginDescriptor(
            name="local",
            kind="runtime",
            version="0.6.0",
            engine="local",
            capabilities=local_caps,
        )
    )
    registry.register_plugin(
        PluginDescriptor(
            name="null",
            kind="runtime",
            version="0.6.0",
            engine="null",
            capabilities=null_caps,
        )
    )
    registry.register_plugin(
        PluginDescriptor(
            name="env-secrets",
            kind="secret_provider",
            version="0.6.0",
            engine="env",
            capabilities=PluginCapabilities(
                engine="env",
                secret_provider=True,
                dataframe=False,
                eager=False,
            ),
        )
    )
    return registry


@dataclass
class PlanningContext:
    """Scoped planning inputs: profile + registries (no live resources)."""

    profile: Profile
    registry: RegistryBundle = field(default_factory=builtin_stub_registry)
    required_capabilities: list[str] = field(default_factory=list)
    allow_capability_fallback: bool = False
    fallback_engine: str | None = "null"
    selection: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        profile: str | Profile | None = None,
        *,
        registry: RegistryBundle | None = None,
        required_capabilities: list[str] | None = None,
        allow_capability_fallback: bool = False,
    ) -> PlanningContext:
        """Build a planning context from a profile name/object.

        When ``dataframe_engine`` is ``polars`` or ``pandas`` and no custom
        registry is supplied, discovered entry-point plugins are registered
        onto a stub registry so plan-only paths work without a runtime.
        When ``sql_engine`` is ``sql``, discovered SQL plugins are registered
        the same way.
        """
        resolved = resolve_profile(profile)
        caps = list(required_capabilities) if required_capabilities is not None else []
        engine = resolved.dataframe_engine or "local"
        sql_engine = resolved.sql_engine
        if not caps and engine in {"polars", "pandas"}:
            caps = ["dataframe", "eager"]
            if engine == "polars":
                caps.append("lazy")
        if not caps and sql_engine == "sql":
            caps = ["sql", "transactions", "sql_catalog_inspect"]
            caps.extend(resolved.required_sql_capabilities)
        reg = registry
        if reg is None:
            reg = builtin_stub_registry()
            if engine in {"polars", "pandas"}:
                from pipelantic.dataframe.discovery import register_discovered_plugins

                register_discovered_plugins(reg)
            if sql_engine == "sql":
                from pipelantic.sql.discovery import (
                    register_discovered_plugins as register_sql,
                )

                register_sql(reg)
        return cls(
            profile=resolved,
            registry=reg,
            required_capabilities=caps,
            allow_capability_fallback=allow_capability_fallback,
        )
