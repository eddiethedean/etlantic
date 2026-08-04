"""Plugin allowlist / version-pin enforcement (0.9)."""

from __future__ import annotations

from typing import Any

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.utils import canonicalize_name
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
    "(for example {'etlantic-polars': '==0.43.0'}), or copy "
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


def _canonicalize_allowlist_key(name: str) -> str:
    text = str(name or "").strip()
    if not text:
        return text
    try:
        return canonicalize_name(text)
    except Exception:
        return text.lower()


def _normalize_allowlist(allowlist: dict[str, str | None]) -> dict[str, str | None]:
    """Return allowlist keyed by canonical distribution names."""
    out: dict[str, str | None] = {}
    for key, pin in dict(allowlist or {}).items():
        canon = _canonicalize_allowlist_key(str(key))
        if not canon:
            continue
        # Prefer an existing non-empty pin if duplicate keys collide.
        if canon in out and out[canon] not in (None, "") and pin in (None, ""):
            continue
        out[canon] = pin
    return out


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
    require_pin: bool = False,
) -> bool:
    """Return True when ``name`` is permitted by ``allowlist`` (and pin)."""
    canon = _canonicalize_allowlist_key(name)
    normalized = _normalize_allowlist(allowlist)
    if canon not in normalized:
        return False
    pin = normalized.get(canon)
    if pin is None or pin == "":
        return not require_pin
    if version is None:
        return False
    try:
        return Version(version) in SpecifierSet(_normalize_version_pin(pin))
    except (InvalidVersion, InvalidSpecifier):
        return False


def allowlist_pin_invalid(pin: str | None) -> bool:
    """Return True when a non-empty pin is not a valid packaging specifier."""
    if pin is None or pin == "":
        return False
    try:
        SpecifierSet(_normalize_version_pin(str(pin)))
    except InvalidSpecifier:
        return True
    return False


def package_identity_candidates(
    *,
    distribution_name: str | None = None,
    package: str | None = None,
) -> list[str]:
    """Return package-identity keys used for allowlist matching.

    Engine / entry short names are intentionally excluded so a plugin cannot
    spoof authorization by setting ``engine="etlantic-polars"``.
    """
    out: list[str] = []
    for value in (distribution_name, package):
        text = _canonicalize_allowlist_key(str(value or "").strip())
        if text and text not in out:
            out.append(text)
    return out


# Stamped onto loaded plugin instances so post-load trust/registry keep the
# same package identity keys used during authorize-before-load.
PLUGIN_IDENTITY_ATTR = "_etlantic_package_identity"


def stamp_plugin_package_identity(
    plugin: Any,
    *,
    distribution_name: str | None = None,
    package: str | None = None,
    distribution_version: str | None = None,
) -> None:
    """Attach package identity to a loaded plugin for registry/trust reuse."""
    identity = {
        "distribution_name": str(distribution_name or "").strip() or None,
        "package": str(package or "").strip() or None,
        "distribution_version": str(distribution_version or "").strip() or None,
    }
    try:
        setattr(plugin, PLUGIN_IDENTITY_ATTR, identity)
    except Exception:
        # Immutable / slotted hosts: still usable via descriptor metadata at
        # register time when callers pass identity explicitly.
        return


def resolve_plugin_package_identity(plugin: Any) -> dict[str, str | None]:
    """Resolve package identity from stamped attrs, descriptor metadata, or info."""
    stamped = getattr(plugin, PLUGIN_IDENTITY_ATTR, None)
    if isinstance(stamped, dict):
        dist = stamped.get("distribution_name")
        pkg = stamped.get("package")
        ver = stamped.get("distribution_version")
        if dist or pkg:
            return {
                "distribution_name": str(dist) if dist else None,
                "package": str(pkg) if pkg else None,
                "distribution_version": str(ver) if ver else None,
            }
    metadata = getattr(plugin, "metadata", None) or {}
    if not isinstance(metadata, dict):
        metadata = {}
    info = getattr(plugin, "info", None)
    if callable(info):
        info = info()
    info_meta = getattr(info, "metadata", None) if info is not None else None
    if not isinstance(info_meta, dict):
        info_meta = {}
    dist = (
        metadata.get("distribution_name")
        or info_meta.get("distribution_name")
        or getattr(info, "distribution_name", None)
    )
    pkg = (
        metadata.get("package")
        or info_meta.get("package")
        or getattr(info, "package", None)
    )
    ver = (
        metadata.get("distribution_version")
        or info_meta.get("distribution_version")
        or getattr(info, "distribution_version", None)
    )
    return {
        "distribution_name": str(dist).strip() if dist else None,
        "package": str(pkg).strip() if pkg else None,
        "distribution_version": str(ver).strip() if ver else None,
    }


