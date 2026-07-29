"""Entry-point discovery for direct-execution scheduler plugins."""

from __future__ import annotations

import warnings
from typing import Any

from etlantic.plugin_lifecycle import discover_evaluate_authorize_load
from etlantic.profile import Profile
from etlantic.registry import PluginDescriptor, RegistryBundle
from etlantic.runtime.scheduler import (
    SCHEDULER_PROTOCOL,
    ExecutionScheduler,
    LocalScheduler,
)

SCHEDULER_PLUGIN_ENTRY_POINT = "etlantic.scheduler_plugins"

# Compile-only engines must never be treated as ExecutionScheduler names.
_COMPILE_ONLY = frozenset({"airflow"})


def discover_scheduler_plugins(
    *,
    profile: Profile | None = None,
) -> dict[str, ExecutionScheduler]:
    """Discover scheduler plugins with authorize-before-load (0.20)."""

    def _key(item: Any, plugin: Any) -> str:
        name = getattr(getattr(plugin, "info", None), "name", None) or item.name
        key = str(name)
        if key in _COMPILE_ONLY:
            raise RuntimeError(
                f"Ignoring scheduler entry point {item.name!r}: {key!r} is a "
                "compile-only orchestrator name, not an ExecutionScheduler."
            )
        return key

    result = discover_evaluate_authorize_load(
        SCHEDULER_PLUGIN_ENTRY_POINT,
        profile=profile,
        key_fn=_key,
    )
    # Surface compile-only skips as warnings when load failed that way.
    for diag in result.diagnostics:
        if "compile-only" in diag.message:
            warnings.warn(diag.message, RuntimeWarning, stacklevel=2)
    return result.loaded  # type: ignore[return-value]


def register_discovered_plugins(
    registry: RegistryBundle,
    *,
    plugins: dict[str, ExecutionScheduler] | None = None,
    profile: Profile | None = None,
) -> dict[str, ExecutionScheduler]:
    """Register discovered scheduler plugins into a planning registry."""
    from etlantic.plugin_trust import descriptor_metadata_for_plugin

    discovered = (
        plugins if plugins is not None else discover_scheduler_plugins(profile=profile)
    )
    for name, plugin in discovered.items():
        info = plugin.info
        registry.register_plugin(
            PluginDescriptor(
                name=info.name,
                kind="scheduler",
                version=info.version,
                engine=info.name or name,
                capabilities={
                    "direct_execution": info.direct_execution,
                    "external_compilation": info.external_compilation,
                },
                metadata=descriptor_metadata_for_plugin(
                    plugin,
                    info,
                    extra={"protocol_version": info.scheduler_protocol},
                ),
            )
        )
    return discovered


def builtin_local_scheduler() -> LocalScheduler:
    """Return the built-in zero-install local scheduler."""
    return LocalScheduler()


def resolve_scheduler(
    name: str,
    *,
    plugins: dict[str, ExecutionScheduler] | None = None,
    profile: Profile | None = None,
) -> ExecutionScheduler:
    """Resolve a scheduler by profile/orchestrator name (fail closed)."""
    key = str(name or "local").strip() or "local"
    if key in _COMPILE_ONLY:
        from etlantic.exceptions import ETLanticError

        raise ETLanticError(
            f"Orchestrator {key!r} is a compile target (etlantic.orchestration/1), "
            "not a direct-execution scheduler. Use LocalScheduler or an "
            f"{SCHEDULER_PROTOCOL} plugin such as prefect, or compile with "
            "`etlantic compile --target airflow`."
        )
    if key == "local":
        return builtin_local_scheduler()
    discovered = (
        plugins if plugins is not None else discover_scheduler_plugins(profile=profile)
    )
    plugin = discovered.get(key)
    if plugin is None:
        from etlantic.exceptions import ETLanticError

        raise ETLanticError(
            f"No ExecutionScheduler named {key!r} is installed. Install the "
            f"optional plugin (for example etlantic-prefect) or set "
            "Profile(orchestrator='local')."
        )
    return plugin


def load_scheduler_plugin(
    name: str,
    *,
    profile: Profile | None = None,
) -> ExecutionScheduler | None:
    """Return a discovered scheduler plugin for ``name``, or None."""
    if name == "local":
        return builtin_local_scheduler()
    return discover_scheduler_plugins(profile=profile).get(name)


def plugin_registry_snapshot(
    *,
    profile: Profile | None = None,
) -> list[dict[str, Any]]:
    """Return serializable descriptors for discovered scheduler plugins."""
    local = builtin_local_scheduler()
    items = [local.info.to_dict()]
    items.extend(
        plugin.info.to_dict()
        for plugin in discover_scheduler_plugins(profile=profile).values()
    )
    return items
