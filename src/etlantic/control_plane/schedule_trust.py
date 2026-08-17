"""Production trust for resource providers and schedule stores."""

from __future__ import annotations

from collections.abc import Mapping

from etlantic.control_plane.schedule_diagnostics import res_diagnostic, svc_diagnostic
from etlantic.plugin_trust import is_production_profile
from etlantic.profile import Profile


def resource_provider_allowed(
    profile: Profile,
    package_name: str,
    *,
    version: str | None = None,
    selected: bool = True,
) -> tuple[bool, object | None]:
    """Return whether ``package_name`` may load as a resource provider.

    Production requires a non-empty ``resource_provider_allowlist`` entry with a
    real pin when a resource provider is selected (same contract as
    ``schema_registry_allowlist``).
    """
    if not selected:
        return True, None
    production = is_production_profile(profile)
    allowlist: Mapping[str, str | None] = dict(
        getattr(profile, "resource_provider_allowlist", {}) or {}
    )
    if production and not allowlist:
        return False, res_diagnostic(
            "not_allowlisted",
            "Production profiles require Profile.resource_provider_allowlist "
            "and fail closed when a resource provider is selected.",
            path=("profile", "resource_provider_allowlist"),
        )
    if not production and not allowlist:
        return True, None
    if package_name not in allowlist:
        return False, res_diagnostic(
            "not_allowlisted",
            f"Resource provider {package_name!r} is not allowlisted.",
            path=("profile", "resource_provider_allowlist", package_name),
        )
    pin = allowlist[package_name]
    if production and (pin is None or not str(pin).strip()):
        return False, res_diagnostic(
            "not_allowlisted",
            f"Production resource_provider_allowlist pin for {package_name!r} "
            "must be a non-empty specifier.",
            path=("profile", "resource_provider_allowlist", package_name),
        )
    if version is not None and pin and pin.startswith("==") and pin[2:] != version:
        return False, res_diagnostic(
            "not_allowlisted",
            f"Resource provider {package_name!r} version {version!r} "
            f"does not match pin {pin!r}.",
            path=("profile", "resource_provider_allowlist", package_name),
        )
    return True, None


def assert_schedule_store_allowed(profile: Profile, store: object) -> None:
    """Production rejects in-memory schedule stores (PMSVC100)."""
    if not is_production_profile(profile):
        return
    name = type(store).__name__
    if name == "MemoryScheduleStore" or "Memory" in name:
        diag = svc_diagnostic(
            "memory_store",
            "Production profiles reject MemoryScheduleStore; use a "
            "transactional ScheduleStore.",
            path=("profile", "schedule_store"),
        )
        raise ValueError(f"{diag.code}: {diag.message}")
