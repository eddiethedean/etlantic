"""Authorization policy classes for plugin lifecycle."""

from __future__ import annotations

from typing import Any, Protocol

from etlantic.diagnostics import Diagnostic, Severity
from etlantic.plugin_trust import (
    allowlist_pin_invalid,
    empty_production_allowlist_message,
    is_builtin_allowlist_exempt,
    is_production_profile,
    package_identity_candidates,
    plugin_allowed,
)
from etlantic.profile import Profile
from etlantic.runtime.events import SecurityEvent


class AuthorizationPolicy(Protocol):
    """Authorize discovered plugins before entry-point import."""

    def authorize(
        self,
        discovered: list,
        profile: Profile | None,
        *,
        run_id: str = "plan",
    ) -> tuple[list, list[Diagnostic], list[SecurityEvent]]: ...


def _with_auth(item: Any, authorization: str) -> Any:
    from etlantic.plugin_lifecycle import DiscoveredPlugin

    return DiscoveredPlugin(
        group=item.group,
        name=item.name,
        target=item.target,
        distribution_name=item.distribution_name,
        distribution_version=item.distribution_version,
        entry_point=item.entry_point,
        manifest=item.manifest,
        digest=item.digest,
        protocol=item.protocol,
        capabilities=item.capabilities,
        engine=item.engine,
        authorization=authorization,
        provenance=dict(item.provenance),
    )


def _plugin_event(
    *, run_id: str, item: Any, outcome: str, message: str
) -> SecurityEvent:
    return SecurityEvent(
        kind="plugin_authorization",
        run_id=run_id,
        provider=item.distribution_name or item.name,
        secret_identity="",
        outcome=outcome,
        message=message,
        schema_version="etlantic.security_event/1",
        subject=item.name,
        metadata={
            "group": item.group,
            "digest": item.digest,
            "protocol": item.protocol,
            "authorization": item.authorization,
            "version": item.distribution_version,
        },
    )


class BaseAuthorizationPolicy:
    """Shared allowlist authorization (package identity only)."""

    def authorize(
        self,
        discovered: list,
        profile: Profile | None,
        *,
        run_id: str = "plan",
    ) -> tuple[list, list[Diagnostic], list[SecurityEvent]]:
        diagnostics: list[Diagnostic] = []
        events: list[SecurityEvent] = []
        authorized: list = []

        if profile is None:
            for item in discovered:
                auth = _with_auth(item, "allowed")
                authorized.append(auth)
                events.append(
                    _plugin_event(
                        run_id=run_id,
                        item=auth,
                        outcome="allowed",
                        message="No profile; authorization open.",
                    )
                )
            return authorized, diagnostics, events

        allowlist = dict(profile.plugin_allowlist or {})
        production = is_production_profile(profile)

        if not allowlist:
            if production:
                diagnostics.append(
                    Diagnostic(
                        code="PMPLUG401",
                        severity=Severity.ERROR,
                        message=empty_production_allowlist_message(profile.name),
                        path=("profile", "plugin_allowlist"),
                        phase="plugin_authorize",
                    )
                )
                for item in discovered:
                    events.append(
                        _plugin_event(
                            run_id=run_id,
                            item=_with_auth(item, "denied"),
                            outcome="denied",
                            message="Empty production allowlist.",
                        )
                    )
                return [], diagnostics, events
            for item in discovered:
                auth = _with_auth(item, "allowed")
                authorized.append(auth)
                events.append(
                    _plugin_event(
                        run_id=run_id,
                        item=auth,
                        outcome="allowed",
                        message="Non-production empty allowlist.",
                    )
                )
            return authorized, diagnostics, events

        for item in discovered:
            # Exempt only true in-tree stubs by EP/plugin name with no
            # distribution package. Never treat third-party engine spoofs
            # (engine="local") as builtin.
            if item.distribution_name is None and is_builtin_allowlist_exempt(
                item.name
            ):
                auth = _with_auth(item, "allowed")
                authorized.append(auth)
                events.append(
                    _plugin_event(
                        run_id=run_id,
                        item=auth,
                        outcome="allowed",
                        message="Builtin stub exempt from package allowlist.",
                    )
                )
                continue

            candidates = package_identity_candidates(
                distribution_name=item.distribution_name,
                package=item.manifest.package if item.manifest else None,
            )
            version = item.distribution_version or (
                item.manifest.version if item.manifest else None
            )

            listed_name = next((c for c in candidates if c in allowlist), None)
            if listed_name is not None:
                pin = allowlist.get(listed_name)
                if allowlist_pin_invalid(pin if isinstance(pin, str) else None):
                    diagnostics.append(
                        Diagnostic(
                            code="PMPLUG403",
                            severity=Severity.ERROR if production else Severity.WARNING,
                            message=(
                                f"Invalid plugin_allowlist pin for "
                                f"{item.distribution_name or item.name!r}: {pin!r}."
                            ),
                            path=("plugin", item.distribution_name or item.name),
                            phase="plugin_authorize",
                        )
                    )
                    events.append(
                        _plugin_event(
                            run_id=run_id,
                            item=_with_auth(item, "denied"),
                            outcome="denied",
                            message="Invalid allowlist pin.",
                        )
                    )
                    continue

            ok = any(
                plugin_allowed(name=str(c), version=version, allowlist=allowlist)
                for c in candidates
            )
            if ok:
                auth = _with_auth(item, "allowed")
                authorized.append(auth)
                events.append(
                    _plugin_event(
                        run_id=run_id,
                        item=auth,
                        outcome="allowed",
                        message="Allowlist matched.",
                    )
                )
            else:
                denied = _with_auth(item, "denied")
                diagnostics.append(
                    Diagnostic(
                        code="PMPLUG402",
                        severity=Severity.ERROR if production else Severity.WARNING,
                        message=(
                            f"Plugin {item.distribution_name or item.name!r} "
                            f"(version={version!r}) is not permitted by profile "
                            f"{profile.name!r} plugin_allowlist."
                        ),
                        path=("plugin", item.distribution_name or item.name),
                        phase="plugin_authorize",
                    )
                )
                events.append(
                    _plugin_event(
                        run_id=run_id,
                        item=denied,
                        outcome="denied",
                        message="Allowlist rejection before import.",
                    )
                )
        return authorized, diagnostics, events


class DevelopmentPolicy(BaseAuthorizationPolicy):
    """Non-production authorization policy."""


class ProductionPolicy(BaseAuthorizationPolicy):
    """Production authorization policy (fail closed on empty allowlist)."""


def policy_for_profile(profile: Profile | None) -> BaseAuthorizationPolicy:
    if profile is not None and is_production_profile(profile):
        return ProductionPolicy()
    return DevelopmentPolicy()
