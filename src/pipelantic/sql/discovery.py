"""Entry-point discovery for SQL plugins."""

from __future__ import annotations

import logging
import warnings
from importlib.metadata import entry_points
from typing import Any

from pipelantic.registry import PluginDescriptor, RegistryBundle
from pipelantic.sql.protocol import SqlPlugin

SQL_PLUGIN_ENTRY_POINT = "pipelantic.sql_plugins"
_LOG = logging.getLogger(__name__)


def discover_sql_plugins() -> dict[str, SqlPlugin]:
    """Load SQL plugins registered under the entry-point group."""
    found: dict[str, SqlPlugin] = {}
    try:
        eps = entry_points(group=SQL_PLUGIN_ENTRY_POINT)
    except TypeError:  # pragma: no cover
        eps = entry_points().get(SQL_PLUGIN_ENTRY_POINT, [])  # type: ignore[attr-defined]
    for ep in eps:
        try:
            factory = ep.load()
            plugin = factory() if callable(factory) else factory
            engine = getattr(getattr(plugin, "info", None), "engine", None) or ep.name
            found[str(engine)] = plugin
        except Exception as exc:
            msg = f"Failed to load SQL plugin entry point {ep.name!r}: {exc}"
            _LOG.warning(msg)
            warnings.warn(msg, RuntimeWarning, stacklevel=2)
            continue
    return found


def register_discovered_plugins(
    registry: RegistryBundle,
    *,
    plugins: dict[str, SqlPlugin] | None = None,
) -> dict[str, SqlPlugin]:
    """Register discovered SQL plugins into a planning registry."""
    discovered = plugins if plugins is not None else discover_sql_plugins()
    for engine, plugin in discovered.items():
        info = plugin.info
        caps = info.capabilities or plugin.capabilities()
        registry.register_plugin(
            PluginDescriptor(
                name=info.name,
                kind="sql",
                version=info.version,
                engine=info.engine or engine,
                capabilities=caps,
                metadata={
                    "protocol_version": info.protocol_version,
                    "dialect": info.dialect,
                },
            )
        )
    return discovered


def load_sql_plugin(engine: str = "sql") -> SqlPlugin | None:
    """Return a discovered plugin for ``engine``, or None."""
    return discover_sql_plugins().get(engine)


def plugin_registry_snapshot() -> list[dict[str, Any]]:
    """Return serializable descriptors for discovered SQL plugins."""
    return [plugin.info.to_dict() for plugin in discover_sql_plugins().values()]
