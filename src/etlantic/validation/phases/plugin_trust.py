"""Plugin trust validation phase."""

from __future__ import annotations

from typing import TYPE_CHECKING

from etlantic.diagnostics import Diagnostic, Severity

if TYPE_CHECKING:
    from etlantic.registry import PlanningContext


def phase_plugin_trust(context: PlanningContext) -> list[Diagnostic]:
    """Enforce production plugin_allowlist fail-closed (empty list is an error)."""
    from etlantic.plugin_trust import (
        filter_plugins_by_allowlist,
        is_non_blocking_trust_diagnostic,
        is_production_profile,
    )
    from etlantic.transform.discovery import discover_transform_compilers_for_profile

    profile = context.profile
    selected: dict[str, object] = {}
    selected_engines = {
        eng
        for eng in (
            profile.dataframe_engine,
            profile.sql_engine,
            profile.spark_engine,
            profile.orchestrator,
        )
        if eng
    }
    present_engines: set[str] = set()
    for name, descriptor in context.registry.plugins.items():
        engine = getattr(descriptor, "engine", None)
        if name in selected_engines or engine in selected_engines:
            selected[name] = descriptor
            present_engines.add(str(name))
            if engine:
                present_engines.add(str(engine))

    compilers = discover_transform_compilers_for_profile(profile)
    transform_diags = list(
        getattr(discover_transform_compilers_for_profile, "last_diagnostics", []) or []
    )
    for engine, compiler in compilers.items():
        if engine in selected_engines:
            selected[f"transform_compiler:{engine}"] = compiler
            present_engines.add(str(engine))

    _kept, diagnostics = filter_plugins_by_allowlist(selected, profile)
    # Sibling discovery denials (phase=plugin_discovery) stay non-blocking.
    filtered_transform = [
        d for d in transform_diags if not is_non_blocking_trust_diagnostic(d)
    ]
    out = list(diagnostics) + filtered_transform

    # Selected engines denied at discovery never enter the registry; surface an
    # explicit blocking trust diagnostic instead of a bare capability miss.
    if is_production_profile(profile) and selected_engines:
        for engine in sorted(selected_engines):
            if engine in present_engines:
                continue
            out.append(
                Diagnostic(
                    code="PMPLUG404",
                    severity=Severity.ERROR,
                    message=(
                        f"Selected engine {engine!r} is not available after "
                        f"production plugin authorization for profile "
                        f"{profile.name!r}; treat as trust failure "
                        "(allowlist denial or load failure)."
                    ),
                    path=("profile", "engine", str(engine)),
                    phase="plugin_trust",
                )
            )
    return out
