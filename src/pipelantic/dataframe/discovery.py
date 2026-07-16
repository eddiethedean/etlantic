"""Entry-point discovery for dataframe plugins."""

from __future__ import annotations

from importlib.metadata import entry_points
from typing import Any

from pipelantic.dataframe.protocol import DataframePlugin
from pipelantic.registry import PluginDescriptor, RegistryBundle

DATAFRAME_PLUGIN_ENTRY_POINT = "pipelantic.dataframe_plugins"


def discover_dataframe_plugins() -> dict[str, DataframePlugin]:
    """Load dataframe plugins registered under the entry-point group.

    Returns a mapping of engine name → plugin instance. Missing or broken
    entry points are skipped (callers should fail closed at planning when the
    selected engine is absent).
    """
    found: dict[str, DataframePlugin] = {}
    try:
        eps = entry_points(group=DATAFRAME_PLUGIN_ENTRY_POINT)
    except TypeError:  # pragma: no cover - older importlib API
        eps = entry_points().get(DATAFRAME_PLUGIN_ENTRY_POINT, [])  # type: ignore[attr-defined]
    for ep in eps:
        try:
            factory = ep.load()
            plugin = factory() if callable(factory) else factory
            engine = getattr(getattr(plugin, "info", None), "engine", None) or ep.name
            found[str(engine)] = plugin
        except Exception:
            continue
    return found


def register_discovered_plugins(
    registry: RegistryBundle,
    *,
    plugins: dict[str, DataframePlugin] | None = None,
) -> dict[str, DataframePlugin]:
    """Register discovered dataframe plugins into a planning registry.

    Returns the plugin instances (live handles for the runtime; descriptors
    only are stored on the registry).
    """
    discovered = plugins if plugins is not None else discover_dataframe_plugins()
    for engine, plugin in discovered.items():
        info = plugin.info
        caps = info.capabilities
        registry.register_plugin(
            PluginDescriptor(
                name=info.name,
                kind="dataframe",
                version=info.version,
                engine=info.engine or engine,
                capabilities=caps,
                metadata={"protocol_version": info.protocol_version},
            )
        )
    return discovered


def load_dataframe_plugin(engine: str) -> DataframePlugin | None:
    """Return a discovered plugin for ``engine``, or None."""
    return discover_dataframe_plugins().get(engine)


def plugin_registry_snapshot() -> list[dict[str, Any]]:
    """Return serializable descriptors for discovered plugins."""
    out: list[dict[str, Any]] = []
    for plugin in discover_dataframe_plugins().values():
        out.append(plugin.info.to_dict())
    return out
