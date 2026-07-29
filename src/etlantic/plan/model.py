"""Immutable PipelinePlan IR (schema etlantic.plan/1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from etlantic.model import Edge, LogicalGraph, Node, NodeKind, ParameterSpec, PortSpec
from etlantic.plan.artifacts import ArtifactRef
from etlantic.plan.freeze import deep_freeze, mutable_copy
from etlantic.plan.regions import ExecutionRegion, MaterializationBoundary
from etlantic.registry import BindingDescriptor, ImplementationDescriptor

PLAN_SCHEMA = "etlantic.plan/1"


def _plan_metadata_strict(profile_snapshot: dict[str, Any]) -> bool:
    mode = str(profile_snapshot.get("security_mode") or "").strip().lower()
    name = str(profile_snapshot.get("name") or "").strip().lower()
    # Fail closed when the snapshot claims production by mode *or* by an
    # authoritative production profile name; never trust a development mode
    # alone if the plan identity says production.
    return bool(mode == "production" or name == "production")


def _assert_plan_snapshot_consistent(profile_snapshot: dict[str, Any]) -> None:
    mode = str(profile_snapshot.get("security_mode") or "").strip().lower()
    name = str(profile_snapshot.get("name") or "").strip().lower()
    if name == "production" and mode and mode != "production":
        raise ValueError(
            "Plan profile_snapshot name is 'production' but security_mode "
            f"is {mode!r}; failing closed."
        )


@dataclass(frozen=True, slots=True)
class PhysicalUnit:
    """A physical execution unit mapped from one or more logical nodes."""

    identity: str
    region_id: str
    logical_nodes: tuple[str, ...]
    engine: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize physical unit."""
        return {
            "identity": self.identity,
            "region_id": self.region_id,
            "logical_nodes": list(self.logical_nodes),
            "engine": self.engine,
            "metadata": mutable_copy(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, strict: bool = False) -> PhysicalUnit:
        """Deserialize physical unit."""
        from etlantic.extensions import validate_extension_metadata

        metadata = dict(data.get("metadata") or {})
        validate_extension_metadata(
            metadata, path="physical_unit.metadata", strict=strict
        )
        unit = cls(
            identity=str(data["identity"]),
            region_id=str(data["region_id"]),
            logical_nodes=tuple(data.get("logical_nodes") or ()),
            engine=str(data["engine"]),
            metadata=metadata,
        )
        object.__setattr__(unit, "metadata", deep_freeze(unit.metadata))
        return unit


@dataclass(frozen=True, slots=True)
class OutputResolution:
    """Resolved strategy for a logical output port."""

    node_name: str
    port_name: str
    artifact: ArtifactRef

    def to_dict(self) -> dict[str, Any]:
        """Serialize output resolution."""
        return {
            "node_name": self.node_name,
            "port_name": self.port_name,
            "artifact": self.artifact.to_dict(),
        }

    @classmethod
    def from_dict(
        cls, data: dict[str, Any], *, strict: bool = False
    ) -> OutputResolution:
        """Deserialize output resolution."""
        resolution = cls(
            node_name=str(data["node_name"]),
            port_name=str(data["port_name"]),
            artifact=ArtifactRef.from_dict(data["artifact"], strict=strict),
        )
        object.__setattr__(
            resolution.artifact,
            "metadata",
            deep_freeze(resolution.artifact.metadata),
        )
        return resolution


@dataclass(frozen=True, slots=True)
class PipelinePlan:
    """Immutable, versioned, secret-free execution-facing intermediate representation.

    Produced by :func:`~etlantic.plan.planner.plan_pipeline` or
    :meth:`~etlantic.pipeline.Pipeline.plan`. Wire schema id:
    :data:`~etlantic.plan.model.PLAN_SCHEMA` (``etlantic.plan/1``).

    Plans contain secret **references** only — never resolved secret values.
    Nested mappings owned by the plan are deep-frozen after construction.

    Serialize with :meth:`to_dict` / :func:`~etlantic.plan.serialize.plan_to_json`.
    Deserialize with :meth:`from_dict` / :func:`~etlantic.plan.serialize.plan_from_json`.
    Verify integrity with :func:`~etlantic.plan.serialize.verify_plan_fingerprint`
    before compile or run trust boundaries.
    """

    schema: str
    plan_id: str
    pipeline_id: str
    pipeline_name: str
    profile_name: str
    fingerprint: str
    logical_graph: LogicalGraph
    regions: tuple[ExecutionRegion, ...] = ()
    physical_units: tuple[PhysicalUnit, ...] = ()
    logical_to_physical: dict[str, str] = field(default_factory=dict)
    implementations: dict[str, ImplementationDescriptor] = field(default_factory=dict)
    bindings: dict[str, BindingDescriptor] = field(default_factory=dict)
    resource_refs: dict[str, dict[str, Any]] = field(default_factory=dict)
    materialization_boundaries: tuple[MaterializationBoundary, ...] = ()
    output_resolutions: tuple[OutputResolution, ...] = ()
    capability_decisions: tuple[dict[str, Any], ...] = ()
    selected_nodes: tuple[str, ...] | None = None
    security_domain: str = "default"
    contract_versions: dict[str, str] = field(default_factory=dict)
    plugin_versions: dict[str, str] = field(default_factory=dict)
    intents: dict[str, Any] = field(default_factory=dict)
    profile_snapshot: dict[str, Any] = field(default_factory=dict)
    execution_settings: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize plan to a JSON-friendly dict."""
        return {
            "schema": self.schema,
            "plan_id": self.plan_id,
            "pipeline_id": self.pipeline_id,
            "pipeline_name": self.pipeline_name,
            "profile_name": self.profile_name,
            "fingerprint": self.fingerprint,
            "logical_graph": _graph_to_dict(self.logical_graph),
            "regions": [r.to_dict() for r in self.regions],
            "physical_units": [u.to_dict() for u in self.physical_units],
            "logical_to_physical": mutable_copy(self.logical_to_physical),
            "implementations": {
                k: v.to_dict() for k, v in self.implementations.items()
            },
            "bindings": {k: v.to_dict() for k, v in self.bindings.items()},
            "resource_refs": mutable_copy(self.resource_refs),
            "materialization_boundaries": [
                b.to_dict() for b in self.materialization_boundaries
            ],
            "output_resolutions": [o.to_dict() for o in self.output_resolutions],
            "capability_decisions": mutable_copy(list(self.capability_decisions)),
            "selected_nodes": (
                list(self.selected_nodes) if self.selected_nodes is not None else None
            ),
            "security_domain": self.security_domain,
            "contract_versions": mutable_copy(self.contract_versions),
            "plugin_versions": mutable_copy(self.plugin_versions),
            "intents": mutable_copy(self.intents),
            "profile_snapshot": mutable_copy(self.profile_snapshot),
            "execution_settings": mutable_copy(self.execution_settings),
            "metadata": mutable_copy(self.metadata),
        }

    def compile(
        self,
        *,
        target: str = "airflow",
        profile: Any = None,
        plugin: Any = None,
        **kwargs: Any,
    ) -> Any:
        """Compile this plan for an external orchestrator.

        Delegates to :func:`etlantic.orchestration.compile_plan`. Verifies the
        plan fingerprint before compilation.

        Args:
            target: Orchestrator engine id (default ``"airflow"``).
            profile: Optional profile for compilation context.
            plugin: Optional pre-constructed orchestrator plugin instance.
            **kwargs: Forwarded to :func:`~etlantic.orchestration.compile_plan`.

        Returns:
            :class:`~etlantic.orchestration.protocol.CompiledOrchestrationArtifact`.

        Raises:
            ValueError: When the embedded fingerprint does not match content.
            OrchestrationCompilationError: When compilation fails closed.
        """
        from etlantic.orchestration.compile import compile_plan

        return compile_plan(
            self, target=target, profile=profile, plugin=plugin, **kwargs
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, verify: bool = True) -> PipelinePlan:
        """Deserialize a plan mapping.

        Requires ``schema`` equal to :data:`PLAN_SCHEMA`. Missing or unknown
        schemas are rejected (no silent default). Documents are upgraded via
        :func:`etlantic.plan.upgrade.upgrade_plan_dict` first.

        When ``verify`` is True and a non-empty fingerprint is present, the
        embedded fingerprint is checked after construction. Empty fingerprints
        (e.g. intermediate planner builds) skip verification.
        """
        from etlantic.extensions import validate_extension_metadata
        from etlantic.plan.upgrade import UnsupportedPlanSchemaError, upgrade_plan_dict

        data = upgrade_plan_dict(data)
        schema = data.get("schema")
        if schema is None or schema == "":
            raise UnsupportedPlanSchemaError(
                f"PipelinePlan is missing required 'schema' (expected {PLAN_SCHEMA!r})."
            )
        if schema != PLAN_SCHEMA:
            raise UnsupportedPlanSchemaError(
                f"Unknown PipelinePlan schema {schema!r}; expected {PLAN_SCHEMA!r}."
            )
        profile_snapshot = dict(data.get("profile_snapshot") or {})
        strict = _plan_metadata_strict(profile_snapshot)
        metadata = dict(data.get("metadata") or {})
        validate_extension_metadata(metadata, path="metadata", strict=strict)
        plan = cls(
            schema=str(schema),
            plan_id=str(data["plan_id"]),
            pipeline_id=str(data["pipeline_id"]),
            pipeline_name=str(data["pipeline_name"]),
            profile_name=str(data["profile_name"]),
            fingerprint=str(data["fingerprint"]),
            logical_graph=_graph_from_dict(data["logical_graph"], strict=strict),
            regions=tuple(
                ExecutionRegion.from_dict(r, strict=strict)
                for r in data.get("regions") or ()
            ),
            physical_units=tuple(
                PhysicalUnit.from_dict(u, strict=strict)
                for u in data.get("physical_units") or ()
            ),
            logical_to_physical=dict(data.get("logical_to_physical") or {}),
            implementations={
                k: ImplementationDescriptor.from_dict(v)
                for k, v in (data.get("implementations") or {}).items()
            },
            bindings={
                k: BindingDescriptor.from_dict(v)
                for k, v in (data.get("bindings") or {}).items()
            },
            resource_refs=dict(data.get("resource_refs") or {}),
            materialization_boundaries=tuple(
                MaterializationBoundary.from_dict(b, strict=strict)
                for b in data.get("materialization_boundaries") or ()
            ),
            output_resolutions=tuple(
                OutputResolution.from_dict(o, strict=strict)
                for o in data.get("output_resolutions") or ()
            ),
            capability_decisions=tuple(data.get("capability_decisions") or ()),
            selected_nodes=(
                tuple(data["selected_nodes"])
                if data.get("selected_nodes") is not None
                else None
            ),
            security_domain=str(data.get("security_domain") or "default"),
            contract_versions=dict(data.get("contract_versions") or {}),
            plugin_versions=dict(data.get("plugin_versions") or {}),
            intents=dict(data.get("intents") or {}),
            profile_snapshot=profile_snapshot,
            execution_settings=dict(data.get("execution_settings") or {}),
            metadata=metadata,
        )
        object.__setattr__(
            plan, "logical_to_physical", deep_freeze(plan.logical_to_physical)
        )
        object.__setattr__(plan, "implementations", deep_freeze(plan.implementations))
        object.__setattr__(plan, "bindings", deep_freeze(plan.bindings))
        object.__setattr__(plan, "resource_refs", deep_freeze(plan.resource_refs))
        object.__setattr__(
            plan,
            "capability_decisions",
            tuple(deep_freeze(item) for item in plan.capability_decisions),
        )
        object.__setattr__(
            plan, "contract_versions", deep_freeze(plan.contract_versions)
        )
        object.__setattr__(plan, "plugin_versions", deep_freeze(plan.plugin_versions))
        object.__setattr__(plan, "intents", deep_freeze(plan.intents))
        object.__setattr__(plan, "profile_snapshot", deep_freeze(plan.profile_snapshot))
        object.__setattr__(
            plan, "execution_settings", deep_freeze(plan.execution_settings)
        )
        object.__setattr__(plan, "metadata", deep_freeze(plan.metadata))
        validate_plan_interchange(plan)
        _assert_plan_snapshot_consistent(dict(plan.profile_snapshot or {}))
        if verify:
            if not plan.fingerprint:
                raise ValueError(
                    "PipelinePlan.from_dict(verify=True) requires a non-empty fingerprint"
                )
            from etlantic.plan.serialize import verify_plan_fingerprint

            verify_plan_fingerprint(plan)
        return plan


def validate_plan_interchange(plan: PipelinePlan) -> None:
    """Fail closed on invalid tabular interchange boundary metadata."""
    from etlantic.interchange.tabular import validate_descriptor

    for boundary in plan.materialization_boundaries:
        if "interchange" not in boundary.metadata:
            continue
        validate_descriptor(boundary.metadata["interchange"])


def _graph_to_dict(graph: LogicalGraph) -> dict[str, Any]:
    return {
        "pipeline_id": graph.pipeline_id,
        "pipeline_name": graph.pipeline_name,
        "nodes": [_node_to_dict(n) for n in graph.nodes],
        "edges": [
            {
                "producer_node": e.producer_node,
                "producer_port": e.producer_port,
                "consumer_node": e.consumer_node,
                "consumer_port": e.consumer_port,
                "producer_contract_id": e.producer_contract_id,
                "consumer_contract_id": e.consumer_contract_id,
            }
            for e in graph.edges
        ],
        "metadata": mutable_copy(graph.metadata),
    }


def _node_to_dict(node: Node) -> dict[str, Any]:
    return {
        "name": node.name,
        "kind": node.kind.value,
        "identity": node.identity,
        "contract_id": node.contract_id,
        "binding": node.binding,
        "transformation_id": node.transformation_id,
        "transformation_name": node.transformation_name,
        "inputs": [
            {
                "name": p.name,
                "direction": p.direction,
                "contract_id": p.contract_id,
                "required": p.required,
                "role": p.role,
            }
            for p in node.inputs
        ],
        "outputs": [
            {
                "name": p.name,
                "direction": p.direction,
                "contract_id": p.contract_id,
                "required": p.required,
                "role": p.role,
            }
            for p in node.outputs
        ],
        "parameters": [
            {
                "name": p.name,
                "has_default": p.has_default,
                "has_value": p.has_value,
            }
            for p in node.parameters
        ],
        "nested_pipeline_id": node.nested_pipeline_id,
        "metadata": mutable_copy(node.metadata),
    }


def _graph_from_dict(data: dict[str, Any], *, strict: bool = False) -> LogicalGraph:
    from etlantic.extensions import validate_extension_metadata

    graph_metadata = dict(data.get("metadata") or {})
    validate_extension_metadata(
        graph_metadata, path="logical_graph.metadata", strict=strict
    )
    nodes = tuple(_node_from_dict(n, strict=strict) for n in data.get("nodes") or ())
    edges = tuple(
        Edge(
            producer_node=e["producer_node"],
            producer_port=e["producer_port"],
            consumer_node=e["consumer_node"],
            consumer_port=e["consumer_port"],
            producer_contract_id=e.get("producer_contract_id"),
            consumer_contract_id=e.get("consumer_contract_id"),
        )
        for e in data.get("edges") or ()
    )
    return LogicalGraph(
        pipeline_id=str(data["pipeline_id"]),
        pipeline_name=str(data["pipeline_name"]),
        nodes=nodes,
        edges=edges,
        metadata=deep_freeze(graph_metadata),
    )


def _node_from_dict(data: dict[str, Any], *, strict: bool = False) -> Node:
    from etlantic.extensions import validate_extension_metadata

    node_metadata = dict(data.get("metadata") or {})
    validate_extension_metadata(node_metadata, path="node.metadata", strict=strict)
    return Node(
        name=str(data["name"]),
        kind=NodeKind(str(data["kind"])),
        identity=str(data["identity"]),
        contract_id=data.get("contract_id"),
        binding=data.get("binding"),
        transformation_id=data.get("transformation_id"),
        transformation_name=data.get("transformation_name"),
        inputs=tuple(
            PortSpec(
                name=p["name"],
                direction=p["direction"],
                contract_type=None,
                contract_id=p.get("contract_id"),
                required=bool(p.get("required", True)),
                role=str(p.get("role") or "valid"),
            )
            for p in data.get("inputs") or ()
        ),
        outputs=tuple(
            PortSpec(
                name=p["name"],
                direction=p["direction"],
                contract_type=None,
                contract_id=p.get("contract_id"),
                required=bool(p.get("required", True)),
                role=str(p.get("role") or "valid"),
            )
            for p in data.get("outputs") or ()
        ),
        parameters=tuple(
            ParameterSpec(
                name=p["name"],
                value_type=None,
                has_default=bool(p.get("has_default", False)),
                has_value=bool(p.get("has_value", False)),
            )
            for p in data.get("parameters") or ()
        ),
        nested_pipeline_id=data.get("nested_pipeline_id"),
        metadata=deep_freeze(node_metadata),
    )
