"""Closed adaptive planning IR (schema ``etlantic.plan/2``).

This module contains representation and integrity checks only.  It deliberately
does not discover plugins, solve placement, or execute physical units.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias

from etlantic.model import LogicalGraph
from etlantic.plan.freeze import deep_freeze, mutable_copy
from etlantic.plan.model import PipelinePlan
from etlantic.plan.physical import PHYSICAL_UNIT_SCHEMA, PhysicalDAG

ADAPTIVE_PLAN_SCHEMA = "etlantic.plan/2"
ADAPTIVE_LIMITS_VERSION = "etlantic.adaptive-limits/1"


@dataclass(frozen=True, slots=True)
class TargetDescriptor:
    """Canonical, secret-free identity and evidence for one eligible target."""

    target_id: str
    identity: str
    engine: str
    compiler: str | None = None
    executor: str | None = None
    connector: str | None = None
    resource: str | None = None
    location: str = "local"
    security_domain: str = "default"
    protocol_versions: Mapping[str, str] = field(default_factory=dict)
    capability_fingerprint: str = ""
    evidence_refs: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("target_id", "identity", "engine", "location", "security_domain"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"PMADP201: target descriptor {name} is required")
        for name in ("compiler", "executor", "connector", "resource"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(
                    f"PMADP201: target descriptor {name} must be a non-blank string or null"
                )
        protocol_versions = _validated_string_map(
            self.protocol_versions, "target descriptor protocol_versions"
        )
        if not isinstance(self.capability_fingerprint, str):
            raise ValueError(
                "PMADP201: target descriptor capability_fingerprint must be a string"
            )
        evidence_refs = _validated_array(
            self.evidence_refs, "target descriptor evidence_refs", code="PMADP202"
        )
        if any(
            not isinstance(value, str) or not value.strip() for value in evidence_refs
        ):
            raise ValueError("PMADP202: evidence_refs must contain non-blank strings")
        object.__setattr__(self, "evidence_refs", evidence_refs)
        object.__setattr__(self, "protocol_versions", deep_freeze(protocol_versions))
        metadata = _validated_metadata(self.metadata, "target descriptor metadata")
        object.__setattr__(self, "metadata", deep_freeze(metadata))
        _reject_wire_sensitive_material(self.to_dict(), path="target descriptor")

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "identity": self.identity,
            "engine": self.engine,
            "compiler": self.compiler,
            "executor": self.executor,
            "connector": self.connector,
            "resource": self.resource,
            "location": self.location,
            "security_domain": self.security_domain,
            "protocol_versions": mutable_copy(self.protocol_versions),
            "capability_fingerprint": self.capability_fingerprint,
            "evidence_refs": list(self.evidence_refs),
            "metadata": mutable_copy(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> TargetDescriptor:
        _reject_unknown(data, set(cls.__dataclass_fields__), "target descriptor")
        _require_fields(data, set(cls.__dataclass_fields__), "target descriptor")
        return cls(
            target_id=data["target_id"],
            identity=data["identity"],
            engine=data["engine"],
            compiler=data.get("compiler"),
            executor=data.get("executor"),
            connector=data.get("connector"),
            resource=data.get("resource"),
            location=data.get("location", "local"),
            security_domain=data.get("security_domain", "default"),
            protocol_versions=data.get("protocol_versions", {}),
            capability_fingerprint=data.get("capability_fingerprint", ""),
            evidence_refs=data.get("evidence_refs", ()),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True, slots=True)
class AdaptiveInventory:
    """Complete ordered inventory used as the candidate solver input."""

    targets: tuple[TargetDescriptor, ...]
    eligible_target_order: tuple[str, ...]
    fingerprint: str
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        targets = _validated_array(self.targets, "adaptive inventory targets")
        targets = tuple(
            target
            if isinstance(target, TargetDescriptor)
            else TargetDescriptor.from_dict(target)
            for target in targets
        )
        target_ids = [target.target_id for target in targets]
        if len(set(target_ids)) != len(target_ids):
            raise ValueError("PMADP201: inventory target ids must be unique")
        order = _validated_array(
            self.eligible_target_order, "adaptive inventory eligible_target_order"
        )
        if any(
            not isinstance(target_id, str) or not target_id.strip()
            for target_id in order
        ):
            raise ValueError(
                "PMADP201: inventory eligible order must contain target ids"
            )
        if len(set(order)) != len(order) or set(order) != set(target_ids):
            raise ValueError(
                "PMADP201: inventory eligible order must cover every target once"
            )
        if not isinstance(self.fingerprint, str) or not self.fingerprint.strip():
            raise ValueError("PMADP201: inventory fingerprint is required")
        evidence_refs = _validated_array(
            self.evidence_refs, "adaptive inventory evidence_refs", code="PMADP202"
        )
        if any(not isinstance(ref, str) or not ref.strip() for ref in evidence_refs):
            raise ValueError("PMADP202: inventory evidence_refs must contain strings")
        object.__setattr__(self, "targets", targets)
        object.__setattr__(self, "eligible_target_order", order)
        object.__setattr__(self, "evidence_refs", evidence_refs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "targets": [target.to_dict() for target in self.targets],
            "eligible_target_order": list(self.eligible_target_order),
            "fingerprint": self.fingerprint,
            "evidence_refs": list(self.evidence_refs),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AdaptiveInventory:
        _reject_unknown(data, set(cls.__dataclass_fields__), "adaptive inventory")
        _require_fields(data, set(cls.__dataclass_fields__), "adaptive inventory")
        return cls(
            targets=data.get("targets", ()),
            eligible_target_order=data.get("eligible_target_order", ()),
            fingerprint=data.get("fingerprint", ""),
            evidence_refs=data.get("evidence_refs", ()),
        )


CandidateStatus = Literal["eligible", "rejected"]
CandidateKind = Literal["source", "sink", "compute"]


@dataclass(frozen=True, slots=True)
class CandidateRecord:
    """One complete node x target matrix cell, including rejected cells."""

    candidate_id: str
    node_name: str
    target_id: str
    kind: CandidateKind | str
    status: CandidateStatus | str
    reason_codes: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    objective_facts: Mapping[str, int] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("candidate_id", "node_name", "target_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"PMADP220: candidate {name} is required")
        if not isinstance(self.kind, str) or self.kind not in {
            "source",
            "sink",
            "compute",
        }:
            raise ValueError(f"PMADP220: unknown candidate kind {self.kind!r}")
        if not isinstance(self.status, str) or self.status not in {
            "eligible",
            "rejected",
        }:
            raise ValueError(f"PMADP220: unknown candidate status {self.status!r}")
        reason_codes = _validated_array(
            self.reason_codes, "candidate reason_codes", code="PMADP220"
        )
        evidence_refs = _validated_array(
            self.evidence_refs, "candidate evidence_refs", code="PMADP220"
        )
        if any(
            not isinstance(value, str) or not value.strip()
            for value in (*reason_codes, *evidence_refs)
        ):
            raise ValueError("PMADP220: candidate references must be non-blank strings")
        if not reason_codes and self.status == "rejected":
            raise ValueError("PMADP221: rejected candidate requires reason_codes")
        if self.status == "eligible" and reason_codes:
            raise ValueError(
                "PMADP220: eligible candidate cannot contain rejection reasons"
            )
        objective_facts = _validated_integer_map(
            self.objective_facts, "candidate objective_facts"
        )
        if any(type(value) is not int for value in objective_facts.values()):
            raise ValueError("PMADP321: candidate objective facts must be integers")
        object.__setattr__(self, "reason_codes", reason_codes)
        object.__setattr__(self, "evidence_refs", evidence_refs)
        object.__setattr__(self, "objective_facts", deep_freeze(objective_facts))
        metadata = _validated_metadata(self.metadata, "candidate metadata")
        object.__setattr__(self, "metadata", deep_freeze(metadata))
        _reject_wire_sensitive_material(self.to_dict(), path="candidate")

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "node_name": self.node_name,
            "target_id": self.target_id,
            "kind": self.kind,
            "status": self.status,
            "reason_codes": list(self.reason_codes),
            "evidence_refs": list(self.evidence_refs),
            "objective_facts": mutable_copy(self.objective_facts),
            "metadata": mutable_copy(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CandidateRecord:
        _reject_unknown(data, set(cls.__dataclass_fields__), "candidate record")
        _require_fields(data, set(cls.__dataclass_fields__), "candidate record")
        return cls(
            candidate_id=data["candidate_id"],
            node_name=data["node_name"],
            target_id=data["target_id"],
            kind=data["kind"],
            status=data["status"],
            reason_codes=data.get("reason_codes", ()),
            evidence_refs=data.get("evidence_refs", ()),
            objective_facts=data.get("objective_facts", {}),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True, slots=True)
class AdaptiveDecision:
    """Selected candidate reference for one selected logical node."""

    node_name: str
    candidate_id: str
    target_id: str

    def __post_init__(self) -> None:
        for name in ("node_name", "candidate_id", "target_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"PMADP320: adaptive decision {name} is required")

    def to_dict(self) -> dict[str, str]:
        return {
            "node_name": self.node_name,
            "candidate_id": self.candidate_id,
            "target_id": self.target_id,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AdaptiveDecision:
        _reject_unknown(data, set(cls.__dataclass_fields__), "adaptive decision")
        _require_fields(data, set(cls.__dataclass_fields__), "adaptive decision")
        return cls(
            node_name=data["node_name"],
            candidate_id=data["candidate_id"],
            target_id=data["target_id"],
        )


@dataclass(frozen=True, slots=True)
class AdaptiveRegion:
    """A deterministic connected region in the adaptive physical lowering."""

    identity: str
    target_id: str
    logical_nodes: tuple[str, ...]
    dependencies: tuple[str, ...] = ()
    fused: bool = False
    security_domain: str = "default"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("identity", "target_id", "security_domain"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"PMADP403: adaptive region {name} is required")
        nodes = _validated_array(
            self.logical_nodes, "adaptive region logical_nodes", code="PMADP403"
        )
        if (
            not nodes
            or any(not isinstance(node, str) or not node.strip() for node in nodes)
            or len(set(nodes)) != len(nodes)
        ):
            raise ValueError("PMADP403: adaptive regions require unique logical nodes")
        dependencies = _validated_array(
            self.dependencies, "adaptive region dependencies", code="PMADP402"
        )
        if any(
            not isinstance(dependency, str) or not dependency.strip()
            for dependency in dependencies
        ):
            raise ValueError("PMADP402: adaptive region dependencies must be non-blank")
        if len(set(dependencies)) != len(dependencies):
            raise ValueError("PMADP402: adaptive region dependencies must be unique")
        if type(self.fused) is not bool:
            raise ValueError("PMADP400: adaptive region fused must be a boolean")
        object.__setattr__(self, "logical_nodes", nodes)
        object.__setattr__(self, "dependencies", dependencies)
        metadata = _validated_metadata(self.metadata, "adaptive region metadata")
        object.__setattr__(self, "metadata", deep_freeze(metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity,
            "target_id": self.target_id,
            "logical_nodes": list(self.logical_nodes),
            "dependencies": list(self.dependencies),
            "fused": self.fused,
            "security_domain": self.security_domain,
            "metadata": mutable_copy(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AdaptiveRegion:
        _reject_unknown(data, set(cls.__dataclass_fields__), "adaptive region")
        _require_fields(data, set(cls.__dataclass_fields__), "adaptive region")
        return cls(
            identity=data["identity"],
            target_id=data["target_id"],
            logical_nodes=data.get("logical_nodes", ()),
            dependencies=data.get("dependencies", ()),
            fused=data.get("fused", False),
            security_domain=data.get("security_domain", "default"),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True, slots=True)
class AdaptivePipelinePlan:
    """Immutable, closed, secret-free adaptive plan document."""

    schema: str
    plan_id: str
    pipeline_id: str
    pipeline_name: str
    profile_name: str
    fingerprint: str
    logical_graph: LogicalGraph
    selected_nodes: tuple[str, ...] | None
    inventory: AdaptiveInventory
    candidates: tuple[CandidateRecord, ...]
    decisions: tuple[AdaptiveDecision, ...]
    objective: tuple[int | str, ...]
    regions: tuple[AdaptiveRegion, ...]
    physical_dag: PhysicalDAG
    protocol_versions: Mapping[str, str]
    profile_snapshot: Mapping[str, Any] = field(default_factory=dict)
    security_domain: str = "default"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def compile(
        self,
        *,
        target: str = "airflow",
        profile: Any = None,
        plugin: Any = None,
        **kwargs: Any,
    ) -> Any:
        """Reject external compilation until a consumer advertises ``/2``."""
        del target, profile, plugin, kwargs
        raise ValueError(
            "PMADP500: external compilation does not advertise adaptive "
            "etlantic.plan/2 and etlantic.physical_unit/1 support"
        )

    def __post_init__(self) -> None:
        if self.schema != ADAPTIVE_PLAN_SCHEMA:
            raise ValueError(
                f"PMADP400: adaptive plan schema must be {ADAPTIVE_PLAN_SCHEMA!r}"
            )
        for name in (
            "plan_id",
            "pipeline_id",
            "pipeline_name",
            "profile_name",
            "security_domain",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"PMADP400: adaptive plan {name} is required")
        # An empty string is used transiently while constructing the content
        # fingerprint; deserialized/wire plans are required to carry a value.
        if not isinstance(self.fingerprint, str):
            raise ValueError("PMADP400: adaptive plan fingerprint must be a string")
        if not isinstance(self.logical_graph, LogicalGraph):
            raise ValueError("PMADP400: adaptive plan logical_graph is required")
        node_order = tuple(self.logical_graph.node_names())
        node_names = set(node_order)
        if self.selected_nodes is not None:
            selected_tuple = _validated_array(
                self.selected_nodes, "adaptive plan selected_nodes", code="PMADP403"
            )
            if any(
                not isinstance(node, str) or not node.strip() for node in selected_tuple
            ):
                raise ValueError("PMADP403: selected_nodes must contain node names")
            if not selected_tuple or len(set(selected_tuple)) != len(selected_tuple):
                raise ValueError(
                    "PMADP403: selected_nodes must be null or non-empty and unique"
                )
            if not set(selected_tuple) <= node_names:
                raise ValueError(
                    "PMADP403: selected_nodes references an unknown logical node"
                )
            if set(selected_tuple) != node_names:
                raise ValueError(
                    "PMADP403: logical_graph must be the selected scope slice"
                )
            if selected_tuple != tuple(
                node for node in node_order if node in set(selected_tuple)
            ):
                raise ValueError(
                    "PMADP403: selected_nodes order must match the logical graph"
                )
        else:
            selected_tuple = node_order
        selected = set(selected_tuple)
        inventory = (
            self.inventory
            if isinstance(self.inventory, AdaptiveInventory)
            else AdaptiveInventory.from_dict(self.inventory)
        )
        target_ids = set(inventory.eligible_target_order)
        targets_by_id = {target.target_id: target for target in inventory.targets}
        target_identities = {target.identity for target in inventory.targets}
        candidates = _validated_array(self.candidates, "adaptive plan candidates")
        candidates = tuple(
            candidate
            if isinstance(candidate, CandidateRecord)
            else CandidateRecord.from_dict(candidate)
            for candidate in self.candidates
        )
        candidate_ids = [candidate.candidate_id for candidate in candidates]
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("PMADP220: candidate ids must be unique")
        actual_pairs = [
            (candidate.node_name, candidate.target_id) for candidate in candidates
        ]
        expected_pairs = [
            (node, target)
            for node in selected_tuple
            for target in inventory.eligible_target_order
        ]
        if (
            len(actual_pairs) != len(expected_pairs)
            or len(set(actual_pairs)) != len(actual_pairs)
            or set(actual_pairs) != set(expected_pairs)
        ):
            raise ValueError("PMADP220: candidate matrix is incomplete or duplicated")
        candidate_by_pair = {
            (candidate.node_name, candidate.target_id): candidate
            for candidate in candidates
        }
        candidates = tuple(candidate_by_pair[pair] for pair in expected_pairs)
        candidate_map = {candidate.candidate_id: candidate for candidate in candidates}
        decisions = _validated_array(self.decisions, "adaptive plan decisions")
        decisions = tuple(
            decision
            if isinstance(decision, AdaptiveDecision)
            else AdaptiveDecision.from_dict(decision)
            for decision in self.decisions
        )
        decision_nodes = [decision.node_name for decision in decisions]
        if set(decision_nodes) != selected or len(decision_nodes) != len(selected):
            raise ValueError(
                "PMADP320: decisions must select exactly one candidate per node"
            )
        decisions_by_node = {decision.node_name: decision for decision in decisions}
        decisions = tuple(decisions_by_node[node] for node in selected_tuple)
        for decision in decisions:
            candidate = candidate_map.get(decision.candidate_id)
            if (
                candidate is None
                or candidate.node_name != decision.node_name
                or candidate.target_id != decision.target_id
                or candidate.status != "eligible"
            ):
                raise ValueError(
                    f"PMADP220: decision {decision.node_name!r} references an invalid candidate"
                )
        regions = _validated_array(self.regions, "adaptive plan regions")
        regions = tuple(
            region
            if isinstance(region, AdaptiveRegion)
            else AdaptiveRegion.from_dict(region)
            for region in self.regions
        )
        region_nodes = [node for region in regions for node in region.logical_nodes]
        if set(region_nodes) != selected or len(region_nodes) != len(set(region_nodes)):
            raise ValueError(
                "PMADP403: regions must partition selected logical nodes exactly"
            )
        for region in regions:
            if region.target_id not in target_ids:
                raise ValueError(
                    "PMADP403: adaptive region references unknown target "
                    f"{region.target_id!r}"
                )
            if any(
                decisions_by_node[node].target_id != region.target_id
                for node in region.logical_nodes
            ):
                raise ValueError(
                    "PMADP403: adaptive region target must match each node decision"
                )
        dag = (
            self.physical_dag
            if isinstance(self.physical_dag, PhysicalDAG)
            else PhysicalDAG.from_dict(self.physical_dag)
        )
        if set(dag.logical_to_physical) != selected:
            raise ValueError(
                "PMADP403: physical DAG coverage must match selected nodes"
            )
        # The 0.51 wire foundation admitted incomplete hand-built topologies.
        # Generation completeness belongs to the versioned planner contract,
        # not to the historical /2 schema itself.
        metadata = _validated_metadata(self.metadata, "adaptive plan metadata")
        if metadata.get("etlantic.planner_version") == "0.52":
            dag.validate_logical_paths(
                tuple(
                    (
                        edge.producer_node,
                        edge.consumer_node,
                        edge.producer_port,
                        edge.consumer_port,
                    )
                    for edge in self.logical_graph.edges
                )
            )
            dag.validate_generated_envelope()
        units_by_id = {unit.identity: unit for unit in dag.units}
        for unit in dag.units:
            if unit.target_identity not in target_identities:
                raise ValueError(
                    "PMADP403: physical unit references unknown target identity "
                    f"{unit.target_identity!r}"
                )
        for node, unit_id in dag.logical_to_physical.items():
            unit = units_by_id[unit_id]
            decision = decisions_by_node[node]
            expected_identity = targets_by_id[decision.target_id].identity
            if unit.target_identity != expected_identity:
                raise ValueError(
                    "PMADP403: physical compute unit target must match node decision"
                )
        protocol_versions = _validated_string_map(
            self.protocol_versions, "adaptive plan protocol_versions"
        )
        if not protocol_versions:
            raise ValueError("PMADP201: adaptive plan protocol_versions are required")
        unknown_protocol_versions = sorted(
            set(protocol_versions) - {"plan", "physical_unit"}
        )
        if unknown_protocol_versions:
            raise ValueError(
                "PMADP400: unknown adaptive plan protocol_versions field(s): "
                + ", ".join(unknown_protocol_versions)
            )
        if protocol_versions.get("plan") != ADAPTIVE_PLAN_SCHEMA:
            raise ValueError(
                "PMADP400: adaptive plan protocol_versions.plan must be "
                f"{ADAPTIVE_PLAN_SCHEMA!r}"
            )
        if protocol_versions.get("physical_unit") != PHYSICAL_UNIT_SCHEMA:
            raise ValueError(
                "PMADP400: adaptive plan protocol_versions.physical_unit must be "
                f"{PHYSICAL_UNIT_SCHEMA!r}"
            )
        if isinstance(self.objective, (str, bytes)) or not isinstance(
            self.objective, (list, tuple)
        ):
            raise ValueError("PMADP321: adaptive plan objective must be an array")
        objective = tuple(self.objective)
        if any(
            type(value) is not int and not isinstance(value, str) for value in objective
        ):
            raise ValueError(
                "PMADP321: adaptive plan objective must be integer/string values"
            )
        profile_snapshot = _validated_json_mapping(
            self.profile_snapshot, "adaptive plan profile_snapshot"
        )
        metadata = _validated_metadata(self.metadata, "adaptive plan metadata")
        object.__setattr__(
            self,
            "selected_nodes",
            None if self.selected_nodes is None else selected_tuple,
        )
        object.__setattr__(self, "inventory", inventory)
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(self, "decisions", decisions)
        object.__setattr__(self, "regions", regions)
        object.__setattr__(self, "physical_dag", dag)
        object.__setattr__(self, "objective", objective)
        object.__setattr__(self, "protocol_versions", deep_freeze(protocol_versions))
        object.__setattr__(self, "profile_snapshot", deep_freeze(profile_snapshot))
        object.__setattr__(self, "metadata", deep_freeze(metadata))
        _reject_wire_sensitive_material(self.to_dict(), path="adaptive plan")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "plan_id": self.plan_id,
            "pipeline_id": self.pipeline_id,
            "pipeline_name": self.pipeline_name,
            "profile_name": self.profile_name,
            "fingerprint": self.fingerprint,
            "logical_graph": _graph_to_dict(self.logical_graph),
            "selected_nodes": list(self.selected_nodes)
            if self.selected_nodes is not None
            else None,
            "inventory": self.inventory.to_dict(),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "decisions": [decision.to_dict() for decision in self.decisions],
            "objective": list(self.objective),
            "regions": [region.to_dict() for region in self.regions],
            "physical_dag": self.physical_dag.to_dict(),
            "protocol_versions": mutable_copy(self.protocol_versions),
            "profile_snapshot": mutable_copy(self.profile_snapshot),
            "security_domain": self.security_domain,
            "metadata": mutable_copy(self.metadata),
        }

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any], *, verify: bool = True
    ) -> AdaptivePipelinePlan:
        from etlantic.plan.model import _graph_from_dict

        required = {
            "schema",
            "plan_id",
            "pipeline_id",
            "pipeline_name",
            "profile_name",
            "fingerprint",
            "logical_graph",
            "selected_nodes",
            "inventory",
            "candidates",
            "decisions",
            "objective",
            "regions",
            "physical_dag",
            "protocol_versions",
            "profile_snapshot",
            "security_domain",
            "metadata",
        }
        _reject_unknown(data, required, "adaptive plan")
        _require_fields(data, required, "adaptive plan")
        if data.get("schema") != ADAPTIVE_PLAN_SCHEMA:
            raise ValueError(
                f"PMADP400: unsupported adaptive plan schema {data.get('schema')!r}"
            )
        if not isinstance(data["fingerprint"], str) or not data["fingerprint"].strip():
            raise ValueError("PMADP400: adaptive plan fingerprint is required")
        plan = cls(
            schema=ADAPTIVE_PLAN_SCHEMA,
            plan_id=data["plan_id"],
            pipeline_id=data["pipeline_id"],
            pipeline_name=data["pipeline_name"],
            profile_name=data["profile_name"],
            fingerprint=data["fingerprint"],
            logical_graph=_graph_from_dict(data["logical_graph"]),
            selected_nodes=data["selected_nodes"],
            inventory=AdaptiveInventory.from_dict(data["inventory"]),
            candidates=data["candidates"],
            decisions=data["decisions"],
            objective=data["objective"],
            regions=data["regions"],
            physical_dag=PhysicalDAG.from_dict(data["physical_dag"]),
            protocol_versions=data["protocol_versions"],
            profile_snapshot=data["profile_snapshot"],
            security_domain=data["security_domain"],
            metadata=data["metadata"],
        )
        if verify:
            from etlantic.plan.adaptive_serialize import verify_adaptive_fingerprint

            verify_adaptive_fingerprint(plan)
        return plan


def _graph_to_dict(graph: LogicalGraph) -> dict[str, Any]:
    from etlantic.plan.model import _graph_to_dict as serialize_graph

    return serialize_graph(graph)


def _reject_unknown(data: Mapping[str, Any], allowed: set[str], label: str) -> None:
    if not isinstance(data, Mapping):
        raise ValueError(f"PMADP400: {label} must be an object")
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ValueError(f"PMADP400: unknown {label} field(s): {', '.join(unknown)}")


def _require_fields(data: Mapping[str, Any], required: set[str], label: str) -> None:
    missing = sorted(required - set(data))
    if missing:
        raise ValueError(f"PMADP400: {label} is missing field(s): {', '.join(missing)}")


def _validated_array(
    value: Any, label: str, *, code: str = "PMADP400"
) -> tuple[Any, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{code}: {label} must be an array")
    return tuple(value)


def _reject_wire_sensitive_material(value: Any, *, path: str) -> None:
    from etlantic.extensions import (
        _reject_nested_secret_material,
        _reject_nested_source_row_material,
    )

    try:
        _reject_nested_secret_material(value, path=path)
        _reject_nested_source_row_material(value, path=path)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"PMADP101: invalid {path}: {exc}") from exc


def _validated_string_map(value: Mapping[str, str], label: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError(f"PMADP400: {label} must be an object")
    result = dict(value)
    if any(
        not isinstance(key, str)
        or not key.strip()
        or not isinstance(item, str)
        or not item.strip()
        for key, item in result.items()
    ):
        raise ValueError(f"PMADP400: {label} must map non-blank strings to strings")
    return result


def _validated_integer_map(value: Mapping[str, int], label: str) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise ValueError(f"PMADP321: {label} must be an object")
    result = dict(value)
    if any(not isinstance(key, str) or not key.strip() for key in result):
        raise ValueError(f"PMADP321: {label} keys must be non-blank strings")
    return result


def _validated_json_mapping(value: Mapping[str, Any], label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"PMADP101: {label} must be an object")
    result = dict(value)
    try:
        json.dumps(mutable_copy(result), separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"PMADP101: {label} must be JSON-serializable") from exc
    return result


def _validated_metadata(value: Mapping[str, Any], label: str) -> dict[str, Any]:
    result = _validated_json_mapping(value, label)
    from etlantic.extensions import validate_extension_metadata

    try:
        validate_extension_metadata(result, path=label, strict=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"PMADP101: invalid {label}: {exc}") from exc
    return result


PlanDocument: TypeAlias = AdaptivePipelinePlan | PipelinePlan
