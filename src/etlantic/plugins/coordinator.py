"""Centralized profile-scoped plugin discovery."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from etlantic.diagnostics import Diagnostic, Severity
from etlantic.plugins.specs import PluginGroupSpec
from etlantic.profile import Profile
from etlantic.registry import RegistryBundle


def profile_plugin_key(profile: Profile) -> str:
    """Stable key for profile-scoped plugin discovery idempotency."""
    payload = {
        "name": profile.name,
        "security_mode": profile.security_mode,
        "plugin_allowlist": dict(profile.plugin_allowlist or {}),
        "require_plugin_probe": profile.require_plugin_probe,
    }
    return json.dumps(payload, sort_keys=True)


@dataclass
class PluginDiscoveryResult:
    """Outcome of discovering plugins for one profile."""

    dataframe_plugins: dict[str, Any] = field(default_factory=dict)
    sql_plugins: dict[str, Any] = field(default_factory=dict)
    spark_plugins: dict[str, Any] = field(default_factory=dict)
    spark_providers: dict[str, Any] = field(default_factory=dict)
    orchestrator_plugins: dict[str, Any] = field(default_factory=dict)
    scheduler_plugins: dict[str, Any] = field(default_factory=dict)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    trust_records: list[dict[str, Any]] = field(default_factory=list)


def _df_key(item: Any, plugin: Any) -> str:
    return str(getattr(getattr(plugin, "info", None), "engine", None) or item.name)


def _generic_key(item: Any, plugin: Any) -> str:
    return str(getattr(getattr(plugin, "info", None), "engine", None) or item.name)


def _provider_key(item: Any, plugin: Any) -> str:
    return str(getattr(getattr(plugin, "info", None), "name", None) or item.name)


_NON_ENGINE = frozenset({"local", "null", ""})


def should_discover_dataframe_plugins(dataframe_engine: str) -> bool:
    """True when a non-local dataframe engine is configured for planning."""
    return bool(dataframe_engine) and dataframe_engine not in _NON_ENGINE


def should_discover_sql_plugins(sql_engine: str | None) -> bool:
    """True when a non-local SQL engine is configured for planning."""
    return bool(sql_engine) and sql_engine not in _NON_ENGINE


def should_discover_spark_plugins(spark_engine: str | None) -> bool:
    """True when any Spark engine is configured for planning."""
    return bool(spark_engine)


def should_include_transform_compilers(
    dataframe_engine: str,
    spark_engine: str | None,
) -> bool:
    """True when a non-local dataframe or any Spark engine needs compilers."""
    return should_discover_dataframe_plugins(dataframe_engine) or (
        should_discover_spark_plugins(spark_engine)
    )


_RUNTIME_GROUPS: tuple[PluginGroupSpec, ...] = (
    PluginGroupSpec(
        entry_point_group="etlantic.dataframe_plugins",
        runtime_attr="dataframe_plugins",
        key_fn=_df_key,
        register_kind="dataframe",
    ),
    PluginGroupSpec(
        entry_point_group="etlantic.sql_plugins",
        runtime_attr="sql_plugins",
        key_fn=_generic_key,
        register_kind="sql",
    ),
    PluginGroupSpec(
        entry_point_group="etlantic.spark_plugins",
        runtime_attr="spark_plugins",
        key_fn=_generic_key,
        register_kind="spark",
    ),
    PluginGroupSpec(
        entry_point_group="etlantic.orchestrator_plugins",
        runtime_attr="orchestrator_plugins",
        key_fn=_generic_key,
        register_kind="orchestrator",
    ),
    PluginGroupSpec(
        entry_point_group="etlantic.scheduler_plugins",
        runtime_attr="scheduler_plugins",
        key_fn=None,
        register_kind="scheduler",
    ),
)


class PluginDiscoveryCoordinator:
    """Discover, authorize, and register plugins for a profile."""

    def discover_for_profile(
        self,
        profile: Profile,
        *,
        registry: RegistryBundle | None = None,
        register_to_registry: bool = True,
        include_runtime_groups: bool = True,
        include_transform_compilers: bool = False,
    ) -> PluginDiscoveryResult:
        from etlantic.plugin_lifecycle import discover_evaluate_authorize_load
        from etlantic.plugin_trust import (
            empty_production_allowlist_message,
            is_production_profile,
        )

        result = PluginDiscoveryResult()

        # Empty production allowlist is a profile-level failure — emit once and
        # skip per-group authorize loops that would otherwise spam PMPLUG401.
        if is_production_profile(profile) and not dict(profile.plugin_allowlist or {}):
            result.diagnostics.append(
                Diagnostic(
                    code="PMPLUG401",
                    severity=Severity.ERROR,
                    message=empty_production_allowlist_message(profile.name),
                    path=("profile", "plugin_allowlist"),
                    phase="plugin_authorize",
                )
            )
            if register_to_registry and registry is not None:
                builtins = frozenset({"local", "null", "env", "env-secrets"})
                for name in list(registry.plugins):
                    if name in builtins:
                        continue
                    descriptor = registry.plugins.pop(name)
                    if descriptor.engine and descriptor.engine in registry.engines:
                        still = any(
                            d.engine == descriptor.engine
                            for d in registry.plugins.values()
                        )
                        if not still:
                            registry.engines.pop(descriptor.engine, None)
            return result

        groups = list(_RUNTIME_GROUPS) if include_runtime_groups else []

        for spec in groups:
            try:
                lifecycle = discover_evaluate_authorize_load(
                    spec.entry_point_group,
                    profile=profile,
                    key_fn=spec.key_fn,
                )
                result.diagnostics.extend(lifecycle.diagnostics)
                result.trust_records.extend(lifecycle.trust_records)
                setattr(result, spec.runtime_attr, dict(lifecycle.loaded))
                if register_to_registry and registry is not None:
                    self._register_group(
                        registry,
                        spec.register_kind,
                        lifecycle.loaded,
                        profile=profile,
                    )
            except Exception as exc:
                result.diagnostics.append(
                    Diagnostic(
                        code="PMPLUG421",
                        severity=Severity.ERROR,
                        message=(
                            f"Plugin discovery failed for "
                            f"{spec.entry_point_group}: {exc}"
                        ),
                        path=("plugin", spec.entry_point_group),
                        phase="plugin_load",
                    )
                )

        if include_runtime_groups:
            try:
                providers = discover_evaluate_authorize_load(
                    "etlantic.spark_providers",
                    profile=profile,
                    key_fn=_provider_key,
                )
                result.diagnostics.extend(providers.diagnostics)
                result.trust_records.extend(providers.trust_records)
                result.spark_providers = dict(providers.loaded)
            except Exception as exc:
                result.diagnostics.append(
                    Diagnostic(
                        code="PMPLUG422",
                        severity=Severity.ERROR,
                        message=f"Spark provider discovery failed: {exc}",
                        path=("plugin", "spark_providers"),
                        phase="plugin_load",
                    )
                )

        if include_transform_compilers:
            from etlantic.transform.discovery import (
                TRANSFORM_COMPILER_ENTRY_POINT,
                register_discovered_compilers,
            )
            from etlantic.transform.discovery import (
                _key as transform_key,
            )

            try:
                compilers = discover_evaluate_authorize_load(
                    TRANSFORM_COMPILER_ENTRY_POINT,
                    profile=profile,
                    key_fn=transform_key,
                )
                result.diagnostics.extend(compilers.diagnostics)
                result.trust_records.extend(compilers.trust_records)
                if register_to_registry and registry is not None:
                    register_discovered_compilers(
                        registry, compilers=compilers.loaded, profile=profile
                    )
            except Exception as exc:
                result.diagnostics.append(
                    Diagnostic(
                        code="PMPLUG423",
                        severity=Severity.ERROR,
                        message=f"Transform compiler discovery failed: {exc}",
                        path=("plugin", "transform_compiler"),
                        phase="plugin_load",
                    )
                )

        return result

    def _register_group(
        self,
        registry: RegistryBundle,
        kind: str,
        loaded: dict[str, Any],
        *,
        profile: Profile,
    ) -> None:
        if kind == "dataframe":
            from etlantic.dataframe.discovery import register_discovered_plugins

            register_discovered_plugins(registry, plugins=loaded, profile=profile)
        elif kind == "sql":
            from etlantic.sql.discovery import (
                register_discovered_plugins as register_sql,
            )

            register_sql(registry, plugins=loaded, profile=profile)
        elif kind == "spark":
            from etlantic.spark.discovery import (
                register_discovered_plugins as register_spark,
            )

            register_spark(registry, plugins=loaded, profile=profile)
        elif kind == "orchestrator":
            from etlantic.orchestration.discovery import (
                register_discovered_plugins as register_orch,
            )

            register_orch(registry, plugins=loaded, profile=profile)
        elif kind == "scheduler":
            from etlantic.runtime.scheduler_discovery import (
                register_discovered_plugins as register_sched,
            )

            register_sched(registry, plugins=loaded, profile=profile)


def discover_planning_plugins(
    profile: Profile,
    registry: RegistryBundle,
    *,
    dataframe_engine: str,
    sql_engine: str | None,
    spark_engine: str | None,
) -> tuple[list[dict[str, Any]], list[Diagnostic]]:
    """Discover plugins required for planning based on profile engines."""
    coordinator = PluginDiscoveryCoordinator()
    include_compilers = should_include_transform_compilers(
        dataframe_engine, spark_engine
    )
    result = coordinator.discover_for_profile(
        profile,
        registry=registry,
        register_to_registry=True,
        include_runtime_groups=False,
        include_transform_compilers=False,
    )
    trust_records = list(result.trust_records)
    diagnostics = list(result.diagnostics)

    # Coordinator already fail-closed on empty production allowlist — do not
    # re-run per-engine authorize loops that would duplicate PMPLUG401.
    if any(d.code == "PMPLUG401" and d.severity is Severity.ERROR for d in diagnostics):
        return trust_records, diagnostics

    from etlantic.plugin_lifecycle import discover_evaluate_authorize_load

    if should_discover_dataframe_plugins(dataframe_engine):
        lifecycle = discover_evaluate_authorize_load(
            "etlantic.dataframe_plugins", profile=profile, key_fn=_df_key
        )
        trust_records.extend(lifecycle.trust_records)
        diagnostics.extend(lifecycle.diagnostics)
        from etlantic.dataframe.discovery import register_discovered_plugins

        register_discovered_plugins(registry, plugins=lifecycle.loaded, profile=profile)

    if should_discover_sql_plugins(sql_engine):
        lifecycle = discover_evaluate_authorize_load(
            "etlantic.sql_plugins", profile=profile, key_fn=_generic_key
        )
        trust_records.extend(lifecycle.trust_records)
        diagnostics.extend(lifecycle.diagnostics)
        from etlantic.sql.discovery import register_discovered_plugins as register_sql

        register_sql(registry, plugins=lifecycle.loaded, profile=profile)

    if should_discover_spark_plugins(spark_engine):
        lifecycle = discover_evaluate_authorize_load(
            "etlantic.spark_plugins", profile=profile, key_fn=_generic_key
        )
        trust_records.extend(lifecycle.trust_records)
        diagnostics.extend(lifecycle.diagnostics)
        from etlantic.spark.discovery import (
            register_discovered_plugins as register_spark,
        )

        register_spark(registry, plugins=lifecycle.loaded, profile=profile)

    if include_compilers:
        from etlantic.transform.discovery import (
            TRANSFORM_COMPILER_ENTRY_POINT,
            register_discovered_compilers,
        )
        from etlantic.transform.discovery import (
            _key as transform_key,
        )

        lifecycle = discover_evaluate_authorize_load(
            TRANSFORM_COMPILER_ENTRY_POINT,
            profile=profile,
            key_fn=transform_key,
        )
        trust_records.extend(lifecycle.trust_records)
        diagnostics.extend(lifecycle.diagnostics)
        register_discovered_compilers(
            registry, compilers=lifecycle.loaded, profile=profile
        )

    return trust_records, diagnostics
