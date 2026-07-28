"""Entry-point discovery for Spark plugins and providers."""

from __future__ import annotations

from typing import Any

from etlantic.plugin_lifecycle import discover_evaluate_authorize_load
from etlantic.profile import Profile
from etlantic.registry import PluginDescriptor, RegistryBundle
from etlantic.spark.protocol import SparkPlugin
from etlantic.spark.provider import SparkProvider

SPARK_PLUGIN_ENTRY_POINT = "etlantic.spark_plugins"
SPARK_PROVIDER_ENTRY_POINT = "etlantic.spark_providers"


def _fail_closed_loaded(result):
    from etlantic.plugin_trust import loaded_plugins_after_trust

    return loaded_plugins_after_trust(result)


def discover_spark_plugins(
    *,
    profile: Profile | None = None,
) -> dict[str, SparkPlugin]:
    """Discover Spark plugins with authorize-before-load (0.20).

    Trust diagnostics from the latest call are exposed on
    ``discover_spark_plugins.last_diagnostics``.
    """
    discover_spark_plugins.last_diagnostics = []  # type: ignore[attr-defined]
    result = discover_evaluate_authorize_load(
        SPARK_PLUGIN_ENTRY_POINT,
        profile=profile,
        key_fn=lambda item, plugin: str(
            getattr(getattr(plugin, "info", None), "engine", None) or item.name
        ),
    )
    discover_spark_plugins.last_diagnostics = list(result.diagnostics)  # type: ignore[attr-defined]
    return _fail_closed_loaded(result)


def discover_spark_providers(
    *,
    profile: Profile | None = None,
) -> dict[str, SparkProvider]:
    """Discover Spark providers with authorize-before-load (0.20).

    Trust diagnostics from the latest call are exposed on
    ``discover_spark_providers.last_diagnostics``.
    """
    discover_spark_providers.last_diagnostics = []  # type: ignore[attr-defined]
    result = discover_evaluate_authorize_load(
        SPARK_PROVIDER_ENTRY_POINT,
        profile=profile,
        key_fn=lambda item, plugin: str(
            getattr(getattr(plugin, "info", None), "name", None) or item.name
        ),
    )
    discover_spark_providers.last_diagnostics = list(result.diagnostics)  # type: ignore[attr-defined]
    return _fail_closed_loaded(result)


def register_discovered_plugins(
    registry: RegistryBundle,
    *,
    plugins: dict[str, SparkPlugin] | None = None,
    profile: Profile | None = None,
) -> dict[str, SparkPlugin]:
    """Register discovered Spark plugins into a planning registry."""
    discovered = (
        plugins if plugins is not None else discover_spark_plugins(profile=profile)
    )
    for engine, plugin in discovered.items():
        info = plugin.info
        caps = info.capabilities or plugin.capabilities()
        registry.register_plugin(
            PluginDescriptor(
                name=info.name,
                kind="spark",
                version=info.version,
                engine=info.engine or engine,
                capabilities=caps,
                metadata={
                    "protocol_version": info.protocol_version,
                    "streaming_stability": info.streaming_stability,
                },
            )
        )
    return discovered


def load_spark_plugin(
    engine: str = "pyspark",
    *,
    profile: Profile | None = None,
) -> SparkPlugin | None:
    """Return a discovered plugin for ``engine``, or None."""
    plugins = discover_spark_plugins(profile=profile)
    if engine in plugins:
        return plugins[engine]
    if engine == "spark":
        return plugins.get("pyspark")
    if engine == "pyspark":
        return plugins.get("spark")
    return None


def load_spark_provider(
    name: str = "local",
    *,
    profile: Profile | None = None,
) -> SparkProvider | None:
    """Return a discovered provider by name, or None."""
    return discover_spark_providers(profile=profile).get(name)


def plugin_registry_snapshot(
    *,
    profile: Profile | None = None,
) -> list[dict[str, Any]]:
    """Return serializable descriptors for discovered Spark plugins."""
    return [
        plugin.info.to_dict()
        for plugin in discover_spark_plugins(profile=profile).values()
    ]
