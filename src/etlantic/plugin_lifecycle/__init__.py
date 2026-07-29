"""Plugin lifecycle: discover → evaluate → authorize → load (0.20)."""

from __future__ import annotations

import logging
import warnings
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib.metadata import EntryPoint, entry_points
from typing import Any, TypeVar

from etlantic.diagnostics import Diagnostic, Severity
from etlantic.plugin_manifest import (
    PluginManifest,
    load_manifest_from_distribution,
)
from etlantic.plugin_trust import is_production_profile
from etlantic.profile import Profile
from etlantic.runtime.events import SecurityEvent

_LOG = logging.getLogger(__name__)
T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class DiscoveredPlugin:
    """Entry-point discovery record before executable load."""

    group: str
    name: str
    target: str
    distribution_name: str | None
    distribution_version: str | None
    entry_point: EntryPoint
    manifest: PluginManifest | None = None
    digest: str | None = None
    protocol: str | None = None
    capabilities: tuple[str, ...] = ()
    engine: str | None = None
    authorization: str = "pending"  # pending|allowed|denied|skipped
    provenance: dict[str, Any] = field(default_factory=dict)

    def trust_record(self) -> dict[str, Any]:
        """Secret-free trust metadata for plans/reports/events."""
        return {
            "group": self.group,
            "name": self.name,
            "target": self.target,
            "distribution": self.distribution_name,
            "version": self.distribution_version,
            "digest": self.digest,
            "protocol": self.protocol,
            "capabilities": list(self.capabilities),
            "engine": self.engine,
            "authorization": self.authorization,
            "provenance": dict(self.provenance),
            "package": self.manifest.package if self.manifest else None,
        }


@dataclass
class PluginLifecycleResult:
    """Outcome of a lifecycle phase batch."""

    discovered: list[DiscoveredPlugin] = field(default_factory=list)
    authorized: list[DiscoveredPlugin] = field(default_factory=list)
    loaded: dict[str, Any] = field(default_factory=dict)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    trust_records: list[dict[str, Any]] = field(default_factory=list)
    security_events: list[SecurityEvent] = field(default_factory=list)


def _iter_entry_points(group: str) -> list[EntryPoint]:
    try:
        eps = entry_points(group=group)
        return list(eps)
    except TypeError:  # pragma: no cover - older importlib API
        return list(entry_points().get(group, []))  # type: ignore[attr-defined]


