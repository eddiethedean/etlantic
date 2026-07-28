"""Entry-point discovery for SQL plugins."""

from __future__ import annotations

from typing import Any

from etlantic.plugin_lifecycle import discover_evaluate_authorize_load
from etlantic.profile import Profile
from etlantic.registry import PluginDescriptor, RegistryBundle
from etlantic.sql.protocol import SqlPlugin

SQL_PLUGIN_ENTRY_POINT = "etlantic.sql_plugins"



def _fail_closed_loaded(result):
    from etlantic.diagnostics import Severity
    from etlantic.exceptions import PipelineExecutionError

    errors = [d for d in result.diagnostics if d.severity is Severity.ERROR]
    loaded = dict(result.loaded)
    if errors and loaded:
        raise PipelineExecutionError(
            "; ".join(d.message for d in errors),
            code=errors[0].code,
        )
    if errors:
        return {}
    return loaded

def discover_sql_plugins(
    *,
    profile: Profile | None = None,
) -> dict[str, SqlPlugin]:
    """Discover SQL plugins with authorize-before-load (0.20)."""
    result = discover_evaluate_authorize_load(
        SQL_PLUGIN_ENTRY_POINT,
        profile=profile,
        key_fn=lambda item, plugin: str(
            getattr(getattr(plugin, "info", None), "engine", None) or item.name
        ),
    )
    return _fail_closed_loaded(result)


def register_discovered_plugins(
    registry: RegistryBundle,
    *,
    plugins: dict[str, SqlPlugin] | None = None,
    profile: Profile | None = None,
) -> dict[str, SqlPlugin]:
    """Register discovered SQL plugins into a planning registry."""
    discovered = (
        plugins if plugins is not None else discover_sql_plugins(profile=profile)
    )
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


def load_sql_plugin(
    engine: str = "sql",
    *,
    profile: Profile | None = None,
) -> SqlPlugin | None:
    """Return a discovered plugin for ``engine``, or None."""
    return discover_sql_plugins(profile=profile).get(engine)


def plugin_registry_snapshot(
    *,
    profile: Profile | None = None,
) -> list[dict[str, Any]]:
    """Return serializable descriptors for discovered SQL plugins."""
    return [
        plugin.info.to_dict()
        for plugin in discover_sql_plugins(profile=profile).values()
    ]
