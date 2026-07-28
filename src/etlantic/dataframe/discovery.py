"""Entry-point discovery for dataframe plugins."""

from __future__ import annotations

from typing import Any

from etlantic.dataframe.protocol import DataframePlugin
from etlantic.diagnostics import Severity
from etlantic.exceptions import PipelineExecutionError
from etlantic.plugin_lifecycle import discover_evaluate_authorize_load
from etlantic.profile import Profile
from etlantic.registry import PluginDescriptor, RegistryBundle

DATAFRAME_PLUGIN_ENTRY_POINT = "etlantic.dataframe_plugins"


def resolve_plugin_info(plugin: Any) -> Any:
    """Return plugin info whether exposed as a property or callable method."""
    info = plugin.info
    return info() if callable(info) else info


def _fail_closed_loaded(result: Any) -> dict[str, Any]:
    """Return loaded plugins, raising only if ERROR diags coexist with loads."""
    errors = [d for d in result.diagnostics if d.severity is Severity.ERROR]
    loaded = dict(result.loaded)
    if errors and loaded:
        raise PipelineExecutionError(
            "; ".join(d.message for d in errors),
            code=errors[0].code,
        )
    if errors:
        return {}
    return loaded  # type: ignore[return-value]


def discover_dataframe_plugins(
    *,
    profile: Profile | None = None,
) -> dict[str, DataframePlugin]:
    """Discover dataframe plugins with authorize-before-load (0.20).

    When ``profile`` is omitted, allowlists are open (non-production behavior).
    Production profiles require manifests and a non-empty allowlist.

    Raises:
        PipelineExecutionError: When trust ERROR diagnostics coexist with
            loaded plugins (fail-open would otherwise occur). Trust failures
            that reject all plugins return an empty mapping.
    """
    result = discover_evaluate_authorize_load(
        DATAFRAME_PLUGIN_ENTRY_POINT,
        profile=profile,
        key_fn=lambda item, plugin: str(
            getattr(resolve_plugin_info(plugin), "engine", None) or item.name
        ),
    )
    return _fail_closed_loaded(result)


def register_discovered_plugins(
    registry: RegistryBundle,
    *,
    plugins: dict[str, DataframePlugin] | None = None,
    profile: Profile | None = None,
) -> dict[str, DataframePlugin]:
    """Register discovered dataframe plugins into a planning registry."""
    discovered = (
        plugins if plugins is not None else discover_dataframe_plugins(profile=profile)
    )
    for engine, plugin in discovered.items():
        info = resolve_plugin_info(plugin)
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


def load_dataframe_plugin(
    engine: str,
    *,
    profile: Profile | None = None,
) -> DataframePlugin | None:
    """Return a discovered plugin for ``engine``, or None."""
    return discover_dataframe_plugins(profile=profile).get(engine)


def plugin_registry_snapshot(
    *,
    profile: Profile | None = None,
) -> list[dict[str, Any]]:
    """Return serializable descriptors for discovered plugins."""
    out: list[dict[str, Any]] = []
    for plugin in discover_dataframe_plugins(profile=profile).values():
        out.append(resolve_plugin_info(plugin).to_dict())
    return out
