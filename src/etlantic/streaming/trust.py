"""Production schema-registry allowlist (fail closed)."""

from __future__ import annotations

from collections.abc import Mapping

from etlantic.plugin_trust import is_production_profile
from etlantic.profile import Profile
from etlantic.streaming.diagnostics import reg_diagnostic


def registry_adapter_allowed(
    profile: Profile,
    package_name: str,
    *,
    version: str | None = None,
) -> tuple[bool, object | None]:
    """Return whether ``package_name`` may load as a registry adapter.

    Production requires a non-empty ``schema_registry_allowlist`` entry with a
    real pin (same contract as ``plugin_allowlist``).
    """
    production = is_production_profile(profile)
    allowlist: Mapping[str, str | None] = dict(
        getattr(profile, "schema_registry_allowlist", {}) or {}
    )
    if production and not allowlist:
        return False, reg_diagnostic(
            "not_allowlisted",
            "Production profiles require Profile.schema_registry_allowlist "
            "and fail closed when it is empty.",
            path=("profile", "schema_registry_allowlist"),
        )
    if not production and not allowlist:
        return True, None
    if package_name not in allowlist:
        return False, reg_diagnostic(
            "not_allowlisted",
            f"Schema-registry adapter {package_name!r} is not allowlisted.",
            path=("profile", "schema_registry_allowlist", package_name),
        )
    pin = allowlist[package_name]
    if production and (pin is None or not str(pin).strip()):
        return False, reg_diagnostic(
            "not_allowlisted",
            f"Production schema_registry_allowlist pin for {package_name!r} "
            "must be a non-empty specifier.",
            path=("profile", "schema_registry_allowlist", package_name),
        )
    if version is not None and pin and pin.startswith("==") and pin[2:] != version:
        return False, reg_diagnostic(
            "not_allowlisted",
            f"Schema-registry adapter {package_name!r} version {version!r} "
            f"does not match pin {pin!r}.",
            path=("profile", "schema_registry_allowlist", package_name),
        )
    return True, None