def discover_entry_points(
    group: str,
) -> tuple[list[DiscoveredPlugin], list[Diagnostic]]:
    """Discover entry points and attach static manifests without loading code."""
    discovered: list[DiscoveredPlugin] = []
    diagnostics: list[Diagnostic] = []
    seen_names: dict[str, str] = {}

    for ep in _iter_entry_points(group):
        dist = getattr(ep, "dist", None)
        dist_name = str(dist.metadata["Name"]) if dist is not None else None
        dist_version = str(dist.version) if dist is not None else None
        manifest: PluginManifest | None = None
        digest: str | None = None
        protocol: str | None = None
        capabilities: tuple[str, ...] = ()
        engine: str | None = None
        provenance: dict[str, Any] = {}

        if dist is not None:
            manifest, m_diags = load_manifest_from_distribution(dist)
            diagnostics.extend(m_diags)
            manifest_errors = [d for d in m_diags if d.severity == Severity.ERROR]
            if manifest is None or manifest_errors:
                # Digest/parse/identity failures must not discover a loadable EP.
                continue
            digest = manifest.digest
            provenance = dict(manifest.provenance)
            entry = manifest.entry_for(group=group, name=ep.name)
            if entry is None:
                diagnostics.append(
                    Diagnostic(
                        code="PMPLUG416",
                        severity=Severity.ERROR,
                        message=(
                            f"Entry point {group}:{ep.name} is not declared in "
                            f"manifest for {dist_name!r}."
                        ),
                        path=("plugin", dist_name or ep.name),
                        phase="plugin_evaluate",
                    )
                )
                continue
            # Target mismatch = tampering / identity failure.
            if entry.target != ep.value:
                diagnostics.append(
                    Diagnostic(
                        code="PMPLUG417",
                        severity=Severity.ERROR,
                        message=(
                            f"Entry point target mismatch for {group}:{ep.name}: "
                            f"manifest={entry.target!r} installed={ep.value!r}."
                        ),
                        path=("plugin", dist_name or ep.name),
                        phase="plugin_evaluate",
                    )
                )
                continue
            protocol = entry.protocol
            capabilities = entry.capabilities or manifest.capabilities
            engine = entry.engine
            if protocol and not manifest.protocol_compatible(protocol):
                diagnostics.append(
                    Diagnostic(
                        code="PMPLUG418",
                        severity=Severity.ERROR,
                        message=(
                            f"Protocol {protocol!r} outside manifest range "
                            f"{manifest.protocol_range!r} for {dist_name!r}."
                        ),
                        path=("plugin", dist_name or ep.name),
                        phase="plugin_evaluate",
                    )
                )
                continue
        else:
            diagnostics.append(
                Diagnostic(
                    code="PMPLUG419",
                    severity=Severity.WARNING,
                    message=(
                        f"Entry point {group}:{ep.name} has no distribution metadata; "
                        "cannot verify static manifest."
                    ),
                    path=("plugin", ep.name),
                    phase="plugin_discover",
                )
            )

        if ep.name in seen_names:
            diagnostics.append(
                Diagnostic(
                    code="PMPLUG420",
                    severity=Severity.ERROR,
                    message=(
                        f"Duplicate entry point name {ep.name!r} in group {group!r} "
                        f"(also from {seen_names[ep.name]!r})."
                    ),
                    path=("plugin", ep.name),
                    phase="plugin_evaluate",
                )
            )
            continue
        seen_names[ep.name] = dist_name or ep.value

        discovered.append(
            DiscoveredPlugin(
                group=group,
                name=ep.name,
                target=ep.value,
                distribution_name=dist_name,
                distribution_version=dist_version,
                entry_point=ep,
                manifest=manifest,
                digest=digest,
                protocol=protocol,
                capabilities=capabilities,
                engine=engine,
                provenance=provenance,
            )
        )
    return discovered, diagnostics


def evaluate_discovered(
    discovered: list[DiscoveredPlugin],
    *,
    required_protocol: str | None = None,
) -> list[Diagnostic]:
    """Additional evaluation checks (protocol range against caller requirement)."""
    diagnostics: list[Diagnostic] = []
    for item in discovered:
        if item.manifest is None:
            continue
        if required_protocol and not item.manifest.protocol_compatible(
            required_protocol
        ):
            diagnostics.append(
                Diagnostic(
                    code="PMPLUG418",
                    severity=Severity.ERROR,
                    message=(
                        f"Required protocol {required_protocol!r} outside range "
                        f"{item.manifest.protocol_range!r} for "
                        f"{item.distribution_name!r}."
                    ),
                    path=("plugin", item.distribution_name or item.name),
                    phase="plugin_evaluate",
                )
            )
    return diagnostics


def authorize_plugins(
    discovered: list[DiscoveredPlugin],
    profile: Profile | None,
    *,
    run_id: str = "plan",
) -> tuple[list[DiscoveredPlugin], list[Diagnostic], list[SecurityEvent]]:
    """Authorize plugins by allowlist before any entry-point import."""
    from etlantic.plugin_lifecycle.policies import policy_for_profile

    return policy_for_profile(profile).authorize(discovered, profile, run_id=run_id)


def _with_auth(item: DiscoveredPlugin, authorization: str) -> DiscoveredPlugin:
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
    *,
    run_id: str,
    item: DiscoveredPlugin,
    outcome: str,
    message: str,
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


