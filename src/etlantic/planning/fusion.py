# pyright: reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownMemberType=false
"""Static recognition and lowering of one bounded native scan composition."""

from __future__ import annotations

import inspect
import types
from collections.abc import Mapping
from dataclasses import replace
from typing import Any, Union, get_args, get_origin

from etlantic.contracts import Data
from etlantic.model import LogicalGraph
from etlantic.plan.physical import (
    PhysicalDAG,
    PhysicalDependency,
    PhysicalUnitKind,
    generated_unit_identity,
)
from etlantic.planning.adaptive_budget import current_budget
from etlantic.planning.adaptive_budget import record as owned_record
from etlantic.transform.fusion import FusionDescriptor, FusionMember, fusion_digest


def schema_contract(model: type[Any] | None, contract_id: str | None) -> dict[str, Any]:
    """Prove contracts which can be checked without inspecting individual rows."""
    if model is None or not contract_id or not hasattr(model, "model_fields"):
        raise ValueError("Fusion requires a schema-provable contract")
    if model.model_config.get("extra") == "forbid":
        raise ValueError("Fusion cannot bypass extra-field rejection")
    if any(
        inspect.getattr_static(model, method)
        is not inspect.getattr_static(Data, method)
        for method in (
            "__init__",
            "model_validate",
            "model_post_init",
            "__get_pydantic_core_schema__",
        )
    ):
        raise ValueError("Fusion cannot bypass custom contract hooks")
    core = model.__pydantic_core_schema__
    if (
        core.get("type") != "model"
        or core.get("custom_init")
        or core.get("post_init")
        or model.__pydantic_custom_init__
        or model.__pydantic_post_init__ is not None
        or core.get("schema", {}).get("type") != "model-fields"
    ):
        raise ValueError("Fusion cannot bypass custom contract construction")
    decorators = model.__pydantic_decorators__
    if any(
        getattr(decorators, name)
        for name in (
            "validators",
            "field_validators",
            "root_validators",
            "model_validators",
            "computed_fields",
            "field_serializers",
            "model_serializers",
        )
    ):
        raise ValueError("Fusion cannot bypass custom contract behavior")
    fields = {}
    for name, field in model.model_fields.items():
        annotation = field.annotation
        if (
            get_origin(annotation) not in (types.UnionType, Union)
            or set(get_args(annotation)) not in ({int, type(None)}, {bool, type(None)})
            or not field.is_required()
            or field.alias is not None
            or field.validation_alias is not None
            or field.serialization_alias is not None
            or field.metadata
            or field.default_factory is not None
        ):
            raise ValueError("Fusion requires required nullable primitive columns")
        compiled_field = core["schema"]["fields"].get(name, {})
        expected_type = "int" if int in get_args(annotation) else "bool"
        if compiled_field.get("type") != "model-field" or compiled_field.get(
            "schema"
        ) != {"type": "nullable", "schema": {"type": expected_type}}:
            raise ValueError("Fusion cannot bypass custom field core schemas")
        fields[name] = "int64" if int in get_args(annotation) else "boolean"
    if not 0 < len(fields) <= 8:
        raise ValueError("Fusion contract exceeds column bounds")
    # The digest convention matches whole-plan contract admission.
    return {
        "id": contract_id,
        "fingerprint": fusion_digest(model.model_json_schema()).removeprefix("sha256:"),
        "fields": fields,
    }


