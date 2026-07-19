"""Map SparkForge IR onto ETLantic Pipeline / Profile (no medallion in core)."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field, replace
from typing import Any

from etlantic import (
    Data,
    Extract,
    Input,
    Load,
    Output,
    Pipeline,
    Transformation,
)
from etlantic.capabilities import PluginCapabilities
from etlantic.diagnostics import Diagnostic, Severity, ValidationReport
from etlantic.plan.model import PipelinePlan
from etlantic.policy import PolicyMode, ValidationPolicy, register_validation_policy
from etlantic.profile import Profile
from etlantic.reliability import WriteIntent, WriteMode
from etlantic_sparkforge.compat import (
    assert_delta_capabilities,
    write_mode_from_sparkforge,
    write_mode_metadata,
)
from etlantic_sparkforge.ir import (
    SparkForgePipelineSpec,
    SparkForgeStepSpec,
    StepKind,
)


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


class AdaptedRow(Data):
    """Generic row contract for adapted SparkForge fixtures (planning/parity)."""

    id: int
    payload: str = ""


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

    def enrich_plan(self, plan: PipelinePlan) -> PipelinePlan:
        """Attach adapted write intents onto ``plan.intents['write_intents']``."""
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
    """Place serialized write intents under ``plan.intents['write_intents']``.

    Shape matches orchestration reliability lookups (subject / sink name →
    ``{intent, kind, ...}``). Local runtime still gates writes via
    ``RunRequest.no_write``; MERGE/APPEND are for plan and orchestration.
    """
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
    engine = (spec.engine or "spark").lower()
    spark_engine = "pyspark" if engine in {"spark", "pyspark", "delta"} else None
    sql_engine = "sql" if engine in {"sql", "postgres", "postgresql"} else None
    required_spark: tuple[str, ...] = ()
    if engine == "delta":
        required_spark = ("spark_delta",)
    resolved_bindings = dict(bindings or {})
    if not resolved_bindings:
        for step in spec.steps:
            if step.table_name:
                resolved_bindings[step.name] = step.table_name
                if step.kind in {StepKind.SILVER_TRANSFORM, StepKind.GOLD_TRANSFORM}:
                    resolved_bindings[f"{step.name}_out"] = step.table_name
    return Profile(
        name=name or f"sparkforge-{spec.schema}",
        orchestrator="local",
        dataframe_engine=None if spark_engine or sql_engine else "local",
        spark_engine=spark_engine,
        sql_engine=sql_engine,
        validation_policy=f"sparkforge-{spec.schema}",
        assets=resolved_bindings,
        resources={"schema": spec.schema},
        required_spark_capabilities=required_spark,
        metadata={
            "adapter": "etlantic-sparkforge",
            "source_schema": spec.schema,
            "min_accept_rates": {
                "ingest": spec.min_bronze_rate,
                "clean": spec.min_silver_rate,
                "publish": spec.min_gold_rate,
            },
            "sparkforge_layer_rates": {
                "bronze": spec.min_bronze_rate,
                "silver": spec.min_silver_rate,
                "gold": spec.min_gold_rate,
            },
        },
    )


def adapt_validation_policy(spec: SparkForgePipelineSpec) -> ValidationPolicy:
    """Map layer thresholds onto a named ValidationPolicy (metadata only)."""
    return ValidationPolicy(
        name=f"sparkforge-{spec.schema}",
        mode=PolicyMode.DEFAULT,
        metadata={
            "min_accept_rate_ingest": spec.min_bronze_rate,
            "min_accept_rate_clean": spec.min_silver_rate,
            "min_accept_rate_publish": spec.min_gold_rate,
        },
    )


def adapt_pipeline(
    spec: SparkForgePipelineSpec,
    *,
    capabilities: PluginCapabilities | None = None,
    strict_delta: bool = True,
) -> AdaptationResult:
    """Map a SparkForge pipeline IR to a concrete ETLantic Pipeline subclass.

    Bronze/silver/gold remain adapter metadata on AdaptationResult.layer_by_node;
    ETLantic core never sees medallion enums.

    Graph edges follow each transform's ``source`` field (topologically ordered),
    not declaration order alone.
    """
    diagnostics: list[Diagnostic] = []
    _validate_spec(spec, diagnostics)

    if any(d.severity is Severity.ERROR for d in diagnostics):
        raise AdapterError(
            "Refusing to adapt invalid SparkForge pipeline IR.",
            report=ValidationReport.from_diagnostics(diagnostics),
            code="PMSF301",
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

    ordered = _topo_order(spec.steps, diagnostics)
    if any(d.severity is Severity.ERROR for d in diagnostics):
        raise AdapterError(
            "SparkForge adaptation failed during graph ordering.",
            report=ValidationReport.from_diagnostics(diagnostics),
            code="PMSF301",
        )

    # Plain dict preserves insertion order (same pattern as DPCS codegen).
    ns: dict[str, Any] = {}
    annotations: dict[str, Any] = {}
    ns["__annotations__"] = annotations
    step_map: dict[str, str] = {}
    layer_by_node: dict[str, str] = {}
    write_intents: list[WriteIntent] = []
    members: dict[str, Any] = {}

    for step in ordered:
        if step.kind is StepKind.BRONZE_RULES:
            binding = step.table_name or step.name
            source = Extract[AdaptedRow](asset=binding, _compat_warn=False)
            ns[step.name] = source
            annotations[step.name] = Extract[AdaptedRow]
            members[step.name] = source
            step_map[step.name] = f"source:{step.name}"
            layer_by_node[step.name] = step.layer.value
            if step.rules:
                diagnostics.append(
                    Diagnostic(
                        code="PMSF411",
                        severity=Severity.WARNING,
                        message=(
                            f"Bronze rules on {step.name!r} are not enforced by the "
                            "IR adapter (passthrough planning only)."
                        ),
                        path=("steps", step.name, "rules"),
                        phase="sparkforge_adapter",
                    )
                )
            continue

        if step.kind in {StepKind.SILVER_TRANSFORM, StepKind.GOLD_TRANSFORM}:
            upstream = _resolve_upstream(step, members, diagnostics)
            if upstream is None:
                continue

            if step.transform_ref or step.rules:
                diagnostics.append(
                    Diagnostic(
                        code="PMSF411",
                        severity=Severity.WARNING,
                        message=(
                            f"Transform {step.name!r} maps to a passthrough "
                            "implementation; transform_ref/rules are not executed."
                        ),
                        path=("steps", step.name),
                        phase="sparkforge_adapter",
                    )
                )

            transform_cls = _make_passthrough_transformation(
                step.name, transform_ref=step.transform_ref
            )
            if isinstance(upstream, Extract):
                step_inst = transform_cls.step(rows=upstream)
            else:
                step_inst = transform_cls.step(rows=upstream.result)
            ns[step.name] = step_inst
            annotations[step.name] = type(step_inst)
            members[step.name] = step_inst
            step_map[step.name] = f"step:{step.name}"
            layer_by_node[step.name] = step.layer.value

            try:
                mode = write_mode_from_sparkforge(step.write_mode)
            except ValueError as exc:
                diagnostics.append(
                    Diagnostic(
                        code="PMSF307",
                        severity=Severity.ERROR,
                        message=str(exc),
                        path=("steps", step.name, "write_mode"),
                        phase="sparkforge_adapter",
                    )
                )
                continue

            mode_meta = write_mode_metadata(step.write_mode)
            merge_keys = step.metadata.get("merge_keys") or step.metadata.get("keys")
            keys: tuple[str, ...] = ()
            if isinstance(merge_keys, (list, tuple)):
                keys = tuple(str(k) for k in merge_keys)
            elif isinstance(merge_keys, str) and merge_keys:
                keys = (merge_keys,)

            if mode is WriteMode.NO_WRITE:
                write_intents.append(
                    WriteIntent(
                        subject_id=step.table_name or step.name,
                        mode=mode,
                        keys=keys,
                        metadata={
                            "step": step.name,
                            "layer": step.layer.value,
                            **mode_meta,
                        },
                    )
                )
                continue

            sink_name = f"{step.name}_out"
            binding = step.table_name or sink_name
            write_intents.append(
                WriteIntent(
                    subject_id=binding,
                    mode=mode,
                    keys=keys,
                    metadata={
                        "step": step.name,
                        "layer": step.layer.value,
                        **mode_meta,
                    },
                )
            )
            sink = Load[AdaptedRow](
                input=step_inst.result, asset=binding, _compat_warn=False
            )
            ns[sink_name] = sink
            annotations[sink_name] = Load[AdaptedRow]
            members[sink_name] = sink
            step_map[sink_name] = f"sink:{sink_name}"
            layer_by_node[sink_name] = step.layer.value
            continue

        diagnostics.append(
            Diagnostic(
                code="PMSF303",
                severity=Severity.ERROR,
                message=f"Unknown SparkForge step kind for {step.name!r}.",
                path=("steps", step.name),
                phase="sparkforge_adapter",
            )
        )

    if any(d.severity is Severity.ERROR for d in diagnostics):
        raise AdapterError(
            "SparkForge adaptation failed.",
            report=ValidationReport.from_diagnostics(diagnostics),
            code="PMSF301",
        )

    class_name = _safe_ident(spec.name) + "Pipeline"
    pipeline_cls = type(class_name, (Pipeline,), ns)
    policy = adapt_validation_policy(spec)
    register_validation_policy(policy)
    profile = adapt_profile(spec)
    if delta_ops and not strict_delta:
        profile = profile.with_updates(
            required_spark_capabilities=tuple(
                dict.fromkeys((*profile.required_spark_capabilities, "spark_delta"))
            ),
            metadata={
                **profile.metadata,
                "required_delta_operations": list(delta_ops),
            },
        )

    return AdaptationResult(
        pipeline_cls=pipeline_cls,
        profile=profile,
        validation_policy=policy,
        write_intents=tuple(write_intents),
        step_map=step_map,
        layer_by_node=layer_by_node,
        diagnostics=tuple(diagnostics),
        metadata={
            "adapter_version": "0.14.0",
            "source_name": spec.name,
            "schema": spec.schema,
        },
        required_delta_operations=delta_ops,
    )


def _resolve_upstream(
    step: SparkForgeStepSpec,
    members: dict[str, Any],
    diagnostics: list[Diagnostic],
) -> Any | None:
    if not step.source:
        diagnostics.append(
            Diagnostic(
                code="PMSF302",
                severity=Severity.ERROR,
                message=(f"Transform step {step.name!r} has no upstream source."),
                path=("steps", step.name, "source"),
                phase="sparkforge_adapter",
            )
        )
        return None
    upstream = members.get(step.source)
    if upstream is None:
        diagnostics.append(
            Diagnostic(
                code="PMSF312",
                severity=Severity.ERROR,
                message=(
                    f"Transform step {step.name!r} references unknown source "
                    f"{step.source!r}."
                ),
                path=("steps", step.name, "source"),
                phase="sparkforge_adapter",
            )
        )
        return None
    return upstream


def _topo_order(
    steps: tuple[SparkForgeStepSpec, ...],
    diagnostics: list[Diagnostic],
) -> list[SparkForgeStepSpec]:
    by_name = {s.name: s for s in steps}
    indegree: dict[str, int] = {s.name: 0 for s in steps}
    children: dict[str, list[str]] = defaultdict(list)
    for step in steps:
        if step.source and step.source in by_name:
            children[step.source].append(step.name)
            indegree[step.name] += 1
        elif step.source and step.source not in by_name:
            # Defer unknown-source error until instantiation so bronze-only graphs
            # that reference external tables can still declare source names later.
            pass

    queue = deque([name for name, deg in indegree.items() if deg == 0])
    # Preserve declaration order among ready nodes.
    declaration = {s.name: i for i, s in enumerate(steps)}
    ordered_names: list[str] = []
    while queue:
        ready = sorted(queue, key=lambda n: declaration[n])
        queue.clear()
        for name in ready:
            ordered_names.append(name)
            for child in children[name]:
                indegree[child] -= 1
                if indegree[child] == 0:
                    queue.append(child)

    if len(ordered_names) != len(steps):
        diagnostics.append(
            Diagnostic(
                code="PMSF306",
                severity=Severity.ERROR,
                message="Cycle detected in SparkForge step source graph.",
                path=("steps",),
                phase="sparkforge_adapter",
            )
        )
        return list(steps)
    return [by_name[name] for name in ordered_names]


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
    edges: dict[str, str | None] = {s.name: s.source for s in spec.steps}
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


def _make_passthrough_transformation(
    name: str,
    *,
    transform_ref: str | None,
) -> type[Transformation]:
    safe = _safe_ident(name)
    ns: dict[str, Any] = {
        "__annotations__": {
            "rows": Input[AdaptedRow],
            "result": Output[AdaptedRow],
        },
        "__doc__": (
            f"Adapted SparkForge transform {name} ({transform_ref or 'passthrough'})."
        ),
    }
    transform_cls = type(safe, (Transformation,), ns)

    @transform_cls.implementation("local")
    def _passthrough(rows: list[Any]) -> list[Any]:
        return list(rows)

    @transform_cls.implementation("pyspark")
    def _passthrough_spark(rows: Any) -> Any:
        return rows

    return transform_cls


def _safe_ident(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in name)
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"S_{cleaned}"
    return cleaned
