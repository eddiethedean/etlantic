"""Lower MedallionDocument onto ETLantic Pipeline / PipelineDefinition."""

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
from etlantic.authoring.normalize import definition_from_pipeline
from etlantic.diagnostics import Diagnostic, Severity, ValidationReport
from etlantic.extensions import facade_provenance
from etlantic.plan.freeze import immutable_mapping
from etlantic.plan.model import PipelinePlan
from etlantic.policy import PolicyMode, ValidationPolicy, register_validation_policy
from etlantic.profile import Profile
from etlantic.quality.gate import make_quality_gate
from etlantic.reliability import WriteIntent, WriteMode
from medallantic.callables import (
    make_callable_transformation,
    resolve_transform_callable,
)
from medallantic.column_rules import (
    NATIVE_QUALITY_CAPABILITY,
    split_portable_and_native_rules,
)
from medallantic.compat import write_mode_from_sparkforge, write_mode_metadata
from medallantic.diagnostics import (
    MDL100_EMPTY,
    MDL101_DUPLICATE_NAME,
    MDL102_CYCLE,
    MDL103_UNKNOWN_SOURCE,
    MDL104_MISSING_SOURCE,
    MDL105_BAD_WRITE_MODE,
    MDL106_UNKNOWN_KIND,
    MDL107_UNKNOWN_LAYER,
    MDL110_RULES_INVALID,
    MDL111_TRANSFORM_PASSTHROUGH,
    MDL130_NATIVE_COLUMN_RULE,
    VALID_LAYERS,
    mdl_diagnostic,
)
from medallantic.lifecycle import (
    default_write_mode_for_layer,
    incremental_strategy_for_step,
    lifecycle_policy_for_layer,
)
from medallantic.rules import RuleDSLError, parse_rules_shorthand
from medallantic.schema import MedallionDocument, MedallionStep


def _medallantic_version() -> str:
    from importlib.metadata import version

    try:
        return version("medallantic")
    except Exception:
        from medallantic import __version__

        return str(__version__)


def _primary_error_code(
    diagnostics: list[Diagnostic] | tuple[Diagnostic, ...],
    fallback: str,
) -> str:
    for diagnostic in diagnostics:
        if diagnostic.severity is Severity.ERROR:
            return diagnostic.code
    return fallback


def _policy_name(doc: MedallionDocument) -> str:
    return f"medallantic-{_safe_ident(doc.name)}-{_safe_ident(doc.schema)}"


def _step_annotations(doc: MedallionDocument) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for step in doc.steps:
        blob: dict[str, Any] = {}
        if step.description is not None:
            blob["description"] = step.description
        if step.tags:
            blob["tags"] = list(step.tags)
        if step.metadata:
            blob["metadata"] = dict(step.metadata)
        if blob:
            out[step.name] = blob
    return out


class LoweringError(Exception):
    """Raised when medallion → ETLantic lowering fails closed."""

    def __init__(
        self,
        message: str,
        *,
        report: ValidationReport | None = None,
        code: str = MDL100_EMPTY,
    ) -> None:
        super().__init__(message)
        self.report = report or ValidationReport()
        self.code = code


class MedallionRow(Data):
    """Generic row contract for medallion planning/parity (passthrough)."""

    id: int
    payload: str = ""


# Backward-compatible alias used by the SparkForge migrate adapter.
AdaptedRow = MedallionRow


