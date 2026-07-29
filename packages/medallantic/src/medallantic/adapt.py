"""Lower SparkForge IR onto ETLantic via shared Medallantic lowering.

The public migrate namespace is ``medallantic.migrate.sparkforge``. Top-level
``medallantic.adapt`` / ``medallantic.ir`` remain compatibility re-exports.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from etlantic.capabilities import PluginCapabilities
from etlantic.diagnostics import Diagnostic, Severity, ValidationReport
from etlantic.pipeline import Pipeline
from etlantic.plan.model import PipelinePlan
from etlantic.policy import ValidationPolicy, register_validation_policy
from etlantic.profile import Profile
from etlantic.reliability import WriteIntent
from medallantic.compat import assert_delta_capabilities
from medallantic.ir import SparkForgePipelineSpec, StepKind
from medallantic.lower import (
    AdaptedRow,
    LoweringError,
    LoweringResult,
    MedallionRow,
    build_profile,
    build_validation_policy,
    lower_document,
)
from medallantic.schema import MedallionDocument, MedallionStep

# Re-export row contract under the historic adapter name.
__all__ = [
    "AdaptationResult",
    "AdaptedRow",
    "AdapterError",
    "MedallionRow",
    "adapt_pipeline",
    "adapt_profile",
    "adapt_validation_policy",
    "enrich_plan",
    "spec_to_document",
]


def _primary_error_code(
    diagnostics: list[Diagnostic] | tuple[Diagnostic, ...],
    fallback: str,
) -> str:
    for diagnostic in diagnostics:
        if diagnostic.severity is Severity.ERROR:
            return diagnostic.code
    return fallback


def _mdl_to_pmsf_code(code: str) -> str:
    return {
        "MDL100": "PMSF304",
        "MDL101": "PMSF305",
        "MDL102": "PMSF306",
        "MDL103": "PMSF312",
        "MDL104": "PMSF302",
        "MDL105": "PMSF307",
        "MDL106": "PMSF303",
        "MDL107": "PMSF303",
    }.get(code, "PMSF301")


class AdapterError(Exception):
    """Raised when SparkForge → ETLantic adaptation fails closed."""

    def __init__(
        self,
        message: str,
        *,
        report: ValidationReport | None = None,
        code: str = "PMSF300",
    ) -> None:
        super().__init__(message)
        self.report = report or ValidationReport()
        self.code = code


@dataclass(frozen=True, slots=True)
class AdaptationResult:
    """Result of adapting a SparkForge pipeline IR."""

    pipeline_cls: type[Pipeline]
    profile: Profile
    validation_policy: ValidationPolicy
    write_intents: tuple[WriteIntent, ...] = ()
    step_map: dict[str, str] = field(default_factory=dict)
    layer_by_node: dict[str, str] = field(default_factory=dict)
    diagnostics: tuple[Diagnostic, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    required_delta_operations: tuple[str, ...] = ()

    @property
    def definition(self):
        return LoweringResult(
            pipeline_cls=self.pipeline_cls,
            profile=self.profile,
            validation_policy=self.validation_policy,
            write_intents=self.write_intents,
            step_map=self.step_map,
            layer_by_node=self.layer_by_node,
            diagnostics=self.diagnostics,
            metadata=self.metadata,
            required_delta_operations=self.required_delta_operations,
        ).definition

    def enrich_plan(self, plan: PipelinePlan) -> PipelinePlan:
        return enrich_plan(plan, self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pipeline": self.pipeline_cls.__name__,
            "profile": self.profile.to_dict(),
            "validation_policy": self.validation_policy.to_dict(),
            "write_intents": [w.to_dict() for w in self.write_intents],
            "step_map": dict(self.step_map),
            "layer_by_node": dict(self.layer_by_node),
            "diagnostics": [
                {
                    "code": d.code,
                    "severity": d.severity.value,
                    "message": d.message,
                }
                for d in self.diagnostics
            ],
            "metadata": dict(self.metadata),
            "required_delta_operations": list(self.required_delta_operations),
        }


def enrich_plan(plan: PipelinePlan, result: AdaptationResult) -> PipelinePlan:
    """Place serialized write intents under ``plan.intents['write_intents']``."""
    write_map: dict[str, Any] = {}
    for intent in result.write_intents:
        blob = {
            "intent": intent.mode.value,
            "kind": intent.mode.value,
            "subject_id": intent.subject_id,
            "mode": intent.mode.value,
            "keys": list(intent.keys),
            "metadata": dict(intent.metadata),
        }
        write_map[intent.subject_id] = blob
        step_name = intent.metadata.get("step")
        if isinstance(step_name, str) and step_name:
            write_map[f"{step_name}_out"] = blob
            write_map[step_name] = blob
    intents = dict(plan.intents)
    intents["write_intents"] = write_map
    return replace(plan, intents=intents)


def adapt_profile(
    spec: SparkForgePipelineSpec,
    *,
    name: str | None = None,
    bindings: dict[str, str] | None = None,
) -> Profile:
    """Build an ETLantic Profile from SparkForge builder config."""
    return build_profile(spec_to_document(spec), name=name, bindings=bindings)


def adapt_validation_policy(spec: SparkForgePipelineSpec) -> ValidationPolicy:
    """Map layer thresholds onto a named ValidationPolicy (metadata only)."""
    return build_validation_policy(spec_to_document(spec))


def spec_to_document(spec: SparkForgePipelineSpec) -> MedallionDocument:
    """Convert SparkForge IR into the shared MedallionDocument."""
    steps: list[MedallionStep] = []
    for step in spec.steps:
        kind = step.kind.value
        if step.kind is StepKind.UNKNOWN:
            kind = "unknown"
        steps.append(
            MedallionStep(
                name=step.name,
                layer=step.layer.value,
                kind=kind,
                source=step.source,
                asset=step.table_name,
                transform_ref=step.transform_ref,
                rules=dict(step.rules),
                write_mode=step.write_mode,
                metadata=dict(step.metadata),
            )
        )
    return MedallionDocument(
        name=spec.name,
        schema=spec.schema,
        steps=tuple(steps),
        min_bronze_rate=spec.min_bronze_rate,
        min_silver_rate=spec.min_silver_rate,
        min_gold_rate=spec.min_gold_rate,
        engine=spec.engine,
        metadata=dict(spec.metadata),
    )


def adapt_pipeline(
    spec: SparkForgePipelineSpec,
    *,
    capabilities: PluginCapabilities | None = None,
    strict_delta: bool = True,
) -> AdaptationResult:
    """Map a SparkForge pipeline IR to a concrete ETLantic Pipeline subclass."""
    diagnostics: list[Diagnostic] = []
    _validate_spec(spec, diagnostics)

    if any(d.severity is Severity.ERROR for d in diagnostics):
        raise AdapterError(
            "Refusing to adapt invalid SparkForge pipeline IR.",
            report=ValidationReport.from_diagnostics(diagnostics),
            code=_primary_error_code(diagnostics, "PMSF301"),
        )

    for ext in spec.legacy_engine_extensions:
        diagnostics.append(
            Diagnostic(
                code="PMSF410",
                severity=Severity.WARNING,
                message=(
                    f"Legacy SparkForge engine extension {ext!r} is deprecated; "
                    "prefer ETLantic plugins (etlantic-pyspark / etlantic-sql)."
                ),
                path=("legacy_engine_extensions", ext),
                phase="sparkforge_adapter",
            )
        )

    delta_ops = tuple(str(x) for x in (spec.metadata.get("delta_operations") or ()))
    if delta_ops:
        diagnostics.extend(
            assert_delta_capabilities(
                list(delta_ops),
                capabilities=capabilities,
                strict=strict_delta,
            )
        )
        if any(d.severity is Severity.ERROR for d in diagnostics):
            raise AdapterError(
                "Delta capability requirements not met.",
                report=ValidationReport.from_diagnostics(diagnostics),
                code="PMSF320",
            )

    doc = spec_to_document(spec)
    try:
        lowered = lower_document(
            doc,
            required_delta_operations=delta_ops,
            diagnostic_phase="sparkforge_adapter",
        )
    except LoweringError as exc:
        # Preserve PMSF-facing codes for migrate callers where possible.
        code = (
            _mdl_to_pmsf_code(exc.code)
            if exc.code.startswith("MDL")
            else _primary_error_code(exc.report.diagnostics, "PMSF301")
        )
        # Remap MDL diagnostics to historic PMSF codes for IR path.
        remapped = tuple(_remap_mdl_to_pmsf(d) for d in exc.report.diagnostics)
        raise AdapterError(
            str(exc),
            report=ValidationReport.from_diagnostics([*diagnostics, *remapped]),
            code=code,
        ) from exc

    merged_diagnostics = tuple(
        [*diagnostics, *(_remap_mdl_to_pmsf(d) for d in lowered.diagnostics)]
    )
    profile = lowered.profile
    if delta_ops and not strict_delta:
        from medallantic.compat import DELTA_CAPABILITY_MAP

        extra_caps = tuple(
            DELTA_CAPABILITY_MAP[op.strip().lower()]
            for op in delta_ops
            if op.strip().lower() in DELTA_CAPABILITY_MAP
        )
        profile = profile.with_updates(
            required_spark_capabilities=tuple(
                dict.fromkeys(
                    (
                        *profile.required_spark_capabilities,
                        "spark_delta",
                        *extra_caps,
                    )
                )
            ),
            metadata={
                **profile.metadata,
                "plugin:medallantic": {
                    **dict(profile.metadata.get("plugin:medallantic") or {}),
                    "required_delta_operations": list(delta_ops),
                },
            },
        )

    register_validation_policy(lowered.validation_policy)
    return AdaptationResult(
        pipeline_cls=lowered.pipeline_cls,
        profile=profile,
        validation_policy=lowered.validation_policy,
        write_intents=lowered.write_intents,
        step_map=lowered.step_map,
        layer_by_node=lowered.layer_by_node,
        diagnostics=merged_diagnostics,
        metadata={
            **lowered.metadata,
            "migrate": "medallantic.migrate.sparkforge",
        },
        required_delta_operations=delta_ops,
    )


def _remap_mdl_to_pmsf(diagnostic: Diagnostic) -> Diagnostic:
    mapping = {
        "MDL100": "PMSF304",
        "MDL101": "PMSF305",
        "MDL102": "PMSF306",
        "MDL103": "PMSF312",
        "MDL104": "PMSF302",
        "MDL105": "PMSF307",
        "MDL106": "PMSF303",
        "MDL107": "PMSF303",
        "MDL110": "PMSF411",
        "MDL111": "PMSF411",
    }
    code = mapping.get(diagnostic.code, diagnostic.code)
    if code == diagnostic.code:
        return diagnostic
    return Diagnostic(
        code=code,
        severity=diagnostic.severity,
        message=diagnostic.message,
        path=diagnostic.path,
        help=diagnostic.help,
        related=diagnostic.related,
        source=diagnostic.source,
        metadata=diagnostic.metadata,
        phase=diagnostic.phase or "sparkforge_adapter",
        actions=diagnostic.actions,
    )


def _validate_spec(spec: SparkForgePipelineSpec, diagnostics: list[Diagnostic]) -> None:
    if not spec.steps:
        diagnostics.append(
            Diagnostic(
                code="PMSF304",
                severity=Severity.ERROR,
                message="SparkForge pipeline IR has no steps.",
                path=("steps",),
                phase="sparkforge_adapter",
            )
        )
    names = [s.name for s in spec.steps]
    if len(names) != len(set(names)):
        diagnostics.append(
            Diagnostic(
                code="PMSF305",
                severity=Severity.ERROR,
                message="Duplicate SparkForge step names are not allowed.",
                path=("steps",),
                phase="sparkforge_adapter",
            )
        )
    edges: dict[str, str | None] = {
        s.name: ((s.source or "").split(".", 1)[0] or None) for s in spec.steps
    }
    for name in names:
        seen: set[str] = set()
        cur: str | None = name
        while cur is not None:
            if cur in seen:
                diagnostics.append(
                    Diagnostic(
                        code="PMSF306",
                        severity=Severity.ERROR,
                        message=f"Cycle detected involving step {name!r}.",
                        path=("steps", name),
                        phase="sparkforge_adapter",
                    )
                )
                break
            seen.add(cur)
            cur = edges.get(cur)