def recognize_fusion(
    graph: LogicalGraph,
    decisions: Any,
    targets: Any,
    context: Any,
    request: Any,
    transforms: Mapping[str, Any],
) -> FusionDescriptor | None:
    """Read descriptors only. Unsupported syntax must not create positive proof."""
    if request is None or len(graph.nodes) != 5 or len(graph.edges) != 4:
        return None
    # The frozen candidate binds placement for the entire exact topology.
    # This makes composition facts assignment-independent for the existing
    # additive solver objective; no optimistic credit for a hypothetical group.
    if set(context.profile.implementation_overrides) != {n.name for n in graph.nodes}:
        return None
    source, first, second, consumer, sink = graph.nodes
    if consumer.metadata.get("etlantic.validation_required") != {
        "schema": "etlantic.physical_operation/1",
        "kind": "validation",
        "port": "result",
        "outcome": "fail",
    }:
        return None
    if tuple(n.kind.value for n in graph.nodes) != (
        "source",
        "step",
        "step",
        "step",
        "sink",
    ):
        return None
    if any(
        len(graph.edges_to(n.name)) != 1 or len(graph.edges_from(n.name)) != 1
        for n in (first, second, consumer)
    ):
        return None
    target_map = {name: target for name, target, _ in targets}
    placements = {d.node_name: d.target_id for d in decisions}
    assigned = [target_map[placements[n.name]] for n in graph.nodes]
    if (
        len({placements[n.name] for n in (source, first, second)}) != 1
        or len({placements[n.name] for n in (consumer, sink)}) != 1
        or [target.engine for target in assigned] != ["polars"] * 3 + ["pandas"] * 2
        or any(
            target.location != "local" or target.resource is not None
            for target in assigned
        )
    ):
        return None
    binding = context.registry.bindings.get(source.binding or source.name)
    if binding is None or binding.provider != "polars-parquet":
        return None
    if (
        request.retry.max_attempts != 1
        or context.profile.retry_max_attempts not in (None, 1)
        or request.materialization.value != "default"
        or context.profile.security_mode not in {"development", "test"}
        or any(node.metadata for node in (source, first, second))
    ):
        return None
    try:
        compiler = context.registry.transform_compilers.get("polars")
        if compiler is None or not callable(getattr(compiler, "analyze_fusion", None)):
            return None
        members = []
        for node in (first, second):
            transform = transforms.get(node.transformation_id or "")
            portable = (
                transform.portable_definition() if transform is not None else None
            )
            if portable is None or len(node.inputs) != 1 or len(node.outputs) != 1:
                return None
            edge = graph.edges_to(node.name)[0]
            members.append(
                FusionMember(
                    logical_node=node.name,
                    upstream_node=edge.producer_node,
                    upstream_port=edge.producer_port,
                    input_port=node.inputs[0].name,
                    output_port=node.outputs[0].name,
                    input_contract=schema_contract(
                        node.inputs[0].contract_type, node.inputs[0].contract_id
                    ),
                    output_contract=schema_contract(
                        node.outputs[0].contract_type, node.outputs[0].contract_id
                    ),
                    definition=portable.plan,
                    ir_fingerprint=portable.fingerprint,
                )
            )
        # Consumer must be the independently compiled portable select signature.
        portable_consumer = transforms[
            consumer.transformation_id or ""
        ].portable_definition()
        action = portable_consumer.plan["actions"]
        if (
            len(action) != 1
            or action[0]["kind"]["action"] != "dtcs:project"
            or set(action[0]["kind"]["parameters"]) != {"fields"}
            or any(
                type(field) is not str
                for field in action[0]["kind"]["parameters"]["fields"]
            )
        ):
            return None
        from etlantic.planning.adaptive import _target_identity

        descriptor = FusionDescriptor(
            source_node=source.name,
            source_port=source.outputs[0].name,
            source_binding=binding.to_dict(),
            source_contract=schema_contract(source.contract_type, source.contract_id),
            target_identity=_target_identity(assigned[0]),
            compiler_name=compiler.info.name,
            compiler_version=compiler.info.version,
            compiler_evidence=compiler.info.evidence_fingerprint,
            policy_digest=fusion_digest(request.to_dict()),
            members=tuple(members),
            parameters={p.name: p.value for p in first.parameters if p.has_value},
        )
        from etlantic.transform.compiler import TransformPlanningContext

        report = compiler.analyze_fusion(
            descriptor,
            context=TransformPlanningContext(
                graph.pipeline_id,
                first.name,
                context.profile.name,
                "polars",
            ),
        )
        return descriptor if report.supported else None
    except (ValueError, TypeError, KeyError, AttributeError):
        return None


def lower_fusion(dag: PhysicalDAG, descriptor: FusionDescriptor) -> PhysicalDAG:
    """Replace exactly three singleton units without a physical self-dependency."""
    with current_budget().allocation(descriptor.to_dict(), "fusion-descriptor"):
        members = descriptor.logical_nodes
        originals = {dag.logical_to_physical[name] for name in members}
        units = {unit.identity: unit for unit in dag.units}
        source = units[dag.logical_to_physical[members[0]]]
        output = units[dag.logical_to_physical[members[-1]]]
        metadata = {
            **dict(source.metadata),
            "etlantic.fusion": descriptor.to_dict(),
            "etlantic.fusion_fingerprint": descriptor.fingerprint,
            "etlantic.internal_edges": [
                list(edge) for edge in descriptor.internal_edges
            ],
            "etlantic.logical_predecessors": [],
        }
        envelope: dict[str, Any] = {
            "kind": PhysicalUnitKind.COMPUTE,
            "target_identity": source.target_identity,
            "logical_nodes": members,
            "input_contracts": source.input_contracts,
            "output_contracts": output.output_contracts,
            "policy": source.policy,
            "retry_policy": source.retry_policy,
            "ownership": source.ownership,
            "protocol_versions": source.protocol_versions,
            "metadata": metadata,
        }
        identity = generated_unit_identity(**envelope)
        fused = owned_record(type(source), "boundary", identity=identity, **envelope)
        rewritten = [fused]
        for unit in dag.units:
            if unit.identity in originals:
                current_budget().release_object(unit)
                continue
            dependencies = tuple(
                PhysicalDependency(
                    identity if dep.unit_id in originals else dep.unit_id,
                    dep.kind,
                )
                for dep in unit.dependencies
            )
            rewritten.append(replace(unit, dependencies=dependencies))
        mapping = {
            name: identity if uid in originals else uid
            for name, uid in dag.logical_to_physical.items()
        }
        order = tuple(
            identity if uid == source.identity else uid
            for uid in dag.topological_order
            if uid not in originals or uid == source.identity
        )
        return PhysicalDAG(
            units=tuple(rewritten), logical_to_physical=mapping, topological_order=order
        )