@dataclass(frozen=True, slots=True)
class LoweringResult:
    """Result of lowering a medallion document onto ETLantic surfaces."""

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
        """Public ``PipelineDefinition`` with facade provenance/extensions."""
        defn = definition_from_pipeline(self.pipeline_cls)
        extensions = {
            "plugin:medallantic": {
                "schema": self.metadata.get("schema"),
                "layers": dict(self.layer_by_node),
                "step_map": dict(self.step_map),
                "description": self.metadata.get("description"),
                "tags": list(self.metadata.get("tags") or ()),
                "source_name": self.metadata.get("source_name"),
                "steps": dict(self.metadata.get("steps") or {}),
                "document_metadata": dict(self.metadata.get("document_metadata") or {}),
            }
        }
        return replace(
            defn,
            provenance=immutable_mapping(
                facade_provenance(
                    identity="medallantic",
                    version=str(_medallantic_version()),
                )
            ),
            extensions=immutable_mapping(extensions),
            metadata=immutable_mapping(dict(defn.metadata)),
        )

    def enrich_plan(self, plan: PipelinePlan) -> PipelinePlan:
        """Attach write intents and incremental strategies onto the plan."""
        write_map: dict[str, Any] = {}
        for intent in self.write_intents:
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
        strategy_map: dict[str, Any] = {}
        for node, layer in self.layer_by_node.items():
            meta = {}
            for intent in self.write_intents:
                if intent.metadata.get("step") == node or intent.subject_id == node:
                    meta = dict(intent.metadata)
                    break
            strategy = incremental_strategy_for_step(
                subject_id=str(meta.get("subject_id") or node),
                layer=layer,
                incremental_column=meta.get("incremental_column")
                if isinstance(meta.get("incremental_column"), str)
                else None,
                watermark_column=meta.get("watermark_column")
                if isinstance(meta.get("watermark_column"), str)
                else None,
            )
            # Also accept nested lifecycle policy incremental_field.
            if strategy is None:
                policy = meta.get("lifecycle_policy")
                if isinstance(policy, dict) and policy.get("incremental_field"):
                    strategy = incremental_strategy_for_step(
                        subject_id=str(policy.get("subject_id") or node),
                        layer=layer,
                        watermark_column=str(policy["incremental_field"]),
                    )
            if strategy is not None:
                strategy_map[strategy.subject_id] = strategy.to_dict()
        intents = dict(plan.intents)
        intents["write_intents"] = write_map
        if strategy_map:
            intents["incremental_strategies"] = strategy_map
        return replace(plan, intents=intents)

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


def build_profile(
    doc: MedallionDocument,
    *,
    name: str | None = None,
    bindings: dict[str, str] | None = None,
) -> Profile:
    """Build an ETLantic Profile from a medallion document."""
    engine = (doc.engine or "local").lower()
    spark_engine = "pyspark" if engine in {"spark", "pyspark", "delta"} else None
    sql_engine = "sql" if engine in {"sql", "postgres", "postgresql"} else None
    required_spark: tuple[str, ...] = ()
    if engine == "delta":
        required_spark = ("spark_delta",)
    resolved_bindings = dict(bindings or {})
    if not resolved_bindings:
        for step in doc.steps:
            if step.asset:
                resolved_bindings[step.name] = step.asset
                if step.kind in {"silver_transform", "gold_transform"}:
                    resolved_bindings[f"{step.name}_out"] = step.asset
    return Profile(
        name=name or _policy_name(doc),
        orchestrator="local",
        dataframe_engine=None if spark_engine or sql_engine else "local",
        spark_engine=spark_engine,
        sql_engine=sql_engine,
        validation_policy=_policy_name(doc),
        assets=resolved_bindings,
        resources={"schema": doc.schema},
        required_spark_capabilities=required_spark,
        metadata={
            "plugin:medallantic": {
                "adapter": "medallantic",
                "source_schema": doc.schema,
                "min_accept_rates": {
                    "ingest": doc.min_bronze_rate,
                    "clean": doc.min_silver_rate,
                    "publish": doc.min_gold_rate,
                },
                "layer_rates": {
                    "bronze": doc.min_bronze_rate,
                    "silver": doc.min_silver_rate,
                    "gold": doc.min_gold_rate,
                },
            }
        },
    )