def load_authorized_plugins(
    authorized: list[DiscoveredPlugin],
    *,
    key_fn: Callable[[DiscoveredPlugin, Any], str] | None = None,
    instantiate: bool = True,
    production: bool = False,
) -> tuple[dict[str, Any], list[Diagnostic]]:
    """Load entry points only for previously authorized plugins."""
    from etlantic.plugin_trust import stamp_plugin_package_identity

    loaded: dict[str, Any] = {}
    diagnostics: list[Diagnostic] = []
    for item in authorized:
        if item.authorization != "allowed":
            continue
        try:
            factory = item.entry_point.load()
            plugin = factory() if instantiate and callable(factory) else factory
            package = None
            if item.manifest is not None:
                package = getattr(item.manifest, "package", None)
            stamp_plugin_package_identity(
                plugin,
                distribution_name=item.distribution_name,
                package=package or item.distribution_name,
                distribution_version=item.distribution_version,
            )
            if key_fn is not None:
                key = key_fn(item, plugin)
            else:
                key = (
                    item.engine
                    or getattr(getattr(plugin, "info", None), "engine", None)
                    or item.name
                )
            loaded[str(key)] = plugin
        except Exception as exc:
            msg = (
                f"Failed to load authorized plugin entry point "
                f"{item.group}:{item.name}: {exc}"
            )
            severity = Severity.ERROR if production else Severity.WARNING
            if production:
                _LOG.error(msg)
            else:
                _LOG.warning(msg)
                warnings.warn(msg, RuntimeWarning, stacklevel=2)
            diagnostics.append(
                Diagnostic(
                    code="PMPLUG424",
                    severity=severity,
                    message=msg,
                    path=("plugin", item.distribution_name or item.name),
                    phase="plugin_load",
                )
            )
    return loaded, diagnostics


def discover_evaluate_authorize_load(
    group: str,
    *,
    profile: Profile | None = None,
    required_protocol: str | None = None,
    run_id: str = "plan",
    key_fn: Callable[[DiscoveredPlugin, Any], str] | None = None,
    require_manifest: bool | None = None,
) -> PluginLifecycleResult:
    """Run the full 0.20 plugin lifecycle for one entry-point group."""
    result = PluginLifecycleResult()
    discovered, d_diags = discover_entry_points(group)
    result.diagnostics.extend(d_diags)
    result.discovered = discovered

    production = is_production_profile(profile) if profile is not None else False
    must_have_manifest = (
        require_manifest if require_manifest is not None else production
    )
    if must_have_manifest:
        kept: list[DiscoveredPlugin] = []
        for item in discovered:
            if item.manifest is None:
                result.diagnostics.append(
                    Diagnostic(
                        code="PMPLUG413",
                        severity=Severity.ERROR,
                        message=(
                            f"Missing static manifest for {group}:{item.name}; "
                            "failing closed."
                        ),
                        path=("plugin", item.distribution_name or item.name),
                        phase="plugin_evaluate",
                    )
                )
            else:
                kept.append(item)
        discovered = kept
        result.discovered = discovered

    result.diagnostics.extend(
        evaluate_discovered(discovered, required_protocol=required_protocol)
    )
    # In production / require_manifest mode, drop packages with evaluate errors.
    if must_have_manifest:
        error_plugins = {
            d.path[-1] if d.path else None
            for d in result.diagnostics
            if d.severity is Severity.ERROR and d.phase == "plugin_evaluate"
        }
        if error_plugins:
            discovered = [
                item
                for item in discovered
                if (item.distribution_name or item.name) not in error_plugins
                and item.name not in error_plugins
            ]
            result.discovered = discovered

    authorized, a_diags, events = authorize_plugins(discovered, profile, run_id=run_id)
    result.diagnostics.extend(a_diags)
    result.authorized = authorized
    result.security_events.extend(events)
    result.trust_records = [item.trust_record() for item in authorized]

    probe_enabled = bool(profile is not None and profile.require_plugin_probe)
    if probe_enabled:
        from etlantic.capability_probe import (
            CapabilityProbeConfig,
            run_capability_probe,
        )

        probe_config = CapabilityProbeConfig(enabled=True)
        probed: list[DiscoveredPlugin] = []
        for item in authorized:
            if item.authorization != "allowed":
                continue
            probe = run_capability_probe(
                group=item.group,
                name=item.name,
                target=item.target,
                config=probe_config,
                run_id=run_id,
            )
            result.diagnostics.extend(probe.diagnostics)
            if probe.event is not None:
                result.security_events.append(probe.event)
            if probe.ok:
                probed.append(item)
            else:
                result.diagnostics.append(
                    Diagnostic(
                        code="PMPLUG432",
                        severity=Severity.ERROR,
                        message=(
                            f"Capability probe required but failed for "
                            f"{item.group}:{item.name}."
                        ),
                        path=("plugin", item.distribution_name or item.name),
                        phase="plugin_probe",
                    )
                )
        authorized = probed

    loaded, l_diags = load_authorized_plugins(
        authorized,
        key_fn=key_fn,
        production=production,
    )
    result.diagnostics.extend(l_diags)
    result.loaded = loaded
    return result
