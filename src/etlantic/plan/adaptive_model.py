"""Closed adaptive planning IR (schema ``etlantic.plan/2``).

This module contains representation and integrity checks only.  It deliberately
does not discover plugins, solve placement, or execute physical units.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias

from etlantic.model import LogicalGraph
from etlantic.plan.freeze import deep_freeze, mutable_copy
from etlantic.plan.model import PipelinePlan
from etlantic.plan.physical import PhysicalDAG

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
        if any(
            not isinstance(value, str) or not value.strip()
            for value in self.evidence_refs
        ):
            raise ValueError("PMADP202: evidence_refs must contain non-blank strings")
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))
        object.__setattr__(
            self, "protocol_versions", deep_freeze(dict(self.protocol_versions))
        )
        object.__setattr__(self, "metadata", deep_freeze(dict(self.metadata)))
        _reject_secret_material(self.to_dict())

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
            evidence_refs=tuple(data.get("evidence_refs", ())),
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
        targets = tuple(
            target
            if isinstance(target, TargetDescriptor)
            else TargetDescriptor.from_dict(target)
            for target in self.targets
        )
        target_ids = [target.target_id for target in targets]
        if len(set(target_ids)) != len(target_ids):
            raise ValueError("PMADP201: inventory target ids must be unique")
        order = tuple(self.eligible_target_order)
        if len(set(order)) != len(order) or set(order) != set(target_ids):
            raise ValueError(
                "PMADP201: inventory eligible order must cover every target once"
            )
        object.__setattr__(self, "targets", targets)
        object.__setattr__(self, "eligible_target_order", order)
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))

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
            targets=tuple(
                TargetDescriptor.from_dict(item) for item in data.get("targets", ())
            ),
            eligible_target_order=tuple(data.get("eligible_target_order", ())),
            fingerprint=data.get("fingerprint", ""),
            evidence_refs=tuple(data.get("evidence_refs", ())),
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
        if self.kind not in {"source", "sink", "compute"}:
            raise ValueError(f"PMADP220: unknown candidate kind {self.kind!r}")
        if self.status not in {"eligible", "rejected"}:
            raise ValueError(f"PMADP220: unknown candidate status {self.status!r}")
        if not self.reason_codes and self.status == "rejected":
            raise ValueError("PMADP221: rejected candidate requires reason_codes")
        if self.status == "eligible" and self.reason_codes:
            raise ValueError(
                "PMADP220: eligible candidate cannot contain rejection reasons"
            )
        if any(not isinstance(value, int) for value in self.objective_facts.values()):
            raise ValueError("PMADP321: candidate objective facts must be integers")
        for name in ("reason_codes", "evidence_refs"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        object.__setattr__(
            self, "objective_facts", deep_freeze(dict(self.objective_facts))
        )
        object.__setattr__(self, "metadata", deep_freeze(dict(self.metadata)))
        _reject_secret_material(self.to_dict())

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
            reason_codes=tuple(data.get("reason_codes", ())),
            evidence_refs=tuple(data.get("evidence_refs", ())),
            objective_facts=data.get("objective_facts", {}),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True, slots=True)
class AdaptiveDecision:
    """Selected candidate reference for one selected logical node."""

    node_name: str
    candidate_id: str
    target_id: str

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
        nodes = tuple(self.logical_nodes)
        if not nodes or len(set(nodes)) != len(nodes):
            raise ValueError("PMADP403: adaptive regions require unique logical nodes")
        if len(set(self.dependencies)) != len(self.dependencies):
            raise ValueError("PMADP402: adaptive region dependencies must be unique")
        object.__setattr__(self, "logical_nodes", nodes)
        object.__setattr__(self, "dependencies", tuple(self.dependencies))
        object.__setattr__(self, "metadata", deep_freeze(dict(self.metadata)))

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
            logical_nodes=tuple(data.get("logical_nodes", ())),
            dependencies=tuple(data.get("dependencies", ())),
            fused=bool(data.get("fused", False)),
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
        node_names = set(self.logical_graph.node_names())
        selected = (
            node_names if self.selected_nodes is None else set(self.selected_nodes)
        )
        if self.selected_nodes is not None:
            if not self.selected_nodes or len(set(self.selected_nodes)) != len(
                self.selected_nodes
            ):
                raise ValueError(
                    "PMADP403: selected_nodes must be null or non-empty and unique"
                )
            if not selected <= node_names:
                raise ValueError(
                    "PMADP403: selected_nodes references an unknown logical node"
                )
        candidates = tuple(
            candidate
            if isinstance(candidate, CandidateRecord)
            else CandidateRecord.from_dict(candidate)
            for candidate in self.candidates
        )
        keys = {(candidate.node_name, candidate.target_id) for candidate in candidates}
        expected = {
            (node, target)
            for node in selected
            for target in self.inventory.eligible_target_order
        }
        if keys != expected or len(keys) != len(candidates):
            raise ValueError("PMADP220: candidate matrix is incomplete or duplicated")
        candidate_map = {candidate.candidate_id: candidate for candidate in candidates}
        decisions = tuple(
            decision
            if isinstance(decision, AdaptiveDecision)
            else AdaptiveDecision.from_dict(decision)
            for decision in self.decisions
        )
        if {decision.node_name for decision in decisions} != selected or len(
            decisions
        ) != len(selected):
            raise ValueError(
                "PMADP320: decisions must select exactly one candidate per node"
            )
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
        dag = (
            self.physical_dag
            if isinstance(self.physical_dag, PhysicalDAG)
            else PhysicalDAG.from_dict(self.physical_dag)
        )
        if set(dag.logical_to_physical) != selected:
            raise ValueError(
                "PMADP403: physical DAG coverage must match selected nodes"
            )
        if (
            not isinstance(self.protocol_versions, Mapping)
            or not self.protocol_versions
        ):
            raise ValueError("PMADP201: adaptive plan protocol_versions are required")
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(self, "decisions", decisions)
        object.__setattr__(self, "regions", regions)
        object.__setattr__(self, "physical_dag", dag)
        object.__setattr__(
            self, "protocol_versions", deep_freeze(dict(self.protocol_versions))
        )
        object.__setattr__(
            self, "profile_snapshot", deep_freeze(dict(self.profile_snapshot))
        )
        object.__setattr__(self, "metadata", deep_freeze(dict(self.metadata)))
        _reject_secret_material(self.to_dict())

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
        plan = cls(
            schema=ADAPTIVE_PLAN_SCHEMA,
            plan_id=data["plan_id"],
            pipeline_id=data["pipeline_id"],
            pipeline_name=data["pipeline_name"],
            profile_name=data["profile_name"],
            fingerprint=data["fingerprint"],
            logical_graph=_graph_from_dict(data["logical_graph"]),
            selected_nodes=(
                tuple(data["selected_nodes"])
                if data["selected_nodes"] is not None
                else None
            ),
            inventory=AdaptiveInventory.from_dict(data["inventory"]),
            candidates=tuple(
                CandidateRecord.from_dict(item) for item in data["candidates"]
            ),
            decisions=tuple(
                AdaptiveDecision.from_dict(item) for item in data["decisions"]
            ),
            objective=tuple(data["objective"]),
            regions=tuple(AdaptiveRegion.from_dict(item) for item in data["regions"]),
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


def _reject_secret_material(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            lowered = str(key).lower()
            if any(
                token in lowered
                for token in (
                    "password",
                    "passwd",
                    "secret_value",
                    "token",
                    "api_key",
                    "credential",
                )
            ):
                raise ValueError(
                    f"PMADP101: adaptive plan contains secret-like field {key!r}"
                )
            _reject_secret_material(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _reject_secret_material(child)


PlanDocument: TypeAlias = AdaptivePipelinePlan | PipelinePlan
