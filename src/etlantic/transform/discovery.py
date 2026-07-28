"""Entry-point discovery for portable transform compilers."""

from __future__ import annotations

import warnings
from typing import Any

from etlantic.plugin_lifecycle import discover_evaluate_authorize_load
from etlantic.profile import Profile
from etlantic.registry import PluginDescriptor, RegistryBundle
from etlantic.transform.compiler import PortableTransformCompiler

TRANSFORM_COMPILER_ENTRY_POINT = "etlantic.transform_compilers"


def _key(item: Any, compiler: Any) -> str:
    engine_key = str(item.name)
    info_engine = getattr(getattr(compiler, "info", None), "engine", None)
    if info_engine is not None and str(info_engine) != engine_key:
        warnings.warn(
            f"Transform compiler entry point {engine_key!r} reports "
            f"info.engine={info_engine!r}; the entry-point name is the "
            "stable discovery key.",
            RuntimeWarning,
            stacklevel=3,
        )
    if not isinstance(compiler, PortableTransformCompiler):
        missing = [
            name
            for name in ("info", "analyze", "compile", "execute")
            if not hasattr(compiler, name)
        ]
        if missing:
            raise TypeError(
                f"entry point {engine_key!r} does not implement "
                f"PortableTransformCompiler (missing {missing})"
            )
    return engine_key


def discover_transform_compilers() -> dict[str, PortableTransformCompiler]:
    """Discover compilers (open allowlist) with authorize-before-load.

    Parameterless for monkeypatch compatibility in unit tests. Profile-aware
    discovery uses :func:`discover_transform_compilers_for_profile`.
    """
    result = discover_evaluate_authorize_load(
        TRANSFORM_COMPILER_ENTRY_POINT,
        profile=None,
        key_fn=_key,
    )
    return result.loaded  # type: ignore[return-value]


discover_transform_compilers._etlantic_lifecycle = True  # type: ignore[attr-defined]


def register_discovered_compilers(
    registry: RegistryBundle,
    *,
    compilers: dict[str, PortableTransformCompiler] | None = None,
    profile: Profile | None = None,
) -> dict[str, PortableTransformCompiler]:
    """Register discovered transform compilers into a planning registry."""
    discovered = (
        compilers
        if compilers is not None
        else discover_transform_compilers_for_profile(profile)
    )
    for engine, compiler in discovered.items():
        info = compiler.info
        registry.register_plugin(
            PluginDescriptor(
                name=info.name,
                kind="transform_compiler",
                version=info.version,
                engine=info.engine or engine,
                capabilities=None,
                metadata={
                    "compiler_protocol": info.compiler_protocol,
                    "dtcs_plan_versions": list(info.dtcs_plan_versions),
                    "transform_capabilities": info.capabilities.to_dict(),
                },
            )
        )
    return discovered


def load_transform_compiler(
    engine: str,
    *,
    profile: Profile | None = None,
) -> PortableTransformCompiler | None:
    """Return a discovered compiler for ``engine``, or None."""
    return discover_transform_compilers_for_profile(profile).get(engine)


def compiler_registry_snapshot(
    *,
    profile: Profile | None = None,
) -> list[dict[str, Any]]:
    """Return serializable descriptors for discovered compilers."""
    return [
        c.info.to_dict()
        for c in discover_transform_compilers_for_profile(profile).values()
    ]


def discover_transform_compilers_for_profile(
    profile: Any | None,
) -> dict[str, PortableTransformCompiler]:
    """Discover compilers applying ``profile.plugin_allowlist`` before load.

    Honors monkeypatches of :func:`discover_transform_compilers` (tests).

    Allowlist/trust diagnostics from the latest call are exposed on
    ``discover_transform_compilers_for_profile.last_diagnostics`` so callers
    can surface ``PMPLUG401``/``PMPLUG402`` instead of a false "no compiler".
    """
    discover_transform_compilers_for_profile.last_diagnostics = []  # type: ignore[attr-defined]
    discover = discover_transform_compilers
    if getattr(discover, "_etlantic_lifecycle", False):
        result = discover_evaluate_authorize_load(
            TRANSFORM_COMPILER_ENTRY_POINT,
            profile=profile,
            key_fn=_key,
        )
        from etlantic.diagnostics import Severity
        from etlantic.exceptions import PipelineExecutionError

        diagnostics = list(result.diagnostics)
        discover_transform_compilers_for_profile.last_diagnostics = diagnostics  # type: ignore[attr-defined]
        from etlantic.plugin_trust import loaded_plugins_after_trust

        return loaded_plugins_after_trust(result)  # type: ignore[return-value]

    found = discover()
    if profile is None:
        return found
    from etlantic.diagnostics import Severity
    from etlantic.exceptions import PipelineExecutionError
    from etlantic.plugin_trust import (
        _NON_BLOCKING_TRUST_CODES,
        filter_plugins_by_allowlist,
    )

    kept, diagnostics = filter_plugins_by_allowlist(found, profile)
    discover_transform_compilers_for_profile.last_diagnostics = list(diagnostics)  # type: ignore[attr-defined]
    errors = [d for d in diagnostics if d.severity is Severity.ERROR]
    blocking = [d for d in errors if d.code not in _NON_BLOCKING_TRUST_CODES]
    if blocking and kept:
        raise PipelineExecutionError(
            "; ".join(d.message for d in blocking),
            code=blocking[0].code,
        )
    return {} if blocking else kept
