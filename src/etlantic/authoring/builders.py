"""Functional builders for PipelineDefinition (no metaclasses or generated classes)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from etlantic.authoring.definition import (
    PIPELINE_SCHEMA,
    ContractDefinition,
    EdgeDefinition,
    FieldSpec,
    ImplementationRef,
    NodeDefinition,
    PipelineDefinition,
    PortDefinitionSpec,
    TransformationDefinition,
)
from etlantic.authoring.serialize import pipeline_fingerprint
from etlantic.identity import node_id
from etlantic.plan.freeze import immutable_mapping


def field_spec(
    name: str,
    type: str,
    *,
    nullable: bool = False,
    required: bool = True,
) -> FieldSpec:
    """Construct a contract field."""
    return FieldSpec(name=name, type=type, nullable=nullable, required=required)


def contract_definition(
    identity: str,
    name: str,
    *,
    version: str | None = None,
    authoring_id: str | None = None,
    fields: Sequence[FieldSpec] = (),
    metadata: Mapping[str, Any] | None = None,
) -> ContractDefinition:
    """Construct an embedded data contract."""
    return ContractDefinition(
        identity=identity,
        name=name,
        version=version,
        authoring_id=authoring_id or identity,
        fields=tuple(fields),
        metadata=immutable_mapping(dict(metadata or {})),
    )


def port_spec(
    name: str,
    direction: str,
    *,
    contract_id: str | None = None,
    value_type: str | None = None,
    default: Any = ...,
    has_default: bool = False,
    value: Any = ...,
    has_value: bool = False,
    role: str = "valid",
    required: bool = True,
) -> PortDefinitionSpec:
    """Construct a port or parameter specification."""
    return PortDefinitionSpec(
        name=name,
        direction=direction,
        contract_id=contract_id,
        value_type=value_type,
        default=default,
        has_default=has_default,
        value=value,
        has_value=has_value,
        role=role,
        required=required,
    )


def input_port(name: str, contract_id: str, *, required: bool = True) -> PortDefinitionSpec:
    return port_spec(name, "input", contract_id=contract_id, required=required)


def output_port(
    name: str,
    contract_id: str,
    *,
    role: str = "valid",
) -> PortDefinitionSpec:
    return port_spec(name, "output", contract_id=contract_id, role=role)


def parameter_port(
    name: str,
    value_type: str,
    *,
    default: Any = ...,
    value: Any = ...,
) -> PortDefinitionSpec:
    has_default = default is not ...
    has_value = value is not ...
    return port_spec(
        name,
        "parameter",
        value_type=value_type,
        default=default,
        has_default=has_default,
        value=value,
        has_value=has_value,
        required=not has_default,
    )


def implementation_ref(
    engine: str,
    identity: str,
    *,
    kind: str = "native",
    is_async: bool = False,
) -> ImplementationRef:
    return ImplementationRef(
        engine=engine, identity=identity, kind=kind, is_async=is_async
    )


def transformation_definition(
    identity: str,
    name: str,
    *,
    version: str | None = None,
    ports: Sequence[PortDefinitionSpec] = (),
    implementation_refs: Sequence[ImplementationRef] = (),
    portable_plan: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> TransformationDefinition:
    return TransformationDefinition(
        identity=identity,
        name=name,
        version=version,
        ports=tuple(ports),
        implementation_refs=tuple(implementation_refs),
        portable_plan=immutable_mapping(dict(portable_plan)) if portable_plan else None,
        metadata=immutable_mapping(dict(metadata or {})),
    )


def extract_node(
    name: str,
    *,
    asset: str,
    contract_id: str,
    pipeline_id: str,
    metadata: Mapping[str, Any] | None = None,
) -> NodeDefinition:
    return NodeDefinition(
        name=name,
        kind="source",
        identity=node_id(pipeline_id, name),
        asset=asset,
        contract_id=contract_id,
        outputs=(output_port("result", contract_id),),
        metadata=immutable_mapping(dict(metadata or {})),
    )


def load_node(
    name: str,
    *,
    asset: str,
    contract_id: str,
    pipeline_id: str,
    metadata: Mapping[str, Any] | None = None,
) -> NodeDefinition:
    return NodeDefinition(
        name=name,
        kind="sink",
        identity=node_id(pipeline_id, name),
        asset=asset,
        contract_id=contract_id,
        inputs=(input_port("input", contract_id),),
        metadata=immutable_mapping(dict(metadata or {})),
    )


def step_node(
    name: str,
    *,
    transformation_id: str,
    transformation_name: str,
    pipeline_id: str,
    inputs: Sequence[PortDefinitionSpec] = (),
    outputs: Sequence[PortDefinitionSpec] = (),
    parameters: Sequence[PortDefinitionSpec] = (),
    metadata: Mapping[str, Any] | None = None,
) -> NodeDefinition:
    return NodeDefinition(
        name=name,
        kind="step",
        identity=node_id(pipeline_id, name),
        transformation_id=transformation_id,
        transformation_name=transformation_name,
        inputs=tuple(inputs),
        outputs=tuple(outputs),
        parameters=tuple(parameters),
        metadata=immutable_mapping(dict(metadata or {})),
    )


def edge(
    producer_node: str,
    producer_port: str,
    consumer_node: str,
    consumer_port: str,
    *,
    producer_contract_id: str | None = None,
    consumer_contract_id: str | None = None,
) -> EdgeDefinition:
    return EdgeDefinition(
        producer_node=producer_node,
        producer_port=producer_port,
        consumer_node=consumer_node,
        consumer_port=consumer_port,
        producer_contract_id=producer_contract_id,
        consumer_contract_id=consumer_contract_id,
    )


def pipeline_definition(
    pipeline_id: str,
    pipeline_name: str,
    *,
    version: str | None = None,
    contracts: Sequence[ContractDefinition] = (),
    transformations: Sequence[TransformationDefinition] = (),
    nodes: Sequence[NodeDefinition] = (),
    edges: Sequence[EdgeDefinition] = (),
    profile_ref: str | None = None,
    policy_refs: Mapping[str, Any] | None = None,
    reliability: Mapping[str, Any] | None = None,
    provenance: Mapping[str, Any] | None = None,
    extensions: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
    fingerprint: bool = True,
) -> PipelineDefinition:
    """Construct a complete PipelineDefinition."""
    defn = PipelineDefinition(
        schema=PIPELINE_SCHEMA,
        pipeline_id=pipeline_id,
        pipeline_name=pipeline_name,
        version=version,
        contracts=tuple(contracts),
        transformations=tuple(transformations),
        nodes=tuple(nodes),
        edges=tuple(edges),
        profile_ref=profile_ref,
        policy_refs=immutable_mapping(dict(policy_refs or {})),
        reliability=immutable_mapping(dict(reliability or {})),
        provenance=immutable_mapping(dict(provenance or {"kind": "functional"})),
        extensions=immutable_mapping(dict(extensions or {})),
        metadata=immutable_mapping(dict(metadata or {})),
    )
    if fingerprint:
        return defn.with_fingerprint(pipeline_fingerprint(defn))
    return defn


def replace_nodes(
    defn: PipelineDefinition, nodes: Sequence[NodeDefinition]
) -> PipelineDefinition:
    """Return a copy with replaced nodes and refreshed fingerprint."""
    updated = PipelineDefinition(
        schema=defn.schema,
        pipeline_id=defn.pipeline_id,
        pipeline_name=defn.pipeline_name,
        version=defn.version,
        contracts=defn.contracts,
        transformations=defn.transformations,
        nodes=tuple(nodes),
        edges=defn.edges,
        profile_ref=defn.profile_ref,
        policy_refs=defn.policy_refs,
        reliability=defn.reliability,
        provenance=defn.provenance,
        extensions=defn.extensions,
        metadata=defn.metadata,
    )
    return updated.with_fingerprint(pipeline_fingerprint(updated))


def add_node(defn: PipelineDefinition, node: NodeDefinition) -> PipelineDefinition:
    """Immutable add-node helper."""
    if any(n.name == node.name for n in defn.nodes):
        raise ValueError(f"Node {node.name!r} already exists")
    return replace_nodes(defn, (*defn.nodes, node))


def remove_node(defn: PipelineDefinition, name: str) -> PipelineDefinition:
    """Remove a node and any incident edges."""
    nodes = tuple(n for n in defn.nodes if n.name != name)
    edges = tuple(
        e
        for e in defn.edges
        if e.producer_node != name and e.consumer_node != name
    )
    updated = PipelineDefinition(
        schema=defn.schema,
        pipeline_id=defn.pipeline_id,
        pipeline_name=defn.pipeline_name,
        version=defn.version,
        contracts=defn.contracts,
        transformations=defn.transformations,
        nodes=nodes,
        edges=edges,
        profile_ref=defn.profile_ref,
        policy_refs=defn.policy_refs,
        reliability=defn.reliability,
        provenance=defn.provenance,
        extensions=defn.extensions,
        metadata=defn.metadata,
    )
    return updated.with_fingerprint(pipeline_fingerprint(updated))


def connect(
    defn: PipelineDefinition,
    producer_node: str,
    producer_port: str,
    consumer_node: str,
    consumer_port: str,
    *,
    producer_contract_id: str | None = None,
    consumer_contract_id: str | None = None,
) -> PipelineDefinition:
    """Add an edge between existing nodes."""
    by_name = {n.name: n for n in defn.nodes}
    if producer_node not in by_name or consumer_node not in by_name:
        raise ValueError("Cannot connect unknown nodes")
    producer = by_name[producer_node]
    consumer = by_name[consumer_node]
    producer_ports = {p.name for p in producer.outputs}
    consumer_ports = {p.name for p in (*consumer.inputs, *consumer.parameters)}
    if producer_port not in producer_ports:
        raise ValueError(
            f"Unknown producer port {producer_node!r}.{producer_port!r}; "
            f"available={sorted(producer_ports)}"
        )
    if consumer_port not in consumer_ports:
        raise ValueError(
            f"Unknown consumer port {consumer_node!r}.{consumer_port!r}; "
            f"available={sorted(consumer_ports)}"
        )
    new_edge = edge(
        producer_node,
        producer_port,
        consumer_node,
        consumer_port,
        producer_contract_id=producer_contract_id,
        consumer_contract_id=consumer_contract_id,
    )
    updated = PipelineDefinition(
        schema=defn.schema,
        pipeline_id=defn.pipeline_id,
        pipeline_name=defn.pipeline_name,
        version=defn.version,
        contracts=defn.contracts,
        transformations=defn.transformations,
        nodes=defn.nodes,
        edges=(*defn.edges, new_edge),
        profile_ref=defn.profile_ref,
        policy_refs=defn.policy_refs,
        reliability=defn.reliability,
        provenance=defn.provenance,
        extensions=defn.extensions,
        metadata=defn.metadata,
    )
    return updated.with_fingerprint(pipeline_fingerprint(updated))


def disconnect(
    defn: PipelineDefinition,
    producer_node: str,
    producer_port: str,
    consumer_node: str,
    consumer_port: str,
) -> PipelineDefinition:
    """Remove a matching edge."""
    edges = tuple(
        e
        for e in defn.edges
        if not (
            e.producer_node == producer_node
            and e.producer_port == producer_port
            and e.consumer_node == consumer_node
            and e.consumer_port == consumer_port
        )
    )
    updated = PipelineDefinition(
        schema=defn.schema,
        pipeline_id=defn.pipeline_id,
        pipeline_name=defn.pipeline_name,
        version=defn.version,
        contracts=defn.contracts,
        transformations=defn.transformations,
        nodes=defn.nodes,
        edges=edges,
        profile_ref=defn.profile_ref,
        policy_refs=defn.policy_refs,
        reliability=defn.reliability,
        provenance=defn.provenance,
        extensions=defn.extensions,
        metadata=defn.metadata,
    )
    return updated.with_fingerprint(pipeline_fingerprint(updated))


def clone_definition(defn: PipelineDefinition) -> PipelineDefinition:
    """Return a fingerprint-stable clone (same content)."""
    return pipeline_from_clone(defn)


def pipeline_from_clone(defn: PipelineDefinition) -> PipelineDefinition:
    from etlantic.authoring.serialize import pipeline_from_dict, pipeline_to_dict

    return pipeline_from_dict(pipeline_to_dict(defn), verify=True)
