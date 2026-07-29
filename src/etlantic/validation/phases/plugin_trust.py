"""Plugin trust validation phase."""

from __future__ import annotations

from typing import TYPE_CHECKING

from etlantic.diagnostics import Diagnostic

if TYPE_CHECKING:
    from etlantic.registry import PlanningContext


def phase_plugin_trust(context: PlanningContext) -> list[Diagnostic]:
    """Enforce production plugin_allowlist fail-closed (empty list is an error)."""
    from etlantic.plugin_trust import (
        _NON_BLOCKING_TRUST_CODES,
        filter_plugins_by_allowlist,
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
    for name, descriptor in context.registry.plugins.items():
        engine = getattr(descriptor, "engine", None)
        if name in selected_engines or engine in selected_engines:
            selected[name] = descriptor

    compilers = discover_transform_compilers_for_profile(profile)
    transform_diags = list(
        getattr(discover_transform_compilers_for_profile, "last_diagnostics", []) or []
    )
    for engine, compiler in compilers.items():
        if engine in selected_engines:
            selected[f"transform_compiler:{engine}"] = compiler

    _kept, diagnostics = filter_plugins_by_allowlist(selected, profile)
    # Sibling allowlist denials from transform discovery are expected when other
    # packages remain installed; do not fail validation for non-selected engines.
    filtered_transform = [
        d
        for d in transform_diags
        if getattr(d, "code", None) not in _NON_BLOCKING_TRUST_CODES
    ]
    return list(diagnostics) + filtered_transform
