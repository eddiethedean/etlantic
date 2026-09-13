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


def qualification_bundle() -> tuple[dict[str, Any], str]:
    """Read packaged support data independent from submitted plans/reports."""
    from importlib.resources import files

    raw = files("etlantic.runtime").joinpath("adaptive_support.json").read_bytes()
    # Git checkouts may translate newlines without changing qualified content.
    raw = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    bundle = json.loads(raw)
    if (
        set(bundle) != {"schema", "maturity", "rows", "observations"}
        or bundle["schema"] != "etlantic.adaptive_qualification/1"
        or bundle["maturity"] != SUPPORT_MATURITY
    ):
        raise ValueError("Packaged adaptive qualification schema is invalid")
    observations = bundle["observations"]
    if not observations or any(
        set(case) != {"id", "result"} or case["result"] != "pass"
        for case in observations
    ):
        raise ValueError("Packaged adaptive qualification lacks passing observations")
    evidence = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(observations, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )
    for row in bundle["rows"].values():
        if set(row) != {"versions", "operations", "policies", "evidence_refs"} or row[
            "evidence_refs"
        ] != [evidence]:
            raise ValueError("Packaged adaptive qualification evidence drifted")
    return bundle, "sha256:" + hashlib.sha256(raw).hexdigest()


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
    nodes = graph.node_map()
    incoming = {name: [] for name in nodes}
    outgoing = {name: [] for name in nodes}
    for edge in graph.edges:
        outgoing[edge.producer_node].append(edge)
        incoming[edge.consumer_node].append(edge)
    roots = [name for name in nodes if not incoming[name]]
    if len(roots) != 1 or nodes[roots[0]].kind.value != "source":
        return "unknown/1"
    root = roots[0]
    if any(
        node.kind.value not in {"source", "step", "sink"} for node in nodes.values()
    ):
        return "unknown/1"
    if sum(node.kind.value == "source" for node in nodes.values()) != 1:
        return "unknown/1"
    if all(len(incoming[n]) <= 1 and len(outgoing[n]) <= 1 for n in nodes):
        current = root
        visited = set()
        while current not in visited:
            visited.add(current)
            if nodes[current].kind.value == "sink" and outgoing[current]:
                break
            if not outgoing[current]:
                return "chain/1" if visited == set(nodes) else "unknown/1"
            current = outgoing[current][0].consumer_node
        return "unknown/1"
    if len(nodes) == 5 and len(outgoing[root]) == 2:
        branches = [edge.consumer_node for edge in outgoing[root]]
        if len(set(branches)) == 2 and all(
            nodes[b].kind.value == "step"
            and len(incoming[b]) == 1
            and len(outgoing[b]) == 1
            for b in branches
        ):
            joins = [outgoing[b][0].consumer_node for b in branches]
            if joins[0] == joins[1]:
                join = joins[0]
                if (
                    nodes[join].kind.value == "step"
                    and len(incoming[join]) == 2
                    and len(outgoing[join]) == 1
                ):
                    sink = outgoing[join][0].consumer_node
                    if (
                        nodes[sink].kind.value == "sink"
                        and not outgoing[sink]
                        and len(incoming[sink]) == 1
                        and len(graph.edges) == 5
                    ):
                        return "diamond/1"
    if len(nodes) == 6 and len(outgoing[root]) == 1:
        shared = outgoing[root][0].consumer_node
        if (
            nodes[shared].kind.value == "step"
            and len(incoming[shared]) == 1
            and len(outgoing[shared]) == 2
        ):
            leaves = [edge.consumer_node for edge in outgoing[shared]]
            if len(set(leaves)) == 2 and all(
                nodes[n].kind.value == "step"
                and len(incoming[n]) == 1
                and len(outgoing[n]) == 1
                for n in leaves
            ):
                sinks = [outgoing[n][0].consumer_node for n in leaves]
                if (
                    len(set(sinks)) == 2
                    and all(
                        nodes[n].kind.value == "sink"
                        and len(incoming[n]) == 1
                        and not outgoing[n]
                        for n in sinks
                    )
                    and len(graph.edges) == 5
                ):
                    return "fanout/1"
    if len(nodes) == 4 and len(outgoing[root]) == 1:
        producer = outgoing[root][0].consumer_node
        routes = outgoing[producer]
        if (
            nodes[producer].kind.value == "step"
            and len(routes) == 2
            and len(nodes[producer].outputs) == 2
            and len(incoming[producer]) == 1
        ):
            consumer = routes[0].consumer_node
            if (
                routes[1].consumer_node == consumer
                and len({r.producer_port for r in routes}) == 2
                and len({r.consumer_port for r in routes}) == 2
                and len(nodes[consumer].inputs) == 2
                and nodes[consumer].kind.value == "step"
                and len(outgoing[consumer]) == 1
            ):
                sink = outgoing[consumer][0].consumer_node
                if (
                    nodes[sink].kind.value == "sink"
                    and not outgoing[sink]
                    and len(graph.edges) == 4
                ):
                    return "dual-port-chain/1"
    return "unknown/1"


def _target_family(plan: AdaptivePipelinePlan) -> tuple[str, ...]:
    by_id = {target.target_id: target for target in plan.inventory.targets}
    assignments = {
        decision.node_name: decision.target_id for decision in plan.decisions
    }
    segments = []
    for node in plan.logical_graph.nodes:
        target_id = assignments.get(node.name)
        if target_id is None or target_id not in by_id:
            return ()
        if not segments or segments[-1] != target_id:
            segments.append(target_id)
    return tuple(by_id[target_id].engine for target_id in segments)


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
    if any(
        unit.kind.value == "compute" and len(unit.logical_nodes) != 1
        for unit in plan.physical_dag.units
    ):
        return None
    families: tuple[str, ...] = _target_family(plan)
    if not families or len(families) > 2:
        return None
    if any(
        target.location != "local" or target.resource is not None
        for target in plan.inventory.targets
    ):
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
    bundle, bundle_digest = qualification_bundle()
    key = f"{pattern}:{'-'.join(families)}"
    qualified = bundle["rows"].get(key)
    if qualified is None:
        return None
    kinds = tuple(kind.value for kind in PhysicalUnitKind)
    return SupportRow(
        row_id=f"local-static:{pattern}:{'-'.join(families)}",
        pattern=pattern,
        target_families=families,
        version_requirements={
            "plan": "etlantic.plan/2",
            "physical_unit": "etlantic.physical_unit/1",
            **qualified["versions"],
        },
        unit_kinds=kinds,
        contract_profiles=("etlantic.contract/1",),
        io_families=("memory", "json", "csv", "null"),
        policy_modes=("standard", "validate", "overwrite", "no_write"),
        evidence_refs=(bundle_digest, *qualified["evidence_refs"]),
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
