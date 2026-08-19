"""Production trust for Experimental MCP extras (`etlantic-mcp`)."""

from __future__ import annotations

from collections.abc import Mapping

from etlantic.agents.diagnostics import mcp_diagnostic
from etlantic.plugin_lifecycle import discover_evaluate_authorize_load
from etlantic.plugin_trust import is_production_profile, loaded_plugins_after_trust
from etlantic.profile import Profile

MCP_ENTRY_POINT = "etlantic.mcp_servers"


def mcp_server_allowed(
    profile: Profile,
    package_name: str,
    *,
    version: str | None = None,
    selected: bool = True,
) -> tuple[bool, object | None]:
    """Fail closed in production when ``etlantic-mcp`` is selected."""
    if not selected:
        return True, None
    if not is_production_profile(profile):
        return True, None
    allowlist: Mapping[str, str | None] = dict(profile.plugin_allowlist or {})
    if package_name not in allowlist:
        return False, mcp_diagnostic(
            "not_allowlisted",
            f"MCP extra {package_name!r} is not in Profile.plugin_allowlist.",
            path=("profile", "plugin_allowlist", package_name),
        )
    pin = allowlist[package_name]
    if pin is None or not str(pin).strip():
        return False, mcp_diagnostic(
            "not_allowlisted",
            f"Production plugin_allowlist pin for {package_name!r} must be a real pin.",
            path=("profile", "plugin_allowlist", package_name),
        )
    if version is not None:
        from packaging.specifiers import InvalidSpecifier, SpecifierSet
        from packaging.version import InvalidVersion, Version

        try:
            if Version(version) not in SpecifierSet(str(pin)):
                return False, mcp_diagnostic(
                    "not_allowlisted",
                    f"MCP extra {package_name!r} version {version} fails pin {pin}.",
                    path=("profile", "plugin_allowlist", package_name),
                )
        except (InvalidSpecifier, InvalidVersion):
            return False, mcp_diagnostic(
                "not_allowlisted",
                f"Invalid plugin_allowlist pin for {package_name!r}.",
                path=("profile", "plugin_allowlist", package_name),
            )
    return True, None


def discover_mcp_servers(*, profile: Profile | None = None) -> dict[str, object]:
    """Discover MCP extras with plugin allowlist, then PMMCP140."""
    discover_mcp_servers.last_diagnostics = []  # type: ignore[attr-defined]
    result = discover_evaluate_authorize_load(
        MCP_ENTRY_POINT,
        profile=profile,
        key_fn=lambda item, plugin: str(getattr(plugin, "package", None) or item.name),
    )
    diagnostics = list(result.diagnostics)
    loaded = dict(loaded_plugins_after_trust(result))
    if profile is not None and loaded:
        for name, plugin in list(loaded.items()):
            package = str(getattr(plugin, "package", None) or name)
            version = getattr(plugin, "version", None)
            allowed, diag = mcp_server_allowed(
                profile,
                package,
                version=str(version) if version is not None else None,
                selected=True,
            )
            if not allowed:
                loaded.pop(name, None)
                if diag is not None:
                    diagnostics.append(diag)
    discover_mcp_servers.last_diagnostics = diagnostics  # type: ignore[attr-defined]
    return loaded
