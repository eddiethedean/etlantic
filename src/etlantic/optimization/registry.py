"""Optimization pass discovery, allowlisting, and deterministic ordering."""

from __future__ import annotations

import contextlib
from importlib.metadata import entry_points
from typing import Any

from etlantic.optimization.diagnostics import optimization_diagnostic
from etlantic.optimization.passes import REFERENCE_PASSES
from etlantic.optimization.protocol import OptimizationPass, PassMetadata
from etlantic.plugin_trust import plugin_allowed
from etlantic.profile import Profile

ENTRY_POINT_GROUP = "etlantic.optimization_passes"


def builtin_passes() -> tuple[OptimizationPass, ...]:
    """Return built-in reference passes in declaration order."""
    return tuple(REFERENCE_PASSES)


def _entry_point_group() -> list[Any]:
    try:
        eps = entry_points()
        if hasattr(eps, "select"):
            return list(eps.select(group=ENTRY_POINT_GROUP))
        return list(eps.get(ENTRY_POINT_GROUP, []))  # type: ignore[attr-defined]
    except Exception:
        return []


def _load_entry_point(ep: Any) -> OptimizationPass | None:
    try:
        loaded = ep.load()
    except Exception:
        return None
    if callable(loaded) and not isinstance(loaded, type):
        with contextlib.suppress(TypeError):
            loaded = loaded()
    if hasattr(loaded, "metadata") and hasattr(loaded, "propose"):
        return loaded  # type: ignore[return-value]
    return None


def _may_load_entry_point(ep_name: str, *, profile: Profile | None) -> bool:
    """Return True when an entry point may be imported (allowlist-before-load)."""
    if profile is None:
        return True
    allowlist = dict(getattr(profile, "optimization_pass_allowlist", {}) or {})
    production = str(getattr(profile, "security_mode", "development")) == "production"
    if production:
        # Fail closed: never import undeclared passes in production.
        return ep_name in allowlist
    if allowlist:
        return ep_name in allowlist
    return True


def discover_optimization_passes(
    *,
    include_entry_points: bool = True,
    include_builtin: bool = True,
    profile: Profile | None = None,
) -> tuple[OptimizationPass, ...]:
    """Discover built-in and entry-point optimization passes.

    Entry points are loaded only after allowlist checks (production fail-closed).
    """
    found: list[OptimizationPass] = []
    if include_builtin:
        found.extend(REFERENCE_PASSES)
    if include_entry_points:
        for ep in _entry_point_group():
            name = str(getattr(ep, "name", "") or "")
            if not name or not _may_load_entry_point(name, profile=profile):
                continue
            loaded = _load_entry_point(ep)
            if loaded is not None:
                found.append(loaded)
    return tuple(found)


def _pin_matches(version: str, pin: str | None) -> bool:
    if pin in (None, ""):
        return True
    return plugin_allowed(
        name="pass",
        version=version,
        allowlist={"pass": pin},
        require_pin=True,
    )


def resolve_pass_order(
    passes: tuple[OptimizationPass, ...] | list[OptimizationPass],
    *,
    profile: Profile,
    explicit_ids: tuple[str, ...] | None = None,
) -> tuple[tuple[OptimizationPass, ...], tuple[Any, ...]]:
    """Filter by allowlist (production fail-closed) and sort deterministically.

    Ordering: explicit_ids (if provided), else (priority asc, pass_id asc).
    """
    diagnostics: list[Any] = []
    allowlist = dict(getattr(profile, "optimization_pass_allowlist", {}) or {})
    production = str(getattr(profile, "security_mode", "development")) == "production"

    by_id: dict[str, OptimizationPass] = {}
    for pass_obj in passes:
        meta = pass_obj.metadata
        if not isinstance(meta, PassMetadata):
            continue
        if production or allowlist:
            if meta.pass_id not in allowlist:
                severity = "error" if production else "warning"
                diagnostics.append(
                    optimization_diagnostic(
                        "pass_not_allowlisted",
                        f"Optimization pass {meta.pass_id!r} is not allowlisted",
                        severity=severity,
                        path=("optimization", "allowlist", meta.pass_id),
                    )
                )
                continue
            pin = allowlist.get(meta.pass_id)
            if not _pin_matches(meta.version, pin if pin is None else str(pin)):
                diagnostics.append(
                    optimization_diagnostic(
                        "pass_not_allowlisted",
                        f"Optimization pass {meta.pass_id!r} version {meta.version!r} "
                        f"does not match pin {pin!r}",
                        severity="error",
                        path=("optimization", "allowlist", meta.pass_id),
                    )
                )
                continue
        if meta.pass_id in by_id:
            diagnostics.append(
                optimization_diagnostic(
                    "pass_not_allowlisted",
                    f"Duplicate optimization pass id {meta.pass_id!r}; last registration wins",
                    severity="error" if production else "warning",
                    path=("optimization", "allowlist", meta.pass_id),
                )
            )
        by_id[meta.pass_id] = pass_obj

    if explicit_ids is not None:
        ordered = tuple(by_id[i] for i in explicit_ids if i in by_id)
        return ordered, tuple(diagnostics)

    ordered_list = sorted(
        by_id.values(),
        key=lambda p: (int(p.metadata.priority), str(p.metadata.pass_id)),
    )
    return tuple(ordered_list), tuple(diagnostics)
