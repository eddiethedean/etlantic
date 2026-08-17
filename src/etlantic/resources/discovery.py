"""Entry-point discovery for resource providers (`etlantic.resource_providers`)."""

from __future__ import annotations

from typing import Any

from etlantic.control_plane.schedule_trust import resource_provider_allowed
from etlantic.plugin_lifecycle import discover_evaluate_authorize_load
from etlantic.profile import Profile
from etlantic.resources.protocol import ResourceProvider

RESOURCE_PROVIDER_ENTRY_POINT = "etlantic.resource_providers"


def _fail_closed_loaded(result):
    from etlantic.plugin_trust import loaded_plugins_after_trust

    return loaded_plugins_after_trust(result)


def discover_resource_providers(
    *,
    profile: Profile | None = None,
) -> dict[str, ResourceProvider]:
    """Discover resource providers with plugin allowlist, then PMRES140."""
    discover_resource_providers.last_diagnostics = []  # type: ignore[attr-defined]
    result = discover_evaluate_authorize_load(
        RESOURCE_PROVIDER_ENTRY_POINT,
        profile=profile,
        key_fn=lambda item, plugin: str(
            getattr(getattr(plugin, "info", None), "name", None) or item.name
        ),
    )
    diagnostics = list(result.diagnostics)
    loaded: dict[str, Any] = dict(_fail_closed_loaded(result))
    if profile is not None and loaded:
        for name, plugin in list(loaded.items()):
            info = getattr(plugin, "info", None)
            package = str(getattr(info, "package", None) or name)
            version = getattr(info, "version", None)
            allowed, diag = resource_provider_allowed(
                profile,
                package,
                version=str(version) if version is not None else None,
                selected=True,
            )
            if not allowed:
                loaded.pop(name, None)
                if diag is not None:
                    diagnostics.append(diag)
    discover_resource_providers.last_diagnostics = diagnostics  # type: ignore[attr-defined]
    return loaded
