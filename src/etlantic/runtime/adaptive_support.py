"""The deliberately small 0.53 adaptive execution support matrix."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from etlantic.plan.adaptive_model import AdaptivePipelinePlan
from etlantic.plan.physical import PhysicalUnitKind

SUPPORT_SCHEMA = "etlantic.adaptive_support/1"
SUPPORT_MATURITY = "Experimental"
SUPPORTED_PATTERNS = frozenset(
    {"chain/1", "diamond/1", "fanout/1", "dual-port-chain/1"}
)


@dataclass(frozen=True, slots=True)
class SupportRow:
    row_id: str
    pattern: str
    target_families: tuple[str, ...]
    version_requirements: Mapping[str, str]
    unit_kinds: tuple[str, ...]
    contract_profiles: tuple[str, ...]
    io_families: tuple[str, ...]
    policy_modes: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    maturity: str = SUPPORT_MATURITY

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SUPPORT_SCHEMA,
            "row_id": self.row_id,
            "pattern": self.pattern,
            "target_families": list(self.target_families),
            "version_requirements": dict(self.version_requirements),
            "unit_kinds": list(self.unit_kinds),
            "contract_profiles": list(self.contract_profiles),
            "io_families": list(self.io_families),
            "policy_modes": list(self.policy_modes),
            "evidence_refs": list(self.evidence_refs),
            "maturity": self.maturity,
        }


def _pattern(plan: AdaptivePipelinePlan) -> str:
    graph = plan.logical_graph
    nodes = {node.name: node for node in graph.nodes}
    indegree = {name: 0 for name in nodes}
    outdegree = {name: 0 for name in nodes}
    for edge in graph.edges:
        indegree[edge.consumer_node] += 1
        outdegree[edge.producer_node] += 1
    sources = [name for name, value in indegree.items() if value == 0]
    sinks = [name for name, value in outdegree.items() if value == 0]
    if len(sources) != 1:
        return "unknown/1"
    source_kinds = {nodes[name].kind.value for name in sources}
    sink_kinds = {nodes[name].kind.value for name in sinks}
    if (
        len(sinks) == 1
        and source_kinds == {"source"}
        and sink_kinds == {"sink"}
        and len(graph.edges) == max(0, len(nodes) - 1)
        and all(value <= 1 for value in indegree.values())
        and all(value <= 1 for value in outdegree.values())
    ):
        return "chain/1"
    # A diamond is exactly source -> two branches -> join -> sink.
    if (
        len(nodes) == 5
        and len(sinks) == 1
        and source_kinds == {"source"}
        and sink_kinds == {"sink"}
        and len(graph.edges) == 6
        and sum(v == 2 for v in indegree.values()) == 1
        and sum(v == 2 for v in outdegree.values()) == 1
        and sum(v == 0 for v in indegree.values()) == 1
        and sum(v == 0 for v in outdegree.values()) == 1
    ):
        return "diamond/1"
    # A fanout has a shared source-side step and two independent leaf steps,
    # each terminating in its own sink (six logical nodes total).
    if (
        len(nodes) == 6
        and len(sinks) == 2
        and source_kinds == {"source"}
        and sink_kinds == {"sink"}
        and len(graph.edges) == 5
        and sum(v == 2 for v in outdegree.values()) == 1
        and sum(v == 1 for v in indegree.values()) == 5
        and sum(v == 0 for v in indegree.values()) == 1
    ):
        return "fanout/1"
    # A two-port boundary is distinguishable from an arbitrary two-input join.
    if (
        len(nodes) == 4
        and len(sinks) == 1
        and source_kinds == {"source"}
        and sink_kinds == {"sink"}
        and len(graph.edges) == 4
        and sum(len(node.outputs) == 2 for node in nodes.values()) == 1
        and sum(len(node.inputs) == 2 for node in nodes.values()) == 1
        and sorted(outdegree.values()) == [0, 1, 1, 2]
        and sorted(indegree.values()) == [0, 1, 1, 2]
    ):
        return "dual-port-chain/1"
    return "unknown/1"


def _target_family(plan: AdaptivePipelinePlan) -> tuple[str, ...]:
    by_id = {target.target_id: target for target in plan.inventory.targets}
    ordered: list[str] = []
    for identity in plan.inventory.eligible_target_order:
        target = by_id.get(identity)
        if target is not None:
            ordered.append(target.engine)
    return tuple(ordered)


def topology_fingerprint(plan: AdaptivePipelinePlan) -> str:
    graph = plan.logical_graph
    payload = {
        "pattern": _pattern(plan),
        "nodes": [
            (node.kind.value, len(node.inputs), len(node.outputs))
            for node in graph.nodes
        ],
        "edges": [(edge.producer_port, edge.consumer_port) for edge in graph.edges],
        "targets": _target_family(plan),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def support_row_for(plan: AdaptivePipelinePlan) -> SupportRow | None:
    pattern = _pattern(plan)
    if pattern not in SUPPORTED_PATTERNS:
        return None
    families: tuple[str, ...] = _target_family(plan)
    if not families or len(families) > 2:
        return None
    if any(target.location != "local" for target in plan.inventory.targets):
        return None
    first_family = next(iter(families), "")
    if len(set(families)) == 1 and first_family not in {"local", "polars", "pandas"}:
        return None
    if len(families) == 2 and tuple(families) not in {
        ("polars", "pandas"),
        ("pandas", "polars"),
    }:
        return None
    if pattern == "dual-port-chain/1" and len(families) != 2:
        return None
    if pattern in {"diamond/1", "fanout/1"} and len(families) != 1:
        return None
    kinds = tuple(kind.value for kind in PhysicalUnitKind)
    return SupportRow(
        row_id=f"local-static:{pattern}:{'-'.join(families)}",
        pattern=pattern,
        target_families=families,
        version_requirements={
            "plan": "etlantic.plan/2",
            "physical_unit": "etlantic.physical_unit/1",
        },
        unit_kinds=kinds,
        contract_profiles=("etlantic.contract/1",),
        io_families=("memory", "json", "csv", "null"),
        policy_modes=("standard", "validate", "overwrite", "no_write"),
        evidence_refs=(f"sha256:{topology_fingerprint(plan)}",),
    )


def is_executable_plan(plan: Any) -> bool:
    return (
        isinstance(plan, AdaptivePipelinePlan)
        and dict(plan.metadata).get("etlantic.execution") == "local-static-batch/1"
        and support_row_for(plan) is not None
    )


__all__ = [
    "SUPPORT_SCHEMA",
    "SupportRow",
    "is_executable_plan",
    "support_row_for",
    "topology_fingerprint",
]