def build_validation_policy(doc: MedallionDocument) -> ValidationPolicy:
    """Map layer thresholds onto a named ValidationPolicy (metadata only)."""
    return ValidationPolicy(
        name=_policy_name(doc),
        mode=PolicyMode.DEFAULT,
        metadata={
            "min_accept_rate_ingest": doc.min_bronze_rate,
            "min_accept_rate_clean": doc.min_silver_rate,
            "min_accept_rate_publish": doc.min_gold_rate,
        },
    )


def lower_document(
    doc: MedallionDocument,
    *,
    required_delta_operations: tuple[str, ...] = (),
    diagnostic_phase: str = "medallion_authoring",
) -> LoweringResult:
    """Map a medallion document to a concrete ETLantic Pipeline subclass.

    Bronze/silver/gold remain facade metadata on ``layer_by_node``; ETLantic
    core never sees medallion enums.
    """
    diagnostics: list[Diagnostic] = []
    _validate_document(doc, diagnostics, phase=diagnostic_phase)

    if any(d.severity is Severity.ERROR for d in diagnostics):
        raise LoweringError(
            "Refusing to lower invalid medallion document.",
            report=ValidationReport.from_diagnostics(diagnostics),
            code=_primary_error_code(diagnostics, MDL100_EMPTY),
        )

    ordered = _topo_order(doc.steps, diagnostics, phase=diagnostic_phase)
    if any(d.severity is Severity.ERROR for d in diagnostics):
        raise LoweringError(
            "Medallion lowering failed during graph ordering.",
            report=ValidationReport.from_diagnostics(diagnostics),
            code=_primary_error_code(diagnostics, MDL102_CYCLE),
        )

    ns: dict[str, Any] = {}
    annotations: dict[str, Any] = {}
    ns["__annotations__"] = annotations
    step_map: dict[str, str] = {}
    layer_by_node: dict[str, str] = {}
    write_intents: list[WriteIntent] = []
    members: dict[str, Any] = {}

    for step in ordered:
        if step.kind == "bronze_rules":
            binding = step.asset or step.name
            source = Extract[MedallionRow](asset=binding)
            if step.rules:
                portable_rules, native_rules = split_portable_and_native_rules(
                    step.rules
                )
                if native_rules:
                    _record_native_column_rules(
                        step=step,
                        native_rules=native_rules,
                        engine=doc.engine,
                        diagnostics=diagnostics,
                        phase=diagnostic_phase,
                    )
                if not portable_rules:
                    # Native-only bronze: extract only when no required native
                    # errors were recorded (callables may be deferred); otherwise
                    # keep building so MDL130 raises at the end.
                    ns[step.name] = source
                    annotations[step.name] = Extract[MedallionRow]
                    members[step.name] = source
                    step_map[step.name] = f"source:{step.name}"
                    layer_by_node[step.name] = step.layer
                    continue
                try:
                    ruleset = parse_rules_shorthand(portable_rules, name=step.name)
                except (RuleDSLError, ValueError) as exc:
                    diagnostics.append(
                        mdl_diagnostic(
                            MDL110_RULES_INVALID,
                            f"Invalid bronze rules on {step.name!r}: {exc}",
                            path=("steps", step.name, "rules"),
                            phase=diagnostic_phase,
                        )
                    )
                    continue
                ingest_name = f"{step.name}__ingest"
                ns[ingest_name] = source
                annotations[ingest_name] = Extract[MedallionRow]
                members[ingest_name] = source
                gate_cls = make_quality_gate(
                    MedallionRow,
                    ruleset,
                    name=f"{_safe_ident(step.name)}Gate",
                    expression_id=step.name,
                )
                gate = gate_cls.step(rows=source)
                ns[step.name] = gate
                annotations[step.name] = type(gate)
                members[step.name] = gate
                step_map[step.name] = f"gate:{step.name}"
                layer_by_node[step.name] = step.layer
                layer_by_node[ingest_name] = step.layer
                _attach_rejected_sink(
                    step_name=step.name,
                    gate=gate,
                    layer=step.layer,
                    ns=ns,
                    annotations=annotations,
                    members=members,
                    step_map=step_map,
                    layer_by_node=layer_by_node,
                    write_intents=write_intents,
                )
            else:
                ns[step.name] = source
                annotations[step.name] = Extract[MedallionRow]
                members[step.name] = source
                step_map[step.name] = f"source:{step.name}"
                layer_by_node[step.name] = step.layer
            continue

        if step.kind in {"silver_transform", "gold_transform"}:
            upstream = _resolve_upstream(
                step, members, diagnostics, phase=diagnostic_phase
            )
            if upstream is None:
                continue

            transform_cls: type[Transformation] | None = None
            quality_gate = False

            # Process rules before transform_ref failure continues so native
            # Column diagnostics (MDL130) are never skipped.
            portable_rules: dict[str, Any] = {}
            native_rules: list[Any] = []
            if step.rules:
                portable_rules, native_rules = split_portable_and_native_rules(
                    step.rules
                )
                if native_rules:
                    _record_native_column_rules(
                        step=step,
                        native_rules=native_rules,
                        engine=doc.engine,
                        diagnostics=diagnostics,
                        phase=diagnostic_phase,
                    )

            if step.transform_ref:
                ref = step.transform_ref.strip()
                looks_like_import = ("." in ref) or (":" in ref)
                try:
                    if looks_like_import:
                        resolve_transform_callable(ref)
                        transform_cls = make_callable_transformation(
                            step.name,
                            transform_ref=ref,
                            row_type=MedallionRow,
                        )
                    else:
                        # Symbolic SparkForge-style names stay passthrough until
                        # callers supply an importable module path.
                        diagnostics.append(
                            mdl_diagnostic(
                                MDL111_TRANSFORM_PASSTHROUGH,
                                (
                                    f"Transform {step.name!r} transform_ref "
                                    f"{ref!r} is a symbolic name (not "
                                    "module:attr); using passthrough until an "
                                    "importable callable is provided."
                                ),
                                severity=Severity.WARNING,
                                path=("steps", step.name, "transform_ref"),
                                phase=diagnostic_phase,
                            )
                        )
                        transform_cls = _make_passthrough_transformation(
                            step.name, transform_ref=ref
                        )
                except Exception as exc:
                    severity = Severity.ERROR if looks_like_import else Severity.WARNING
                    diagnostics.append(
                        mdl_diagnostic(
                            MDL111_TRANSFORM_PASSTHROUGH,
                            (
                                f"Transform {step.name!r} transform_ref "
                                f"{ref!r} could not be resolved: {exc}"
                            ),
                            severity=severity,
                            path=("steps", step.name, "transform_ref"),
                            phase=diagnostic_phase,
                        )
                    )
                    if looks_like_import:
                        continue
                    transform_cls = _make_passthrough_transformation(
                        step.name, transform_ref=ref
                    )

            if portable_rules:
                try:
                    ruleset = parse_rules_shorthand(
                        portable_rules, name=step.name
                    )
                except (RuleDSLError, ValueError) as exc:
                    diagnostics.append(
                        mdl_diagnostic(
                            MDL110_RULES_INVALID,
                            f"Invalid rules on {step.name!r}: {exc}",
                            path=("steps", step.name, "rules"),
                            phase=diagnostic_phase,
                        )
                    )
                    continue
                gate_cls = make_quality_gate(
                    MedallionRow,
                    ruleset,
                    name=f"{_safe_ident(step.name)}Gate",
                    expression_id=step.name,
                )
                if transform_cls is not None:
                    # Compose: callable transform, then quality gate.
                    if isinstance(upstream, Extract):
                        xform_inst = transform_cls.step(rows=upstream)
                    else:
                        xform_inst = transform_cls.step(rows=upstream.result)
                    ns[f"{step.name}__xform"] = xform_inst
                    annotations[f"{step.name}__xform"] = type(xform_inst)
                    members[f"{step.name}__xform"] = xform_inst
                    step_map[f"{step.name}__xform"] = f"step:{step.name}__xform"
                    layer_by_node[f"{step.name}__xform"] = step.layer
                    step_inst = gate_cls.step(rows=xform_inst.result)
                else:
                    if isinstance(upstream, Extract):
                        step_inst = gate_cls.step(rows=upstream)
                    else:
                        step_inst = gate_cls.step(rows=upstream.result)
                quality_gate = True
            elif transform_cls is not None:
                if isinstance(upstream, Extract):
                    step_inst = transform_cls.step(rows=upstream)
                else:
                    step_inst = transform_cls.step(rows=upstream.result)
            else:
                transform_cls = _make_passthrough_transformation(
                    step.name, transform_ref=None
                )
                if isinstance(upstream, Extract):
                    step_inst = transform_cls.step(rows=upstream)
                else:
                    step_inst = transform_cls.step(rows=upstream.result)

            ns[step.name] = step_inst
            annotations[step.name] = type(step_inst)
            members[step.name] = step_inst
            step_map[step.name] = f"step:{step.name}"
            layer_by_node[step.name] = step.layer
            if quality_gate:
                _attach_rejected_sink(
                    step_name=step.name,
                    gate=step_inst,
                    layer=step.layer,
                    ns=ns,
                    annotations=annotations,
                    members=members,
                    step_map=step_map,
                    layer_by_node=layer_by_node,
                    write_intents=write_intents,
                )

            try:
                if step.write_mode:
                    mode = write_mode_from_sparkforge(step.write_mode)
                else:
                    mode = default_write_mode_for_layer(step.layer)
            except ValueError as exc:
                diagnostics.append(
                    mdl_diagnostic(
                        MDL105_BAD_WRITE_MODE,
                        str(exc),
                        path=("steps", step.name, "write_mode"),
                        phase=diagnostic_phase,
                    )
                )
                continue

            mode_meta = write_mode_metadata(step.write_mode)
            policy = lifecycle_policy_for_layer(
                subject_id=step.asset or step.name,
                layer=step.layer,
                incremental_field=str(
                    step.metadata.get("incremental_column")
                    or step.metadata.get("watermark_column")
                    or ""
                )
                or None,
            )
            mode_meta["lifecycle_action"] = policy.default_action.value
            mode_meta["lifecycle_policy"] = policy.to_dict()
            if step.metadata.get("incremental_column"):
                mode_meta["incremental_column"] = step.metadata["incremental_column"]
            if step.metadata.get("watermark_column"):
                mode_meta["watermark_column"] = step.metadata["watermark_column"]
            merge_keys = step.metadata.get("merge_keys") or step.metadata.get("keys")
            keys: tuple[str, ...] = ()
            if isinstance(merge_keys, (list, tuple)):
                keys = tuple(str(k) for k in merge_keys)
            elif isinstance(merge_keys, str) and merge_keys:
                keys = (merge_keys,)

            if mode is WriteMode.NO_WRITE:
                write_intents.append(
                    WriteIntent(
                        subject_id=step.asset or step.name,
                        mode=mode,
                        keys=keys,
                        metadata={
                            "step": step.name,
                            "layer": step.layer,
                            **mode_meta,
                        },
                    )
                )
                continue

            sink_name = f"{step.name}_out"
            binding = step.asset or sink_name
            write_intents.append(
                WriteIntent(
                    subject_id=binding,
                    mode=mode,
                    keys=keys,
                    metadata={
                        "step": step.name,
                        "layer": step.layer,
                        **mode_meta,
                    },
                )
            )
            sink = Load[MedallionRow](input=step_inst.result, asset=binding)
            ns[sink_name] = sink
            annotations[sink_name] = Load[MedallionRow]
            members[sink_name] = sink
            step_map[sink_name] = f"sink:{sink_name}"
            layer_by_node[sink_name] = step.layer
            continue

        diagnostics.append(
            mdl_diagnostic(
                MDL106_UNKNOWN_KIND,
                f"Unknown medallion step kind for {step.name!r}: {step.kind!r}.",
                path=("steps", step.name),
                phase=diagnostic_phase,
            )
        )

    if any(d.severity is Severity.ERROR for d in diagnostics):
        raise LoweringError(
            "Medallion lowering failed.",
            report=ValidationReport.from_diagnostics(diagnostics),
            code=_primary_error_code(diagnostics, MDL106_UNKNOWN_KIND),
        )

    class_name = _safe_ident(doc.name) + "Pipeline"
    pipeline_cls = type(class_name, (Pipeline,), ns)
    policy = build_validation_policy(doc)
    register_validation_policy(policy)
    profile = build_profile(doc)

    return LoweringResult(
        pipeline_cls=pipeline_cls,
        profile=profile,
        validation_policy=policy,
        write_intents=tuple(write_intents),
        step_map=step_map,
        layer_by_node=layer_by_node,
        diagnostics=tuple(diagnostics),
        metadata={
            "adapter_version": _medallantic_version(),
            "source_name": doc.name,
            "schema": doc.schema,
            "description": doc.description,
            "tags": list(doc.tags),
            "document_metadata": dict(doc.metadata),
            "steps": _step_annotations(doc),
        },
        required_delta_operations=required_delta_operations,
    )


