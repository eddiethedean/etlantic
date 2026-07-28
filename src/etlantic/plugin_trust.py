"""Plugin allowlist / version-pin enforcement (0.9)."""

from __future__ import annotations

from typing import Any

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from etlantic.diagnostics import Diagnostic, Severity
from etlantic.profile import Profile

# In-tree stub descriptors (registry.builtin_stub_registry). These are not
# entry-point packages and must not require package allowlist keys — otherwise
# adopters are pushed to list short names like ``"local": null``, which widens
# authorization when engine/name matching is enabled.
BUILTIN_ALLOWLIST_EXEMPT = frozenset({"local", "null", "env", "env-secrets"})

_EMPTY_ALLOWLIST_REMEDIATION = (
    "Set Profile.plugin_allowlist to a non-empty map of package→pin "
    "(for example {'etlantic-polars': '==0.26.0'}), or copy "
    "docs/01_GETTING_STARTED/prod.example.json. The built-in "
    "--profile production template is empty and fail-closed."
)


def empty_production_allowlist_message(profile_name: str) -> str:
    """Return a remediation-rich empty-allowlist error message."""
    return (
        f"Production profile {profile_name!r} requires a non-empty "
        f"plugin_allowlist; rejecting all discovered plugins. "
        f"{_EMPTY_ALLOWLIST_REMEDIATION}"
    )


def is_production_profile(
    profile: Profile | None = None,
    *,
    name: str | None = None,
    security_domain: str | None = None,
    security_mode: str | None = None,
) -> bool:
    """Return True when fail-closed production trust/drift applies.

    ETLantic 0.19 uses explicit ``Profile.security_mode == "production"`` only.
    ``name`` / ``security_domain`` remain labels for compatibility and are not
    used for this decision.
    """
    del name, security_domain
    mode = security_mode
    if mode is None and profile is not None:
        mode = getattr(profile, "security_mode", None)
    return str(mode or "").strip().lower() == "production"


def _is_production_profile(profile: Profile) -> bool:
    return is_production_profile(profile)


def _normalize_version_pin(pin: str) -> str:
    """Accept bare versions as exact pins (``0.11.0`` → ``==0.11.0``)."""
    text = pin.strip()
    if not text:
        return text
    # Specifiers start with a comparison operator or include a comma/OR.
    if text[0] in "<>!=-~*" or "," in text or "||" in text:
        return text
    # Bare version string → exact match.
    try:
        Version(text)
    except InvalidVersion:
        return text
    return f"=={text}"


def plugin_allowed(
    *,
    name: str,
    version: str | None,
    allowlist: dict[str, str | None],
) -> bool:
    """Return True when ``name`` is permitted by ``allowlist`` (and pin)."""
    if name not in allowlist:
        return False
    pin = allowlist.get(name)
    if pin is None or pin == "":
        return True
    if version is None:
        return False
    try:
        return Version(version) in SpecifierSet(_normalize_version_pin(pin))
    except (InvalidVersion, InvalidSpecifier):
        return False


def is_builtin_allowlist_exempt(name: str | None) -> bool:
    """Return True for in-tree stub plugin identities exempt from package pins."""
    return str(name or "").strip().lower() in BUILTIN_ALLOWLIST_EXEMPT


