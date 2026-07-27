"""Normalize class-authored pipelines into PipelineDefinition and back to LogicalGraph."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
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
from etlantic.identity import (
    contract_id,
    node_id,
    pipeline_id,
    published_contract_id,
    published_contract_version,
)
from etlantic.model import (
    Edge,
    LogicalGraph,
    Node,
    NodeKind,
    ParameterSpec,
    PortSpec,
)
from etlantic.pipeline import (
    Extract,
    Load,
    Pipeline,
    SubpipelineInstance,
    _resolve_binding_ref,
)
from etlantic.plan.freeze import immutable_mapping
from etlantic.transformation import Step, Transformation


def _type_name(value_type: type[Any] | None) -> str | None:
    if value_type is None:
        return None
    mapping = {
        int: "integer",
        str: "string",
        bool: "boolean",
        float: "number",
        bytes: "binary",
    }
    if value_type in mapping:
        return mapping[value_type]
    origin = getattr(value_type, "__origin__", None)
    if origin is not None:
        return _type_name(origin) or "json"
    return "json"


def _json_safe(value: Any) -> Any:
    """Return a JSON-safe copy or raise TypeError for non-serializable values."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, Mapping):
        return {str(k): _json_safe(v) for k, v in value.items()}
    raise TypeError(
        f"Pipeline definitions cannot embed non-JSON value of type {type(value).__name__}"
    )


def _fields_for_contract(ctype: type[Any]) -> tuple[FieldSpec, ...]:
    try:
        from etlantic.interchange.odcs import schema_fields_for_dtcs

        raw = schema_fields_for_dtcs(ctype)
        return tuple(
            FieldSpec(
                name=str(item["name"]),
                type=str(item["type"]),
                nullable=bool(item.get("nullable", False)),
                required=not bool(item.get("nullable", False)),
            )
            for item in raw
        )
    except Exception:
        # Fall back to pydantic model fields when ODCS projection fails.
        fields: list[FieldSpec] = []
        model_fields = getattr(ctype, "model_fields", None)
        if isinstance(model_fields, Mapping):
            for name, info in model_fields.items():
                ann = getattr(info, "annotation", None)
                fields.append(
                    FieldSpec(
                        name=str(name),
                        type=_type_name(ann) or "json",
                        nullable=not bool(getattr(info, "is_required", lambda: True)()),
                        required=bool(getattr(info, "is_required", lambda: True)()),
                    )
                )
        return tuple(fields)


def _contract_definition(ctype: type[Any]) -> ContractDefinition:
    authoring = contract_id(ctype)
    published = published_contract_id(ctype) or authoring
    return ContractDefinition(
        identity=published,
        name=getattr(ctype, "__name__", published),
        version=published_contract_version(ctype),
        authoring_id=authoring,
        fields=_fields_for_contract(ctype),
        metadata=immutable_mapping({}),
    )


def _port_from_transform_port(
    port: Any, *, value: Any = ..., has_value: bool = False
) -> PortDefinitionSpec:
    direction = port.kind
    ctype = port.contract_type
    cid = contract_id(ctype) if ctype is not None else None
    if direction == "parameter":
        default = port.default
        has_default = bool(port.has_default)
        return PortDefinitionSpec(
            name=port.name,
            direction="parameter",
            contract_id=None,
            value_type=_type_name(ctype),
            default=_json_safe(default) if has_default and default is not ... else ...,
            has_default=has_default,
            value=_json_safe(value) if has_value and value is not ... else ...,
            has_value=has_value,
            role="valid",
            required=not has_default,
        )
    return PortDefinitionSpec(
        name=port.name,
        direction="input" if direction == "input" else "output",
        contract_id=cid,
        value_type=None,
        role=getattr(port, "role", "valid"),
        required=True,
    )


def _transformation_definition(
    transform: type[Transformation],
) -> TransformationDefinition:
    ports: list[PortDefinitionSpec] = []
    for port in transform.inputs():
        ports.append(_port_from_transform_port(port))
    for port in transform.outputs():
        ports.append(_port_from_transform_port(port))
    for port in transform.parameters():
        ports.append(_port_from_transform_port(port))

    impl_refs: list[ImplementationRef] = []
    for engine, record in transform.implementations().items():
        impl_refs.append(
            ImplementationRef(
                engine=engine,
                identity=record.identity,
                kind="native",
                is_async=bool(record.is_async),
            )
        )

    portable_plan: Mapping[str, Any] | None = None
    if transform.portable_definition() is not None:
        try:
            portable_plan = immutable_mapping(transform.to_transform_plan())
        except Exception:
            portable_plan = None

    version = getattr(transform, "__published_version__", None)
    return TransformationDefinition(
        identity=transform.identity(),
        name=transform.__name__,
        version=str(version) if isinstance(version, str) else None,
        ports=tuple(ports),
        implementation_refs=tuple(impl_refs),
        portable_plan=portable_plan,
        metadata=immutable_mapping({}),
    )