def _attach_rejected_sink(
    *,
    step_name: str,
    gate: Any,
    layer: str,
    ns: dict[str, Any],
    annotations: dict[str, Any],
    members: dict[str, Any],
    step_map: dict[str, str],
    layer_by_node: dict[str, str],
    write_intents: list[WriteIntent],
) -> None:
    """Retain quality-gate rejected rows as a no-write Load artifact."""
    reject_name = f"{step_name}__rejected"
    binding = reject_name
    sink = Load[MedallionRow](input=gate.rejected, asset=binding)
    ns[reject_name] = sink
    annotations[reject_name] = Load[MedallionRow]
    members[reject_name] = sink
    step_map[reject_name] = f"sink:{reject_name}"
    layer_by_node[reject_name] = layer
    write_intents.append(
        WriteIntent(
            subject_id=binding,
            mode=WriteMode.NO_WRITE,
            keys=(),
            metadata={
                "step": step_name,
                "layer": layer,
                "role": "rejected",
                "quality_gate": True,
            },
        )
    )


def _resolve_upstream(
    step: MedallionStep,
    members: dict[str, Any],
    diagnostics: list[Diagnostic],
    *,
    phase: str,
) -> Any | None:
    if not step.source:
        diagnostics.append(
            mdl_diagnostic(
                MDL104_MISSING_SOURCE,
                f"Transform step {step.name!r} has no upstream source.",
                path=("steps", step.name, "source"),
                phase=phase,
            )
        )
        return None
    # Support typed prior-result references: "step" or "step.result".
    source_name = step.source.split(".", 1)[0]
    upstream = members.get(source_name)
    if upstream is None:
        diagnostics.append(
            mdl_diagnostic(
                MDL103_UNKNOWN_SOURCE,
                (
                    f"Transform step {step.name!r} references unknown source "
                    f"{step.source!r}."
                ),
                path=("steps", step.name, "source"),
                phase=phase,
            )
        )
        return None
    return upstream


