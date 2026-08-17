"""Public ``compile_plan`` entry point for external orchestration."""

from __future__ import annotations

from typing import Any

from etlantic.exceptions import ETLanticError
from etlantic.orchestration.discovery import (
    discover_orchestrator_plugins,
    load_orchestrator_plugin,
)
from etlantic.orchestration.mapping import context_from_profile
from etlantic.orchestration.protocol import (
    ORCHESTRATION_PROTOCOL_VERSION,
    CompilationContext,
    CompilationDiagnostic,
    CompiledOrchestrationArtifact,
    OrchestratorPlugin,
)
from etlantic.plan.model import PipelinePlan
from etlantic.profile import Profile, resolve_profile


class OrchestrationCompilationError(ETLanticError):
    """Raised when orchestration compilation fails closed."""

    def __init__(
        self,
        message: str,
        *,
        diagnostics: list[CompilationDiagnostic] | None = None,
        code: str = "PMORCH300",
    ) -> None:
        super().__init__(message)
        self.diagnostics = list(diagnostics or [])
        self.code = code


def _assert_capabilities(
    plugin: OrchestratorPlugin,
    context: CompilationContext,
) -> list[CompilationDiagnostic]:
    caps = plugin.capabilities()
    diagnostics: list[CompilationDiagnostic] = []
    for req in context.required_capabilities:
        if not caps.supports(req):
            diagnostics.append(
                CompilationDiagnostic(
                    code="PMORCH301",
                    severity="error",
                    message=(
                        f"Orchestrator {plugin.info.engine!r} does not support "
                        f"required capability {req!r}."
                    ),
                    subject_id=req,
                )
            )
    return diagnostics


def _assert_streaming_control(
    plugin: OrchestratorPlugin,
    plan: PipelinePlan,
) -> list[CompilationDiagnostic]:
    from etlantic.streaming.plan_meta import graph_required_streaming_extras

    required = graph_required_streaming_extras(plan.logical_graph)
    if not required:
        meta = dict(plan.metadata or {})
        if "etlantic.expansion" in meta or "etlantic.streaming" in meta:
            required = ("control.expansion",)
    if not required:
        return []
    caps = plugin.capabilities()
    diagnostics: list[CompilationDiagnostic] = []
    for extra in required:
        if not caps.supports(extra):
            diagnostics.append(
                CompilationDiagnostic(
                    code="PMDYN130",
                    severity="error",
                    message=(
                        f"Orchestrator {plugin.info.engine!r} cannot preserve "
                        f"required dynamic/stream extra {extra!r}; refusing to "
                        "flatten into an inequivalent static DAG."
                    ),
                    subject_id=extra,
                )
            )
    return diagnostics


def compile_plan(
    plan: PipelinePlan,
    *,
    target: str = "airflow",
    profile: Profile | str | None = None,
    plugin: OrchestratorPlugin | None = None,
    context: CompilationContext | None = None,
    plugins: dict[str, OrchestratorPlugin] | None = None,
    allow_adhoc_profile: bool = False,
) -> CompiledOrchestrationArtifact:
    """Compile a secret-free :class:`~etlantic.plan.model.PipelinePlan` into an orchestration artifact.

    Verifies the plan fingerprint, resolves the target orchestrator plugin
    (discovered entry points or explicit ``plugin``), and fails closed when
    required capabilities are missing or compilation diagnostics contain errors.

    Args:
        plan: Resolved plan to compile. Must include a valid ``fingerprint``.
        target: Orchestrator engine id (default ``"airflow"``).
        profile: Optional profile for compilation context and plugin discovery.
        plugin: Optional pre-constructed orchestrator plugin instance.
        context: Optional explicit :class:`~etlantic.orchestration.protocol.CompilationContext`.
        plugins: Optional pre-discovered plugin mapping (``engine`` → plugin).
        allow_adhoc_profile: Forwarded to :func:`~etlantic.profile.resolve_profile`.

    Returns:
        :class:`~etlantic.orchestration.protocol.CompiledOrchestrationArtifact`
        with secret-free source/metadata suitable for DAG check-in.

    Raises:
        ValueError: When :func:`~etlantic.plan.serialize.verify_plan_fingerprint`
            fails.
        OrchestrationCompilationError: When the plugin is missing or compilation
            diagnostics include errors (codes such as ``PMORCH300``).
    """
    from etlantic.plan.serialize import verify_plan_fingerprint

    verify_plan_fingerprint(plan)
    resolved_profile = (
        resolve_profile(profile, allow_adhoc_profile=allow_adhoc_profile)
        if profile is not None
        else None
    )
    if context is None:
        if resolved_profile is not None:
            context = context_from_profile(resolved_profile, target=target)
        else:
            context = CompilationContext(target=target)

    if plugin is None:
        discovered = (
            plugins
            if plugins is not None
            else discover_orchestrator_plugins(profile=resolved_profile)
        )
        plugin = discovered.get(target)
        if plugin is None and plugins is None:
            plugin = load_orchestrator_plugin(target, profile=resolved_profile)

    if plugin is None:
        raise OrchestrationCompilationError(
            f"No orchestrator plugin available for target {target!r}. "
            "Install etlantic-airflow (or another orchestrator plugin) and ensure "
            "it is discoverable via entry points.",
            code="PMORCH300",
            diagnostics=[
                CompilationDiagnostic(
                    code="PMORCH300",
                    severity="error",
                    message=f"Missing orchestrator plugin for {target!r}",
                    subject_id=target,
                )
            ],
        )

    cap_diags = _assert_capabilities(plugin, context)
    cap_diags.extend(_assert_streaming_control(plugin, plan))
    cap_errors = [d for d in cap_diags if d.severity == "error"]
    if cap_errors:
        raise OrchestrationCompilationError(
            f"Orchestration compilation to {target!r} failed with "
            f"{len(cap_errors)} error(s): {cap_errors[0].message}",
            diagnostics=cap_diags,
            code=cap_errors[0].code,
        )
    artifact = plugin.compile(plan, context=context)
    all_diags = list(cap_diags) + list(artifact.diagnostics)
    errors = [d for d in all_diags if d.severity == "error"]
    if errors:
        raise OrchestrationCompilationError(
            f"Orchestration compilation to {target!r} failed with "
            f"{len(errors)} error(s): {errors[0].message}",
            diagnostics=all_diags,
            code=errors[0].code,
        )

    # Ensure protocol metadata is stamped.
    if not artifact.protocol_version:
        artifact.protocol_version = ORCHESTRATION_PROTOCOL_VERSION
    if not artifact.plan_id:
        artifact.plan_id = plan.plan_id
    if not artifact.pipeline_id:
        artifact.pipeline_id = plan.pipeline_id
    if not artifact.fingerprint:
        artifact.fingerprint = plan.fingerprint
    if all_diags and not artifact.diagnostics:
        artifact.diagnostics = tuple(all_diags)
    elif cap_diags:
        artifact.diagnostics = tuple([*artifact.diagnostics, *cap_diags])
    return artifact


def explain_compilation(artifact: CompiledOrchestrationArtifact) -> dict[str, Any]:
    """Return a JSON-friendly compilation explanation."""
    return artifact.explain()