def filter_plugins_by_allowlist(
    plugins: dict[str, Any],
    profile: Profile,
    *,
    name_attr: str = "name",
    version_attr: str = "version",
) -> tuple[dict[str, Any], list[Diagnostic]]:
    """Filter discovered plugins using profile allowlist.

    Production profiles fail closed when the allowlist is empty or a plugin is
    not listed / does not match the version pin. Non-production profiles with an
    empty allowlist remain unrestricted.

    Built-in stub identities (``local``, ``null``, ``env``, ``env-secrets``) are
    exempt from package allowlist matching so production profiles need not list
    short engine names.
    """
    allowlist = dict(profile.plugin_allowlist or {})
    production = _is_production_profile(profile)
    diagnostics: list[Diagnostic] = []

    if not allowlist:
        if production:
            diagnostics.append(
                Diagnostic(
                    code="PMPLUG401",
                    severity=Severity.ERROR,
                    message=empty_production_allowlist_message(profile.name),
                    path=("profile", "plugin_allowlist"),
                    phase="plugin_trust",
                )
            )
            return {}, diagnostics
        return dict(plugins), diagnostics

    kept: dict[str, Any] = {}
    for key, plugin in plugins.items():
        if is_builtin_allowlist_exempt(str(key)):
            kept[key] = plugin
            continue
        info = getattr(plugin, "info", None)
        if callable(info):
            info = info()
        metadata = getattr(plugin, "metadata", None) or {}
        if not isinstance(metadata, dict):
            metadata = {}
        pname = (
            getattr(info, name_attr, None) or getattr(plugin, name_attr, None) or key
        )
        if is_builtin_allowlist_exempt(str(pname)):
            kept[key] = plugin
            continue
        pversion = (
            getattr(info, version_attr, None)
            or getattr(plugin, version_attr, None)
            or None
        )
        identity_candidates = [
            str(pname),
            str(key),
            str(metadata.get("package") or "") or None,
            str(metadata.get("distribution_name") or "") or None,
        ]
        listed_name = next(
            (c for c in identity_candidates if c and c in allowlist),
            None,
        )
        if listed_name is not None:
            pin = allowlist.get(listed_name)
            if pin not in (None, ""):
                try:
                    SpecifierSet(_normalize_version_pin(str(pin)))
                except InvalidSpecifier:
                    diagnostics.append(
                        Diagnostic(
                            code="PMPLUG403",
                            severity=Severity.ERROR if production else Severity.WARNING,
                            message=(
                                f"Invalid plugin_allowlist pin for {pname!r}: {pin!r}."
                            ),
                            path=("plugin", str(pname)),
                            phase="plugin_trust",
                        )
                    )
                    continue
        if any(
            plugin_allowed(name=str(c), version=pversion, allowlist=allowlist)
            for c in identity_candidates
            if c
        ):
            kept[key] = plugin
        else:
            diagnostics.append(
                Diagnostic(
                    code="PMPLUG402",
                    severity=Severity.ERROR if production else Severity.WARNING,
                    message=(
                        f"Plugin {pname!r} (version={pversion!r}) is not permitted "
                        f"by profile {profile.name!r} plugin_allowlist."
                    ),
                    path=("plugin", str(pname)),
                    phase="plugin_trust",
                )
            )
    return kept, diagnostics


def assert_plugin_trust(
    plugins: dict[str, Any],
    profile: Profile,
) -> dict[str, Any]:
    """Filter plugins and raise when production trust fails closed."""
    from etlantic.exceptions import PipelineExecutionError

    kept, diagnostics = filter_plugins_by_allowlist(plugins, profile)
    errors = [d for d in diagnostics if d.severity is Severity.ERROR]
    if errors:
        raise PipelineExecutionError(
            "; ".join(d.message for d in errors),
            code=errors[0].code,
        )
    return kept


# Per-plugin allowlist denials are expected when other packages remain allowed.
_NON_BLOCKING_TRUST_CODES = frozenset({"PMPLUG402"})


def loaded_plugins_after_trust(result: Any) -> dict[str, Any]:
    """Return authorized loads from a lifecycle result.

    ``PMPLUG402`` denials of non-allowlisted siblings do not invalidate plugins
    that were authorized and loaded. Other trust ERROR codes still fail closed
    (raise when loads coexist; otherwise return an empty mapping).
    """
    from etlantic.exceptions import PipelineExecutionError

    errors = [
        d
        for d in getattr(result, "diagnostics", ()) or ()
        if getattr(d, "severity", None) is Severity.ERROR
    ]
    loaded = dict(getattr(result, "loaded", {}) or {})
    blocking = [
        d for d in errors if getattr(d, "code", None) not in _NON_BLOCKING_TRUST_CODES
    ]
    if blocking and loaded:
        raise PipelineExecutionError(
            "; ".join(d.message for d in blocking),
            code=blocking[0].code,
        )
    if blocking:
        return {}
    return loaded