def _topo_order(
    steps: tuple[MedallionStep, ...],
    diagnostics: list[Diagnostic],
    *,
    phase: str,
) -> list[MedallionStep]:
    by_name = {s.name: s for s in steps}
    indegree: dict[str, int] = {s.name: 0 for s in steps}
    children: dict[str, list[str]] = defaultdict(list)
    for step in steps:
        source_name = (step.source or "").split(".", 1)[0] or None
        if source_name and source_name in by_name:
            children[source_name].append(step.name)
            indegree[step.name] += 1

    queue = deque([name for name, deg in indegree.items() if deg == 0])
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
            mdl_diagnostic(
                MDL102_CYCLE,
                "Cycle detected in medallion step source graph.",
                path=("steps",),
                phase=phase,
            )
        )
        return list(steps)
    return [by_name[name] for name in ordered_names]


def _validate_document(
    doc: MedallionDocument,
    diagnostics: list[Diagnostic],
    *,
    phase: str,
) -> None:
    if not doc.steps:
        diagnostics.append(
            mdl_diagnostic(
                MDL100_EMPTY,
                "Medallion document has no steps.",
                path=("steps",),
                phase=phase,
            )
        )
    names = [s.name for s in doc.steps]
    if len(names) != len(set(names)):
        diagnostics.append(
            mdl_diagnostic(
                MDL101_DUPLICATE_NAME,
                "Duplicate medallion step names are not allowed.",
                path=("steps",),
                phase=phase,
            )
        )
    for step in doc.steps:
        if step.layer not in VALID_LAYERS:
            diagnostics.append(
                mdl_diagnostic(
                    MDL107_UNKNOWN_LAYER,
                    (
                        f"Unknown medallion layer for step {step.name!r}: "
                        f"{step.layer!r}."
                    ),
                    path=("steps", step.name, "layer"),
                    phase=phase,
                )
            )
    edges: dict[str, str | None] = {
        s.name: ((s.source or "").split(".", 1)[0] or None) for s in doc.steps
    }
    for name in names:
        seen: set[str] = set()
        cur: str | None = name
        while cur is not None:
            if cur in seen:
                diagnostics.append(
                    mdl_diagnostic(
                        MDL102_CYCLE,
                        f"Cycle detected involving step {name!r}.",
                        path=("steps", name),
                        phase=phase,
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
            "rows": Input[MedallionRow],
            "result": Output[MedallionRow],
        },
        "__doc__": (f"Medallion transform {name} ({transform_ref or 'passthrough'})."),
    }
    transform_cls = type(safe, (Transformation,), ns)

    @transform_cls.implementation("local")
    def _passthrough(rows: list[Any]) -> list[Any]:
        return list(rows)

    @transform_cls.implementation("pyspark")
    def _passthrough_spark(rows: Any) -> Any:
        return rows

    return transform_cls