def definition_from_pipeline(cls: type[Pipeline]) -> PipelineDefinition:
    """Normalize a class-authored pipeline into an unresolved PipelineDefinition."""
    graph = cls.build_graph()
    members = cls.__pipeline_members__
    contracts: dict[str, ContractDefinition] = {}
    transformations: dict[str, TransformationDefinition] = {}
    nodes: list[NodeDefinition] = []

    def _remember_contract(ctype: type[Any] | None) -> str | None:
        if ctype is None:
            return None
        authoring = contract_id(ctype)
        if authoring not in contracts:
            contracts[authoring] = _contract_definition(ctype)
        return authoring

    for name, member in members.items():
        if isinstance(member, Extract) and not isinstance(member, Load):
            cid = _remember_contract(member.contract_type)
            nodes.append(
                NodeDefinition(
                    name=name,
                    kind="source",
                    identity=node_id(graph.pipeline_id, name),
                    asset=member.asset,
                    contract_id=cid,
                    outputs=(
                        PortDefinitionSpec(
                            name="result",
                            direction="output",
                            contract_id=cid,
                        ),
                    ),
                )
            )
        elif isinstance(member, Step):
            transform = member.transformation
            if transform.identity() not in transformations:
                transformations[transform.identity()] = _transformation_definition(
                    transform
                )
            for port in (*transform.inputs(), *transform.outputs()):
                _remember_contract(port.contract_type)
            params = tuple(
                _port_from_transform_port(
                    p,
                    value=member.parameters.get(p.name, ...),
                    has_value=p.name in member.parameters,
                )
                for p in transform.parameters()
            )
            nodes.append(
                NodeDefinition(
                    name=name,
                    kind="step",
                    identity=node_id(graph.pipeline_id, name),
                    transformation_id=transform.identity(),
                    transformation_name=transform.__name__,
                    inputs=tuple(
                        _port_from_transform_port(p) for p in transform.inputs()
                    ),
                    outputs=tuple(
                        _port_from_transform_port(p) for p in transform.outputs()
                    ),
                    parameters=params,
                )
            )
        elif isinstance(member, Load):
            cid = _remember_contract(member.contract_type)
            nodes.append(
                NodeDefinition(
                    name=name,
                    kind="sink",
                    identity=node_id(graph.pipeline_id, name),
                    asset=member.asset,
                    contract_id=cid,
                    inputs=(
                        PortDefinitionSpec(
                            name="input",
                            direction="input",
                            contract_id=cid,
                        ),
                    ),
                )
            )
        elif isinstance(member, SubpipelineInstance):
            nested_defn = definition_from_pipeline(member.pipeline_cls)
            for c in nested_defn.contracts:
                contracts.setdefault(c.authoring_id or c.identity, c)
            for t in nested_defn.transformations:
                transformations.setdefault(t.identity, t)
            binding_map: dict[str, Any] = {}
            for key, raw in member.bindings.items():
                producer = _resolve_binding_ref(
                    raw, members=members, pipeline_cls=cls, port_hint=key
                )
                if producer is not None and producer.node_name:
                    binding_map[key] = {
                        "node": producer.node_name,
                        "port": producer.port_name,
                    }
                    continue
                node_name = getattr(raw, "node_name", None)
                port_name = getattr(raw, "port_name", None)
                if isinstance(node_name, str) and isinstance(port_name, str):
                    binding_map[key] = {
                        "node": node_name,
                        "port": port_name,
                    }
                    continue
                raise TypeError(
                    f"Cannot serialize subpipeline binding {key!r} on {name!r}: "
                    f"expected a resolvable port reference, got {type(raw).__name__}"
                )
            nodes.append(
                NodeDefinition(
                    name=name,
                    kind="subpipeline",
                    identity=node_id(graph.pipeline_id, name),
                    nested=nested_defn,
                    nested_pipeline_id=nested_defn.pipeline_id,
                    inputs=tuple(
                        PortDefinitionSpec(
                            name=n.name,
                            direction="input",
                            contract_id=n.contract_id,
                        )
                        for n in nested_defn.nodes
                        if n.kind == "source"
                    ),
                    outputs=tuple(
                        PortDefinitionSpec(
                            name=n.name,
                            direction="output",
                            contract_id=n.contract_id,
                        )
                        for n in nested_defn.nodes
                        if n.kind == "sink"
                    ),
                    bindings=immutable_mapping(binding_map),
                )
            )

    edges = tuple(
        EdgeDefinition(
            producer_node=e.producer_node,
            producer_port=e.producer_port,
            consumer_node=e.consumer_node,
            consumer_port=e.consumer_port,
            producer_contract_id=e.producer_contract_id,
            consumer_contract_id=e.consumer_contract_id,
        )
        for e in graph.edges
    )

    provenance: dict[str, Any] = {}
    published = getattr(cls, "__published_id__", None)
    if isinstance(published, str) and published:
        provenance["published_id"] = published
    published_version = getattr(cls, "__published_version__", None)
    if isinstance(published_version, str) and published_version:
        provenance["published_version"] = published_version
    provenance["kind"] = "python"
    provenance["source_identity"] = pipeline_id(cls)

    return PipelineDefinition(
        schema=PIPELINE_SCHEMA,
        pipeline_id=graph.pipeline_id,
        pipeline_name=graph.pipeline_name,
        version=(
            str(published_version) if isinstance(published_version, str) else None
        ),
        contracts=tuple(contracts.values()),
        transformations=tuple(transformations.values()),
        nodes=tuple(nodes),
        edges=edges,
        provenance=immutable_mapping(provenance),
        metadata=immutable_mapping(dict(graph.metadata) if graph.metadata else {}),
    )


