"""Optimization pass discovery, allowlisting, and deterministic ordering."""

from __future__ import annotations

import contextlib
from importlib.metadata import entry_points
from typing import Any

from etlantic.optimization.diagnostics import optimization_diagnostic
from etlantic.optimization.passes import REFERENCE_PASSES
from etlantic.optimization.protocol import OptimizationPass, PassMetadata
from etlantic.profile import Profile

ENTRY_POINT_GROUP = "etlantic.optimization_passes"


def builtin_passes() -> tuple[OptimizationPass, ...]:
    """Return built-in reference passes in declaration order."""
    return tuple(REFERENCE_PASSES)


def discover_optimization_passes(
    *,
    include_entry_points: bool = True,
    include_builtin: bool = True,
) -> tuple[OptimizationPass, ...]:
    """Discover built-in and entry-point optimization passes."""
    found: list[OptimizationPass] = []
    if include_builtin:
        found.extend(REFERENCE_PASSES)
    if include_entry_points:
        try:
            eps = entry_points()
            if hasattr(eps, "select"):
                selected = eps.select(group=ENTRY_POINT_GROUP)
            else:
                selected = eps.get(ENTRY_POINT_GROUP, [])  # type: ignore[attr-defined]
        except Exception:
            selected = []
        for ep in selected:
            try:
                loaded = ep.load()
            except Exception:
                continue
            if callable(loaded) and not isinstance(loaded, type):
                with contextlib.suppress(TypeError):
                    loaded = loaded()
            if hasattr(loaded, "metadata") and hasattr(loaded, "propose"):
                found.append(loaded)  # type: ignore[arg-type]
    return tuple(found)


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
                if production:
                    diagnostics.append(
                        optimization_diagnostic(
                            "pass_not_allowlisted",
                            f"Optimization pass {meta.pass_id!r} is not allowlisted",
                            severity="error",
                            path=("optimization", "allowlist", meta.pass_id),
                        )
                    )
                continue
            pin = allowlist.get(meta.pass_id)
            if pin not in (None, "") and str(pin) != meta.version:
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
        by_id[meta.pass_id] = pass_obj

    if explicit_ids is not None:
        ordered = tuple(by_id[i] for i in explicit_ids if i in by_id)
        return ordered, tuple(diagnostics)

    ordered_list = sorted(
        by_id.values(),
        key=lambda p: (int(p.metadata.priority), str(p.metadata.pass_id)),
    )
    return tuple(ordered_list), tuple(diagnostics)
