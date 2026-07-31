"""Connector entry-point discovery (thin wrappers over plugin_lifecycle)."""

from __future__ import annotations

from typing import Any

from etlantic.diagnostics import Diagnostic
from etlantic.plugin_lifecycle import (
    DiscoveredPlugin,
    PluginLifecycleResult,
    discover_entry_points,
    discover_evaluate_authorize_load,
)
from etlantic.profile import Profile

SOURCE_CONNECTORS_GROUP = "etlantic.source_connectors"
SINK_CONNECTORS_GROUP = "etlantic.sink_connectors"
STORAGE_CONNECTORS_GROUP = "etlantic.storage_connectors"

CONNECTOR_ENTRY_POINT_GROUPS: tuple[str, ...] = (
    SOURCE_CONNECTORS_GROUP,
    SINK_CONNECTORS_GROUP,
    STORAGE_CONNECTORS_GROUP,
)


def discover_source_connectors() -> tuple[list[DiscoveredPlugin], list[Diagnostic]]:
    """Discover ``etlantic.source_connectors`` without importing factories."""
    return discover_entry_points(SOURCE_CONNECTORS_GROUP)


def discover_sink_connectors() -> tuple[list[DiscoveredPlugin], list[Diagnostic]]:
    """Discover ``etlantic.sink_connectors`` without importing factories."""
    return discover_entry_points(SINK_CONNECTORS_GROUP)


def discover_storage_connectors() -> tuple[list[DiscoveredPlugin], list[Diagnostic]]:
    """Discover ``etlantic.storage_connectors`` without importing factories."""
    return discover_entry_points(STORAGE_CONNECTORS_GROUP)


def _ensure_connector_instances(loaded: dict[str, Any]) -> dict[str, Any]:
    """Instantiate remaining callable factories (match coordinator load path)."""
    instances: dict[str, Any] = {}
    for key, plugin in loaded.items():
        if isinstance(plugin, type) or (
            callable(plugin) and not hasattr(plugin, "info")
        ):
            instances[key] = plugin()
        else:
            instances[key] = plugin
    return instances


def discover_connectors_for_profile(
    profile: Profile | None,
    *,
    groups: tuple[str, ...] | None = None,
    run_id: str = "plan",
) -> dict[str, PluginLifecycleResult]:
    """Discover → evaluate → authorize → load connector groups for a profile."""
    results: dict[str, PluginLifecycleResult] = {}
    for group in groups or CONNECTOR_ENTRY_POINT_GROUPS:
        result = discover_evaluate_authorize_load(
            group,
            profile=profile,
            run_id=run_id,
            key_fn=connector_key,
        )
        result.loaded = _ensure_connector_instances(dict(result.loaded))
        results[group] = result
    return results


def connector_key(item: DiscoveredPlugin, plugin: Any) -> str:
    """Stable registry key for a loaded connector factory/instance."""
    info = getattr(plugin, "info", None)
    if callable(info):
        try:
            declared = info()
            name = getattr(declared, "name", None) or getattr(
                declared, "provider", None
            )
            if name:
                return str(name)
        except Exception:
            pass
    provider = getattr(plugin, "provider", None) or getattr(plugin, "name", None)
    if provider:
        return str(provider)
    return item.name


__all__ = [
    "CONNECTOR_ENTRY_POINT_GROUPS",
    "SINK_CONNECTORS_GROUP",
    "SOURCE_CONNECTORS_GROUP",
    "STORAGE_CONNECTORS_GROUP",
    "connector_key",
    "discover_connectors_for_profile",
    "discover_sink_connectors",
    "discover_source_connectors",
    "discover_storage_connectors",
]
