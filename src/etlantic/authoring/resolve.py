"""Policy-governed resolution of definition references into planning context."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from etlantic.authoring.definition import PipelineDefinition
from etlantic.authoring.normalize import definition_from_pipeline
from etlantic.diagnostics import Diagnostic, Severity, ValidationReport
from etlantic.identity import implementation_id
from etlantic.pipeline import Pipeline
from etlantic.registry import ImplementationDescriptor, PlanningContext
from etlantic.transformation import ImplementationRecord, Step, Transformation


@dataclass
class CallableRegistry:
    """Process-scoped host registry of native implementation callables.

    Deserialized JSON never populates this registry. Hosts register callables
    explicitly after loading a definition (or they are harvested from classes).
    """

    callables: dict[str, ImplementationRecord] = field(default_factory=dict)

    def register(
        self,
        transformation_id: str,
        engine: str,
        fn: Callable[..., Any],
        *,
        identity: str | None = None,
    ) -> ImplementationRecord:
        key = f"{transformation_id}::{engine}"
        record = ImplementationRecord(
            engine=engine,
            identity=identity or implementation_id(transformation_id, engine),
            callable=fn,
            is_async=inspect.iscoroutinefunction(fn),
            signature=inspect.signature(fn),
        )
        self.callables[key] = record
        return record

    def get(self, transformation_id: str, engine: str) -> ImplementationRecord | None:
        return self.callables.get(f"{transformation_id}::{engine}")

    def get_by_identity(self, identity: str) -> ImplementationRecord | None:
        for record in self.callables.values():
            if record.identity == identity:
                return record
        return None


_GLOBAL_CALLABLES = CallableRegistry()


def callable_registry() -> CallableRegistry:
    """Return the process-local callable registry used by definition runs."""
    return _GLOBAL_CALLABLES


def harvest_callables_from_pipeline(cls: type[Pipeline]) -> None:
    """Register native implementations discovered on a pipeline class."""
    members = getattr(cls, "__pipeline_members__", {})
    for member in members.values():
        if not isinstance(member, Step):
            continue
        transform = member.transformation
        for engine, record in transform.implementations().items():
            callable_registry().callables[
                f"{transform.identity()}::{engine}"
            ] = record


def harvest_callables_from_definition_context(
    defn: PipelineDefinition,
    *,
    transforms: Mapping[str, type[Transformation]] | None = None,
) -> None:
    """Harvest callables from known transformation classes when available."""
    transforms = transforms or {}
    for xf_def in defn.transformations:
        xf = transforms.get(xf_def.identity)
        if xf is None:
            for candidate in _all_transformation_subclasses():
                if candidate.identity() == xf_def.identity:
                    xf = candidate
                    break
        if xf is None:
            continue
        for engine, record in xf.implementations().items():
            callable_registry().callables[f"{xf.identity()}::{engine}"] = record


def _all_transformation_subclasses() -> list[type[Transformation]]:
    found: list[type[Transformation]] = []
    stack = list(Transformation.__subclasses__())
    while stack:
        cls = stack.pop()
        found.append(cls)
        stack.extend(cls.__subclasses__())
    return found


def resolve_definition(
    pipeline: type[Pipeline] | PipelineDefinition,
    *,
    context: PlanningContext | None = None,
    profile: str | Any | None = None,
) -> tuple[PipelineDefinition, PlanningContext, ValidationReport]:
    """Resolve registry references for a class or definition.

    Structural data is never executed. Missing implementations produce
    diagnostics; production plugin allowlists remain fail-closed via normal
    validation.
    """
    ctx = context or PlanningContext.create(profile=profile)
    if isinstance(pipeline, type) and issubclass(pipeline, Pipeline):
        defn = definition_from_pipeline(pipeline)
        harvest_callables_from_pipeline(pipeline)
    else:
        assert isinstance(pipeline, PipelineDefinition)
        defn = pipeline
        harvest_callables_from_definition_context(defn)

    diagnostics: list[Diagnostic] = []
    for xf in defn.transformations:
        for ref in xf.implementation_refs:
            key = f"{xf.identity}::{ref.engine}"
            if key not in ctx.registry.implementations:
                ctx.registry.register_implementation(
                    ImplementationDescriptor(
                        transformation_id=xf.identity,
                        engine=ref.engine,
                        identity=ref.identity,
                        is_async=ref.is_async,
                        kind=ref.kind,
                        portable_plan=(
                            dict(xf.portable_plan)
                            if xf.portable_plan is not None and ref.kind != "native"
                            else None
                        ),
                    )
                )
            live = callable_registry().get(xf.identity, ref.engine)
            if live is None and ref.kind == "native":
                diagnostics.append(
                    Diagnostic(
                        code="PMAUTH410",
                        severity=Severity.WARNING,
                        message=(
                            f"No live callable registered for {xf.identity} "
                            f"engine {ref.engine!r}; planning may succeed but "
                            "execution will fail until the host registers it."
                        ),
                        path=("transformations", xf.identity, "implementation_refs", ref.engine),
                        phase="reference",
                    )
                )

    return defn, ctx, ValidationReport.from_diagnostics(diagnostics)
