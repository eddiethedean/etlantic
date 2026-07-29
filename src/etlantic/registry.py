"""Scoped registries for plugins, implementations, bindings, and providers.

Registries belong to a PlanningContext instance (ADR-004), never process globals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from etlantic._version import __version__
from etlantic.capabilities import PluginCapabilities
from etlantic.diagnostics import Diagnostic
from etlantic.profile import Profile, resolve_profile
from etlantic.quality.model import PORTABLE_QUALITY_CAPABILITIES
from etlantic.reliability import WRITE_CAPABILITY_EXTRAS
from etlantic.secrets import SecretRef


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
    kind: str = "native"  # "native" | "portable_compiled"
    ir_fingerprint: str | None = None
    compiler_name: str | None = None
    compiler_version: str | None = None
    compiler_protocol: str | None = None
    requirements: dict[str, list[str]] = field(default_factory=dict)
    support_summary: dict[str, Any] = field(default_factory=dict)
    fallback_reason: str | None = None
    # Bounded canonical dtcs.transform-plan/2 (data-only); never live objects.
    portable_plan: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize implementation descriptor."""
        return {
            "transformation_id": self.transformation_id,
            "engine": self.engine,
            "identity": self.identity,
            "is_async": self.is_async,
            "kind": self.kind,
            "ir_fingerprint": self.ir_fingerprint,
            "compiler_name": self.compiler_name,
            "compiler_version": self.compiler_version,
            "compiler_protocol": self.compiler_protocol,
            "requirements": {
                key: list(values) for key, values in self.requirements.items()
            },
            "support_summary": dict(self.support_summary),
            "fallback_reason": self.fallback_reason,
            "portable_plan": dict(self.portable_plan) if self.portable_plan else None,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImplementationDescriptor:
        """Deserialize implementation descriptor."""
        requirements_raw = data.get("requirements") or {}
        return cls(
            transformation_id=str(data["transformation_id"]),
            engine=str(data["engine"]),
            identity=str(data["identity"]),
            is_async=bool(data.get("is_async", False)),
            kind=str(data.get("kind") or "native"),
            ir_fingerprint=data.get("ir_fingerprint"),
            compiler_name=data.get("compiler_name"),
            compiler_version=data.get("compiler_version"),
            compiler_protocol=data.get("compiler_protocol"),
            requirements={
                str(k): [str(x) for x in (v or [])]
                for k, v in dict(requirements_raw).items()
            },
            support_summary=dict(data.get("support_summary") or {}),
            fallback_reason=data.get("fallback_reason"),
            portable_plan=(
                dict(data["portable_plan"])
                if isinstance(data.get("portable_plan"), dict)
                else None
            ),
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
        invalid_row_separation=True,
        extras=frozenset({"python", "records"})
        | PORTABLE_QUALITY_CAPABILITIES
        | WRITE_CAPABILITY_EXTRAS,
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
            version=__version__,
            engine="local",
            capabilities=local_caps,
        )
    )
    registry.register_plugin(
        PluginDescriptor(
            name="null",
            kind="runtime",
            version=__version__,
            engine="null",
            capabilities=null_caps,
        )
    )
    registry.register_plugin(
        PluginDescriptor(
            name="env-secrets",
            kind="secret_provider",
            version=__version__,
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
    plugin_trust_records: list[dict[str, Any]] = field(default_factory=list)
    plugin_discovery_diagnostics: tuple[Diagnostic, ...] = ()

    @classmethod
    def create(
        cls,
        profile: str | Profile | None = None,
        *,
        registry: RegistryBundle | None = None,
        required_capabilities: list[str] | None = None,
        allow_capability_fallback: bool = False,
        allow_adhoc_profile: bool = False,
    ) -> PlanningContext:
        """Build a planning context from a profile name/object.

        When a non-local ``dataframe_engine`` is configured and no custom
        registry is supplied, discovered entry-point plugins are registered
        onto a stub registry so plan-only paths work without a runtime.
        When a non-local ``sql_engine`` is configured, discovered SQL plugins
        are registered the same way. When ``spark_engine`` is set, discovered
        Spark plugins are registered the same way.
        """
        resolved = (
            profile
            if isinstance(profile, Profile)
            else resolve_profile(profile, allow_adhoc_profile=allow_adhoc_profile)
        )
        caps = list(required_capabilities) if required_capabilities is not None else []
        from etlantic.engines import get_engine_registry

        engine_registry = get_engine_registry()
        if not caps:
            caps = engine_registry.default_capabilities(resolved)
        engine = resolved.dataframe_engine or "local"
        sql_engine = resolved.sql_engine
        spark_engine = resolved.spark_engine
        reg = registry if registry is not None else builtin_stub_registry()
        trust_records: list[dict[str, Any]] = []
        plan_diags: tuple[Diagnostic, ...] = ()

        from etlantic.plugins.coordinator import profile_plugin_key

        planning_key = profile_plugin_key(resolved)
        last_key = getattr(reg, "_etlantic_planning_profile_key", None)

        def _clear_non_builtin_plugins() -> None:
            builtins = frozenset({"local", "null", "env", "env-secrets"})
            for name in list(reg.plugins):
                if name in builtins:
                    continue
                descriptor = reg.plugins.pop(name)
                if descriptor.engine and descriptor.engine in reg.engines:
                    still = any(
                        d.engine == descriptor.engine for d in reg.plugins.values()
                    )
                    if not still:
                        reg.engines.pop(descriptor.engine, None)
                if name in reg.secret_providers:
                    reg.secret_providers.pop(name, None)

        def _needs_planning_discovery() -> bool:
            from etlantic.plugins.coordinator import (
                should_discover_dataframe_plugins,
                should_discover_spark_plugins,
                should_discover_sql_plugins,
            )

            if registry is None:
                return True
            if last_key is not None and last_key != planning_key:
                return True
            if should_discover_dataframe_plugins(engine) and engine not in reg.engines:
                return True
            if (
                should_discover_sql_plugins(sql_engine)
                and sql_engine not in reg.engines
            ):
                return True
            if should_discover_spark_plugins(spark_engine):
                assert spark_engine is not None
                if spark_engine in reg.engines:
                    return False
                # First-party spark/pyspark aliases share registration.
                aliased = spark_engine in {"pyspark", "spark"} and (
                    "pyspark" in reg.engines or "spark" in reg.engines
                )
                return not aliased
            return False

        if _needs_planning_discovery():
            from etlantic.plugins.coordinator import discover_planning_plugins

            if (
                registry is not None
                and last_key is not None
                and last_key != planning_key
            ):
                _clear_non_builtin_plugins()
            trust_records, discovered = discover_planning_plugins(
                resolved,
                reg,
                dataframe_engine=engine,
                sql_engine=sql_engine,
                spark_engine=spark_engine,
            )
            plan_diags = tuple(discovered)
            reg._etlantic_planning_profile_key = planning_key  # type: ignore[attr-defined]
        elif last_key is None:
            reg._etlantic_planning_profile_key = planning_key  # type: ignore[attr-defined]

        # Prefer capabilities advertised by the selected engine (e.g. lazy)
        # rather than inventing requirements from first-party engine names.
        def _augment_from_engine(name: str | None) -> None:
            if not name:
                return
            available = reg.engines.get(name)
            if available is None:
                return
            if available.supports("lazy") and "lazy" not in caps:
                caps.append("lazy")

        _augment_from_engine(engine if engine != "local" else None)
        _augment_from_engine(sql_engine)
        _augment_from_engine(spark_engine)

        return cls(
            profile=resolved,
            registry=reg,
            required_capabilities=caps,
            allow_capability_fallback=allow_capability_fallback,
            plugin_trust_records=trust_records,
            plugin_discovery_diagnostics=plan_diags,
        )