def descriptor_metadata_for_plugin(
    plugin: Any,
    info: Any = None,
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build PluginDescriptor.metadata including package identity fields."""
    if info is None:
        info = getattr(plugin, "info", None)
        if callable(info):
            info = info()
    metadata: dict[str, Any] = {}
    if info is not None and getattr(info, "protocol_version", None) is not None:
        metadata["protocol_version"] = info.protocol_version
    identity = resolve_plugin_package_identity(plugin)
    for key, value in identity.items():
        if value:
            metadata[key] = value
    if extra:
        metadata.update(extra)
    return metadata


def is_builtin_allowlist_exempt(name: str | None) -> bool:
    """Return True for in-tree stub plugin identities exempt from package pins."""
    return str(name or "").strip().lower() in BUILTIN_ALLOWLIST_EXEMPT


def filter_plugins_by_allowlist(
    plugins: dict[str, Any],
    profile: Profile,
    *,
    name_attr: str = "name",
    version_attr: str = "version",
    denial_phase: str = "plugin_trust",
    allow_builtin_exempt: bool = True,
) -> tuple[dict[str, Any], list[Diagnostic]]:
    """Filter discovered plugins using profile allowlist.

    Production profiles fail closed when the allowlist is empty or a plugin is
    not listed / does not match the version pin. Non-production profiles with an
    empty allowlist remain unrestricted.

    Built-in stub identities (``local``, ``null``, ``env``, ``env-secrets``) are
    exempt from package allowlist matching so production profiles need not list
    short engine names — unless ``allow_builtin_exempt=False`` (manual overlays).

    ``denial_phase`` tags allowlist denials: use ``plugin_discovery`` for broad
    sibling discovery and ``plugin_trust`` for selected-engine / manual checks.
    """
    allowlist = _normalize_allowlist(dict(profile.plugin_allowlist or {}))
    production = _is_production_profile(profile)
    diagnostics: list[Diagnostic] = []
    phase = str(denial_phase or "plugin_trust")

    if not allowlist:
        if production:
            diagnostics.append(
                Diagnostic(
                    code="PMPLUG401",
                    severity=Severity.ERROR,
                    message=empty_production_allowlist_message(profile.name),
                    path=("profile", "plugin_allowlist"),
                    phase=phase,
                )
            )
            return {}, diagnostics
        return dict(plugins), diagnostics

    kept: dict[str, Any] = {}
    for key, plugin in plugins.items():
        info = getattr(plugin, "info", None)
        if callable(info):
            info = info()
        identity = resolve_plugin_package_identity(plugin)
        # Third-party package identity never qualifies for builtin exemption,
        # even when engine/name spoofs ``local`` / ``env`` / etc.
        has_package_identity = bool(
            identity.get("distribution_name") or identity.get("package")
        )
        pname = (
            getattr(info, name_attr, None) or getattr(plugin, name_attr, None) or key
        )
        if (
            allow_builtin_exempt
            and not has_package_identity
            and (
                is_builtin_allowlist_exempt(str(key))
                or is_builtin_allowlist_exempt(str(pname))
            )
        ):
            kept[key] = plugin
            continue
        pversion = (
            identity.get("distribution_version")
            or getattr(info, version_attr, None)
            or getattr(plugin, version_attr, None)
            or None
        )
        identity_candidates = package_identity_candidates(
            distribution_name=identity.get("distribution_name"),
            package=identity.get("package"),
        )
        # Prefer package metadata; fall back to plugin.info.name when it looks
        # like a distribution (etlantic-*), never bare engine keys alone.
        pname_canon = _canonicalize_allowlist_key(str(pname))
        if (
            str(pname).startswith("etlantic-")
            and pname_canon not in identity_candidates
        ):
            identity_candidates.append(pname_canon)
        listed_name = next(
            (c for c in identity_candidates if c and c in allowlist),
            None,
        )
        if listed_name is not None:
            pin = allowlist.get(listed_name)
            if pin in (None, "") and production:
                diagnostics.append(
                    Diagnostic(
                        code="PMPLUG403",
                        severity=Severity.ERROR,
                        message=(
                            f"Production plugin_allowlist entry for {pname!r} "
                            f"requires a non-empty version pin "
                            f"(for example '==0.43.0')."
                        ),
                        path=("plugin", str(pname)),
                        phase=phase,
                    )
                )
                continue
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
                            phase=phase,
                        )
                    )
                    continue
        if any(
            plugin_allowed(
                name=str(c),
                version=pversion,
                allowlist=allowlist,
                require_pin=production,
            )
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
                    phase=phase,
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
# Only discovery-phase ``PMPLUG402`` is non-blocking; authorize/trust 402s fail closed.
# Missing static manifests (``PMPLUG413``) skip the EP during discover; the code is
# informational for that skip and must not fail every profile ensure when optional
# connector wheels are installed without manifests yet.
_NON_BLOCKING_TRUST_CODES = frozenset({"PMPLUG402", "PMPLUG413"})
_DISCOVERY_TRUST_PHASES = frozenset({"plugin_discovery", "plugin_discover"})


def is_non_blocking_trust_diagnostic(diagnostic: Any) -> bool:
    """Return True for sibling discovery allowlist denials / skipped EPs.

    ``PMPLUG402`` from ``plugin_trust`` / ``plugin_authorize`` (selected engines
    or manual overlays) is blocking. Discovery-phase sibling denials and
    missing-manifest skips (``PMPLUG413``) are not.
    """
    code = getattr(diagnostic, "code", None)
    if code not in _NON_BLOCKING_TRUST_CODES:
        return False
    phase = str(getattr(diagnostic, "phase", None) or "")
    return phase in _DISCOVERY_TRUST_PHASES


def loaded_plugins_after_trust(result: Any) -> dict[str, Any]:
    """Return authorized loads from a lifecycle result.

    Discovery-phase ``PMPLUG402`` denials of non-allowlisted siblings do not
    invalidate plugins that were authorized and loaded. Authorize/trust-phase
    ``PMPLUG402`` and other trust ERROR codes still fail closed.
    """
    from etlantic.exceptions import PipelineExecutionError

    errors = [
        d
        for d in getattr(result, "diagnostics", ()) or ()
        if getattr(d, "severity", None) is Severity.ERROR
    ]
    loaded = dict(getattr(result, "loaded", {}) or {})
    blocking = [d for d in errors if not is_non_blocking_trust_diagnostic(d)]
    if blocking and loaded:
        raise PipelineExecutionError(
            "; ".join(d.message for d in blocking),
            code=blocking[0].code,
        )
    if blocking:
        return {}
    return loaded