def _record_native_column_rules(
    *,
    step: MedallionStep,
    native_rules: list[Any],
    engine: str,
    diagnostics: list[Diagnostic],
    phase: str,
) -> None:
    """Attach native Column rule metadata and fail closed when not executable.

    Opaque Column objects and unresolved refs always emit ``MDL130``.
    Required native rules never succeed as metadata-only no-ops — including on
    spark/pyspark/delta — until a concrete evaluator exists for the rule form.
    """
    payload = [rule.to_dict() for rule in native_rules]
    step.metadata.setdefault("native_column_rules", payload)
    step.metadata.setdefault("required_quality_capabilities", [NATIVE_QUALITY_CAPABILITY])
    required = [r for r in native_rules if getattr(r, "required", True)]
    if not required:
        return
    engine_key = (engine or "local").lower()
    # Fail closed for all engines: native Column rules are not yet executed by
    # a portable gate. Callable refs are recorded for a future executor; until
    # then required rules refuse to lower.
    diagnostics.append(
        mdl_diagnostic(
            MDL130_NATIVE_COLUMN_RULE,
            (
                f"Step {step.name!r} declares PySpark Column / native "
                f"rules requiring {NATIVE_QUALITY_CAPABILITY!r}; required "
                f"native rules are not executable yet on engine {engine_key!r} "
                "(failing closed). Use portable etlantic.quality rules, or "
                "remove native Column rules."
            ),
            path=("steps", step.name, "rules"),
            phase=phase,
        )
    )


def _safe_ident(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in name)
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"S_{cleaned}"
    return cleaned