def logical_graph_from_definition(defn: PipelineDefinition) -> LogicalGraph:
    """Project a PipelineDefinition into an in-memory LogicalGraph."""
    nodes: list[Node] = []
    for node in defn.nodes:
        kind = NodeKind(node.kind)
        inputs = tuple(
            PortSpec(
                name=p.name,
                direction="input",
                contract_type=None,
                contract_id=p.contract_id,
                required=p.required,
                role=p.role,
            )
            for p in node.inputs
        )
        outputs = tuple(
            PortSpec(
                name=p.name,
                direction="output",
                contract_type=None,
                contract_id=p.contract_id,
                required=p.required,
                role=p.role,
            )
            for p in node.outputs
        )
        parameters = tuple(
            ParameterSpec(
                name=p.name,
                value_type=None,
                default=p.default if p.has_default else ...,
                has_default=p.has_default,
                value=p.value if p.has_value else ...,
                has_value=p.has_value,
            )
            for p in node.parameters
        )
        nested_graph = (
            logical_graph_from_definition(node.nested)
            if node.nested is not None
            else None
        )
        nodes.append(
            Node(
                name=node.name,
                kind=kind,
                identity=node.identity,
                contract_type=None,
                contract_id=node.contract_id,
                binding=node.asset,
                transformation_id=node.transformation_id,
                transformation_name=node.transformation_name,
                inputs=inputs,
                outputs=outputs,
                parameters=parameters,
                nested_pipeline_id=node.nested_pipeline_id,
                nested_graph=nested_graph,
                metadata=MappingProxyType(dict(node.metadata)),
            )
        )
    edges = tuple(
        Edge(
            producer_node=e.producer_node,
            producer_port=e.producer_port,
            consumer_node=e.consumer_node,
            consumer_port=e.consumer_port,
            producer_contract_id=e.producer_contract_id,
            consumer_contract_id=e.consumer_contract_id,
        )
        for e in defn.edges
    )
    return LogicalGraph(
        pipeline_id=defn.pipeline_id,
        pipeline_name=defn.pipeline_name,
        nodes=tuple(nodes),
        edges=edges,
        metadata=MappingProxyType(dict(defn.metadata)),
    )


def authoring_graph_fingerprint(defn: PipelineDefinition) -> tuple[Any, ...]:
    """Fingerprint a definition's topology using authoring contract ids only."""
    nodes = tuple(
        (
            node.name,
            node.kind,
            node.asset,
            node.transformation_id,
            tuple(
                (p.name, p.direction, p.contract_id, p.role)
                for p in (*node.inputs, *node.outputs)
            ),
            tuple(
                (
                    p.name,
                    p.value_type,
                    p.has_default,
                    p.has_value,
                    p.default if p.has_default else None,
                    p.value if p.has_value else None,
                )
                for p in node.parameters
            ),
        )
        for node in defn.nodes
    )
    edges = tuple(
        (
            e.producer_node,
            e.producer_port,
            e.consumer_node,
            e.consumer_port,
        )
        for e in defn.edges
    )
    return nodes, edges
