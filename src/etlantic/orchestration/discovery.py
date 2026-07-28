"""Entry-point discovery for orchestrator plugins."""

from __future__ import annotations

from typing import Any

from etlantic.orchestration.protocol import OrchestratorPlugin
from etlantic.plugin_lifecycle import discover_evaluate_authorize_load
from etlantic.profile import Profile
from etlantic.registry import PluginDescriptor, RegistryBundle

ORCHESTRATOR_PLUGIN_ENTRY_POINT = "etlantic.orchestrator_plugins"


def _fail_closed_loaded(result):
    from etlantic.plugin_trust import loaded_plugins_after_trust

    return loaded_plugins_after_trust(result)


def discover_orchestrator_plugins(
    *,
    profile: Profile | None = None,
) -> dict[str, OrchestratorPlugin]:
    """Discover orchestrator plugins with authorize-before-load (0.20).

    Trust diagnostics from the latest call are exposed on
    ``discover_orchestrator_plugins.last_diagnostics``.
    """
    discover_orchestrator_plugins.last_diagnostics = []  # type: ignore[attr-defined]
    result = discover_evaluate_authorize_load(
        ORCHESTRATOR_PLUGIN_ENTRY_POINT,
        profile=profile,
        key_fn=lambda item, plugin: str(
            getattr(getattr(plugin, "info", None), "engine", None) or item.name
        ),
    )
    discover_orchestrator_plugins.last_diagnostics = list(result.diagnostics)  # type: ignore[attr-defined]
    return _fail_closed_loaded(result)


def register_discovered_plugins(
    registry: RegistryBundle,
    *,
    plugins: dict[str, OrchestratorPlugin] | None = None,
    profile: Profile | None = None,
) -> dict[str, OrchestratorPlugin]:
    """Register discovered orchestrator plugins into a planning registry."""
    discovered = (
        plugins
        if plugins is not None
        else discover_orchestrator_plugins(profile=profile)
    )
    for engine, plugin in discovered.items():
        info = plugin.info
        caps = info.capabilities or plugin.capabilities()
        registry.register_plugin(
            PluginDescriptor(
                name=info.name,
                kind="orchestrator",
                version=info.version,
                engine=info.engine or engine,
                capabilities=caps,
                metadata={"protocol_version": info.protocol_version},
            )
        )
    return discovered


def load_orchestrator_plugin(
    engine: str = "airflow",
    *,
    profile: Profile | None = None,
) -> OrchestratorPlugin | None:
    """Return a discovered orchestrator plugin for ``engine``, or None."""
    return discover_orchestrator_plugins(profile=profile).get(engine)


def plugin_registry_snapshot(
    *,
    profile: Profile | None = None,
) -> list[dict[str, Any]]:
    """Return serializable descriptors for discovered orchestrator plugins."""
    return [
        plugin.info.to_dict()
        for plugin in discover_orchestrator_plugins(profile=profile).values()
    ]
