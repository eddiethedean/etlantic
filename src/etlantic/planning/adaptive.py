"""Deterministic adaptive placement planner.

The adaptive planner is deliberately plan-only.  It consumes the canonical
logical graph and the profile's target descriptors, produces the closed
``etlantic.plan/2`` model, and never compiles or executes a transformation.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from typing import Any

from packaging.specifiers import InvalidSpecifier, SpecifierSet

from etlantic.diagnostics import Diagnostic, Severity, ValidationReport
from etlantic.exceptions import PipelineValidationError
from etlantic.model import LogicalGraph, NodeKind
from etlantic.plan.adaptive_model import (
    ADAPTIVE_LIMITS_VERSION,
    ADAPTIVE_PLAN_SCHEMA,
    AdaptiveDecision,
    AdaptiveInventory,
    AdaptivePipelinePlan,
    AdaptiveRegion,
    CandidateRecord,
    TargetDescriptor,
)
from etlantic.plan.adaptive_serialize import adaptive_plan_fingerprint
from etlantic.plan.physical import (
    PHYSICAL_UNIT_SCHEMA,
    PhysicalDAG,
    PhysicalDependency,
    PhysicalUnit,
    PhysicalUnitKind,
)
from etlantic.plan.slicing import (
    dependency_closure,
    run_one_selection,
    run_until_selection,
    slice_graph,
)
from etlantic.registry import PlanningContext

MAX_NODES = 256
MAX_TARGETS = 8
MAX_CANDIDATES = 2048
MAX_EVIDENCE = 8
MAX_SOLVER_EXPANSIONS = 1_000_000
ORACLE_MAX_NODES = 8
ORACLE_MAX_TARGETS = 4
ORACLE_MAX_ASSIGNMENTS = 65_536
MAX_TRANSIENT_BYTES = 256 * 1024 * 1024


def build_adaptive_plan(
    pipeline_cls: type[Any] | None,
    context: PlanningContext,
    *,
    selection: dict[str, Any] | None = None,
    definition: Any | None = None,
) -> AdaptivePipelinePlan | Any:
    """Build an adaptive plan, or the explicitly configured fallback plan."""
    graph = _graph_for_input(pipeline_cls, definition)
    selected = _select_graph(graph, selection or context.selection)
    _validate_scope(selected)
    targets = _inventory(context)
    unknown_overrides = sorted(
        set(context.profile.implementation_overrides.values())
        - {target_id for target_id, _, _ in targets}
    )
    if unknown_overrides:
        raise _error(
            "PMADP121",
            f"Unknown adaptive target override(s): {', '.join(unknown_overrides)}.",
            path=("profile", "implementation_overrides"),
        )
    candidates = _candidate_matrix(selected, targets, context, pipeline_cls, definition)
    viable = {
        node.name: [
            c for c in candidates if c.node_name == node.name and c.status == "eligible"
        ]
        for node in selected.nodes
    }
    missing = [node for node, cells in viable.items() if not cells]
    if missing:
        error = _error(
            "PMADP320",
            f"No viable adaptive target for node(s): {', '.join(missing)}.",
            path=("adaptive", "candidates"),
        )
        if context.profile.adaptive_fallback == "explicit":
            return _explicit_fallback(
                pipeline_cls,
                context,
                selected,
                selection=selection,
                definition=definition,
                report=error.report,
            )
        raise error

    decisions = _solve(selected, candidates, targets, context)
    _check_oracle(selected, candidates, targets, decisions)
    regions = _regions(selected, decisions, targets, context)
    physical = _physical_dag(selected, decisions, targets, regions)
    inventory = _inventory_model(targets)
    objective = _objective(selected, decisions, candidates, inventory)

    profile = context.profile
    metadata = {
        "etlantic.planner": "etlantic.planning.adaptive",
        "etlantic.planner_version": "0.52",
        "etlantic.objective_version": "etlantic.adaptive-objective/1",
        "etlantic.limits_version": ADAPTIVE_LIMITS_VERSION,
        "etlantic.solver": "deterministic-lexicographic/1",
        "etlantic.execution": "planning-only",
        "etlantic.selected-node-count": len(selected.nodes),
        "etlantic.candidate-count": len(candidates),
        "etlantic.objective": list(objective),
    }
    selected_nodes = (
        None if not (selection or context.selection) else selected.node_names()
    )
    plan = AdaptivePipelinePlan(
        schema=ADAPTIVE_PLAN_SCHEMA,
        plan_id="plan:pending",
        pipeline_id=selected.pipeline_id,
        pipeline_name=selected.pipeline_name,
        profile_name=profile.name,
        fingerprint="",
        logical_graph=selected,
        selected_nodes=selected_nodes,
        inventory=inventory,
        candidates=tuple(candidates),
        decisions=tuple(decisions),
        objective=objective,
        regions=tuple(regions),
        physical_dag=physical,
        protocol_versions={
            "plan": ADAPTIVE_PLAN_SCHEMA,
            "physical_unit": PHYSICAL_UNIT_SCHEMA,
        },
        profile_snapshot=profile.to_plan_snapshot(),
        security_domain=profile.security_domain,
        metadata=metadata,
    )
    fingerprint = adaptive_plan_fingerprint(plan)
    return replace(plan, fingerprint=fingerprint, plan_id=f"plan:{fingerprint[:16]}")


def _graph_for_input(
    pipeline_cls: type[Any] | None, definition: Any | None
) -> LogicalGraph:
    if definition is not None:
        from etlantic.authoring.normalize import logical_graph_from_definition

        return logical_graph_from_definition(definition)
    if pipeline_cls is None:
        raise TypeError("pipeline_cls is required when definition is omitted")
    return pipeline_cls.build_graph()


def _select_graph(graph: LogicalGraph, selection: dict[str, Any]) -> LogicalGraph:
    if not selection:
        return graph
    try:
        if "run_one" in selection:
            selected = run_one_selection(graph, str(selection["run_one"]))
        elif "run_until" in selection:
            selected = run_until_selection(graph, str(selection["run_until"]))
        elif "nodes" in selection:
            selected = dependency_closure(graph, list(selection["nodes"]))
        else:
            selected = graph.node_names()
        if not selected:
            raise ValueError("Selection produced an empty graph.")
        return slice_graph(graph, selected)
    except ValueError as exc:
        raise _error("PMPLAN501", str(exc), path=("selection",)) from exc


def _validate_scope(graph: LogicalGraph) -> None:
    if len(graph.nodes) > MAX_NODES:
        raise _error(
            "PMADP300",
            f"Adaptive planning supports at most {MAX_NODES} selected nodes.",
            path=("logical_graph",),
        )
    unsupported = [
        node
        for node in graph.nodes
        if node.kind not in {NodeKind.SOURCE, NodeKind.STEP, NodeKind.SINK}
    ]
    if unsupported:
        raise _error(
            "PMADP502",
            f"Unsupported adaptive graph node kind {unsupported[0].kind.value!r}.",
            path=("logical_graph", unsupported[0].name),
        )


def _inventory(context: PlanningContext) -> tuple[tuple[str, Any, Any], ...]:
    profile = context.profile
    if len(profile.eligible_targets) > MAX_TARGETS:
        raise _error(
            "PMADP100",
            f"Adaptive planning supports at most {MAX_TARGETS} eligible targets.",
            path=("profile", "eligible_targets"),
        )
    result: list[tuple[str, Any, Any]] = []
    seen_identity: dict[str, str] = {}
    for target_id in profile.eligible_targets:
        target = profile.placement_targets[target_id]
        identity = target.identity()
        previous = seen_identity.get(identity)
        if previous is not None:
            raise _error(
                "PMADP201",
                f"Targets {previous!r} and {target_id!r} resolve to the same execution identity.",
                path=("profile", "placement_targets"),
            )
        seen_identity[identity] = target_id
        caps = context.registry.engines.get(target.engine)
        result.append((target_id, target, caps))
    return tuple(result)


def _inventory_model(targets: tuple[tuple[str, Any, Any], ...]) -> AdaptiveInventory:
    descriptors: list[TargetDescriptor] = []
    for target_id, target, caps in targets:
        capability_payload = caps.to_dict() if caps is not None else {}
        cap_fp = _digest(capability_payload)
        descriptor = TargetDescriptor(
            target_id=target_id,
            identity=target.identity(),
            engine=target.engine,
            compiler=target.compiler,
            executor=target.executor,
            connector=target.connector,
            resource=target.resource,
            location=target.location,
            security_domain=target.security_domain,
            protocol_versions={
                "plan": ADAPTIVE_PLAN_SCHEMA,
                "physical_unit": PHYSICAL_UNIT_SCHEMA,
            },
            capability_fingerprint=cap_fp,
            evidence_refs=(f"etlantic.target/{target_id}",),
            metadata={
                "etlantic.available": caps is not None,
                "etlantic.required_capabilities": list(target.required_capabilities),
                "etlantic.version_constraints": dict(target.version_constraints),
            },
        )
        descriptors.append(descriptor)
    payload = {
        "targets": [item.to_dict() for item in descriptors],
        "eligible_target_order": [x[0] for x in targets],
    }
    return AdaptiveInventory(
        targets=tuple(descriptors),
        eligible_target_order=tuple(x[0] for x in targets),
        fingerprint=_digest(payload),
        evidence_refs=tuple(ref for item in descriptors for ref in item.evidence_refs),
    )


def _candidate_matrix(
    graph: LogicalGraph,
    targets: tuple[tuple[str, Any, Any], ...],
    context: PlanningContext,
    pipeline_cls: type[Any] | None,
    definition: Any | None,
) -> tuple[CandidateRecord, ...]:
    if len(graph.nodes) * len(targets) > MAX_CANDIDATES:
        raise _error(
            "PMADP301",
            f"Adaptive candidate matrix exceeds {MAX_CANDIDATES} records.",
            path=("adaptive", "candidates"),
        )
    transform_map = _transform_map(pipeline_cls, definition)
    output: list[CandidateRecord] = []
    charged = 0
    overrides = context.profile.implementation_overrides
    for node in graph.nodes:
        for target_id, target, caps in targets:
            reasons: list[str] = []
            evidence_items = [
                f"etlantic.target/{target_id}",
                f"etlantic.capability/{target.engine}",
            ]
            if caps is None:
                reasons.append("PMADP200")
            reasons.extend(_version_rejection_codes(target, context))
            if target.security_domain not in {
                context.profile.security_domain,
                "default",
            }:
                reasons.append("PMADP124")
            unsupported_caps = [
                req
                for req in target.required_capabilities
                if caps is None
                or (
                    (req != "batch" or target.engine != "local")
                    and not caps.supports(req)
                )
            ]
            if unsupported_caps:
                reasons.append("PMADP123")
            override = overrides.get(node.name)
            if override is not None and override != target_id:
                reasons.append("PMADP122")
            if node.kind is NodeKind.STEP:
                portable = _portable_definition(node, transform_map)
                if (
                    portable is None
                    or context.profile.portable_transform_policy == "native"
                ):
                    reasons.append("PMADP120")
                elif (
                    target.engine != "local"
                    and f"{node.transformation_id}::{target.engine}"
                    not in context.registry.implementations
                ):
                    reasons.append("PMADP124")
            if node.kind is NodeKind.STEP:
                implementation = context.registry.implementations.get(
                    f"{node.transformation_id}::{target.engine}"
                )
                if implementation is not None:
                    evidence_items.extend(
                        ref
                        for ref in (
                            implementation.identity,
                            implementation.ir_fingerprint,
                            implementation.compiler_evidence_fingerprint,
                        )
                        if ref
                    )
                    if (
                        implementation.kind != "portable_compiled"
                        and target.engine != "local"
                    ):
                        reasons.append("PMADP120")
            evidence = _bounded_evidence(evidence_items)
            kind = "compute" if node.kind is NodeKind.STEP else node.kind.value
            candidate_id = _digest(
                {"node": node.name, "target": target_id, "identity": target.identity()}
            )[:24]
            record = CandidateRecord(
                candidate_id=f"candidate:{candidate_id}",
                node_name=node.name,
                target_id=target_id,
                kind=kind,
                status="eligible" if not reasons else "rejected",
                reason_codes=tuple(sorted(set(reasons))),
                evidence_refs=evidence,
                objective_facts=_objective_facts(
                    node, target, caps, context, transform_map
                ),
                metadata={
                    "etlantic.engine": target.engine,
                    "etlantic.version_constraints": dict(target.version_constraints),
                    "etlantic.required_capabilities": list(
                        target.required_capabilities
                    ),
                },
            )
            charged += (
                len(
                    json.dumps(
                        record.to_dict(),
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=False,
                    ).encode("utf-8")
                )
                + 64
            )
            if charged > MAX_TRANSIENT_BYTES:
                raise _error(
                    "PMADP303",
                    "Adaptive planner transient budget exceeded.",
                    path=("adaptive", "candidates"),
                )
            output.append(record)
    return tuple(output)


def _transform_map(
    pipeline_cls: type[Any] | None, definition: Any | None
) -> dict[str, Any]:
    if definition is not None:
        return {
            item.identity: item for item in getattr(definition, "transformations", ())
        }
    if pipeline_cls is None:
        return {}
    result: dict[str, Any] = {}
    for _name, member in getattr(pipeline_cls, "__pipeline_members__", {}).items():
        transform = getattr(member, "transformation", None)
        if transform is not None:
            identity = getattr(transform, "identity", None)
            if callable(identity):
                identity = identity()
            if identity:
                result[str(identity)] = transform
    return result


def _portable_definition(node: Any, transforms: dict[str, Any]) -> Any | None:
    transform = transforms.get(node.transformation_id)
    if transform is None:
        return None
    method = getattr(transform, "portable_definition", None)
    if not callable(method):
        return None
    try:
        return method()
    except Exception:
        return None


def _version_rejection_codes(target: Any, context: PlanningContext) -> list[str]:
    """Evaluate target constraints against static registry descriptors only."""
    rejected: list[str] = []
    for component, spec in target.version_constraints.items():
        try:
            requirement = SpecifierSet(str(spec))
        except InvalidSpecifier:
            rejected.append("PMADP101")
            continue
        component_ref = {
            "engine": target.engine,
            "compiler": target.compiler,
            "executor": target.executor,
            "connector": target.connector,
            "resource": target.resource,
        }.get(component, component)
        if component_ref is None:
            rejected.append("PMADP124")
            continue
        descriptor = context.registry.plugins.get(component_ref)
        if descriptor is None:
            # Component names may be engine/compiler/executor aliases.
            descriptor = next(
                (
                    item
                    for item in context.registry.plugins.values()
                    if item.engine == component_ref or item.name == component_ref
                ),
                None,
            )
        if descriptor is None or not requirement.contains(
            str(descriptor.version), prereleases=True
        ):
            rejected.append("PMADP124")
    return rejected


def _bounded_evidence(values: list[str]) -> tuple[str, ...]:
    """Canonicalize and cap evidence refs, retaining a deterministic marker."""
    ordered = sorted({str(value) for value in values if str(value).strip()})
    if len(ordered) <= MAX_EVIDENCE:
        return tuple(ordered)
    omitted = len(ordered) - (MAX_EVIDENCE - 1)
    return (
        *ordered[: MAX_EVIDENCE - 1],
        f"etlantic.evidence-truncated/1:omitted={omitted}",
    )


def _objective_facts(
    node: Any,
    target: Any,
    caps: Any,
    context: PlanningContext,
    transforms: dict[str, Any],
) -> dict[str, int]:
    metadata = dict(getattr(node, "metadata", {}) or {})
    facts = {
        "proven_local_io_nodes": int(
            node.kind in {NodeKind.SOURCE, NodeKind.SINK}
            and target.location == "local"
            and caps is not None
        ),
        "proven_pushdown_actions": 0,
        "collection_units": int(
            bool(metadata.get("etlantic.collection_required", False))
        ),
        "durable_materialization_units": int(
            bool(metadata.get("etlantic.materialization_required", False))
        ),
        "safely_fusible_logical_edges": 0,
    }
    if node.kind is NodeKind.STEP:
        transform = transforms.get(node.transformation_id)
        portable = _portable_definition(node, transforms)
        # Pushdown/fusion are positive claims only when an implementation
        # descriptor explicitly advertises them; absence remains conservative.
        implementation = context.registry.implementations.get(
            f"{node.transformation_id}::{target.engine}"
        )
        support = dict(getattr(implementation, "support_summary", {}) or {})
        if portable is not None and implementation is not None:
            facts["proven_pushdown_actions"] = int(
                bool(support.get("pushdown") or support.get("semantic_parity"))
            )
            facts["safely_fusible_logical_edges"] = int(
                bool(support.get("fusion") or support.get("fusible"))
            )
        del transform
    return facts


def _solve(
    graph: LogicalGraph,
    candidates: tuple[CandidateRecord, ...],
    targets: tuple[tuple[str, Any, Any], ...],
    context: PlanningContext,
) -> tuple[AdaptiveDecision, ...]:
    priority = {target_id: index for index, (target_id, _, _) in enumerate(targets)}
    by_node = {
        node.name: sorted(
            [
                c
                for c in candidates
                if c.node_name == node.name and c.status == "eligible"
            ],
            key=lambda c: (priority[c.target_id], c.target_id, c.candidate_id),
        )
        for node in graph.nodes
    }
    inventory = _inventory_model(targets)
    ordered_nodes = tuple(graph.node_names())
    best_score: tuple[int | str, ...] | None = None
    best: tuple[AdaptiveDecision, ...] | None = None
    expansions = 0

    def visit(index: int, chosen: list[CandidateRecord]) -> None:
        nonlocal best_score, best, expansions
        expansions += 1
        if expansions > MAX_SOLVER_EXPANSIONS:
            raise _error(
                "PMADP304",
                "Adaptive solver expansion limit exceeded.",
                path=("adaptive", "solver"),
            )
        if index == len(ordered_nodes):
            decisions = tuple(
                AdaptiveDecision(node, candidate.candidate_id, candidate.target_id)
                for node, candidate in zip(ordered_nodes, chosen, strict=True)
            )
            score = _objective(graph, decisions, candidates, inventory)
            if best_score is None or score < best_score:
                best_score, best = score, decisions
            return
        for candidate in by_node[ordered_nodes[index]]:
            chosen.append(candidate)
            visit(index + 1, chosen)
            chosen.pop()

    visit(0, [])
    assert best is not None
    return best


def _check_oracle(
    graph: LogicalGraph,
    candidates: tuple[CandidateRecord, ...],
    targets: tuple[tuple[str, Any, Any], ...],
    selected: tuple[AdaptiveDecision, ...],
) -> None:
    """Cross-check small plans with an independently written exhaustive oracle."""
    if len(graph.nodes) > ORACLE_MAX_NODES or len(targets) > ORACLE_MAX_TARGETS:
        return
    assignments = 1
    for node in graph.nodes:
        count = sum(
            candidate.status == "eligible"
            for candidate in candidates
            if candidate.node_name == node.name
        )
        assignments *= count
    if assignments > ORACLE_MAX_ASSIGNMENTS:
        return
    inventory = _inventory_model(targets)
    by_node = {
        node.name: tuple(
            candidate
            for candidate in candidates
            if candidate.node_name == node.name and candidate.status == "eligible"
        )
        for node in graph.nodes
    }
    best_score: tuple[int | str, ...] | None = None
    best_assignment: tuple[AdaptiveDecision, ...] | None = None

    def enumerate_assignments(index: int, chosen: list[CandidateRecord]) -> None:
        nonlocal best_score, best_assignment
        if index == len(graph.nodes):
            decisions = tuple(
                AdaptiveDecision(node.name, candidate.candidate_id, candidate.target_id)
                for node, candidate in zip(graph.nodes, chosen, strict=True)
            )
            score = _objective(graph, decisions, candidates, inventory)
            if best_score is None or (
                score,
                tuple(d.candidate_id for d in decisions),
            ) < (
                best_score,
                tuple(d.candidate_id for d in (best_assignment or ())),
            ):
                best_score = score
                best_assignment = decisions
            return
        for candidate in sorted(
            by_node[graph.nodes[index].name], key=lambda c: c.candidate_id
        ):
            chosen.append(candidate)
            enumerate_assignments(index + 1, chosen)
            chosen.pop()

    enumerate_assignments(0, [])
    if best_assignment is None or best_score is None:
        return
    selected_score = _objective(graph, selected, candidates, inventory)
    if selected_score != best_score or tuple(d.candidate_id for d in selected) != tuple(
        d.candidate_id for d in best_assignment
    ):
        raise _error(
            "PMADP306",
            "Adaptive solver disagrees with exhaustive oracle.",
            path=("adaptive", "solver"),
        )


def _objective(
    graph: LogicalGraph,
    decisions: tuple[AdaptiveDecision, ...],
    candidates: tuple[CandidateRecord, ...],
    inventory: AdaptiveInventory,
) -> tuple[int | str, ...]:
    cmap = {c.candidate_id: c for c in candidates}
    by_node = {d.node_name: d for d in decisions}
    local_io = sum(
        cmap[d.candidate_id].objective_facts.get("proven_local_io_nodes", 0)
        for d in decisions
    )
    pushdown = sum(
        cmap[d.candidate_id].objective_facts.get("proven_pushdown_actions", 0)
        for d in decisions
    )
    cross = sum(
        by_node[e.producer_node].target_id != by_node[e.consumer_node].target_id
        for e in graph.edges
    )
    collection = sum(
        cmap[by_node[e.consumer_node].candidate_id].objective_facts.get(
            "collection_units", 0
        )
        for e in graph.edges
        if by_node[e.producer_node].target_id != by_node[e.consumer_node].target_id
    )
    durable = sum(
        cmap[d.candidate_id].objective_facts.get("durable_materialization_units", 0)
        for d in decisions
    )
    fusible = sum(
        min(
            cmap[by_node[e.producer_node].candidate_id].objective_facts.get(
                "safely_fusible_logical_edges", 0
            ),
            cmap[by_node[e.consumer_node].candidate_id].objective_facts.get(
                "safely_fusible_logical_edges", 0
            ),
        )
        for e in graph.edges
        if by_node[e.producer_node].target_id == by_node[e.consumer_node].target_id
    )
    priorities = tuple(
        inventory.eligible_target_order.index(d.target_id) for d in decisions
    )
    identities = tuple(
        next(t.identity for t in inventory.targets if t.target_id == d.target_id)
        for d in decisions
    )
    return (
        -local_io,
        -pushdown,
        cross,
        collection,
        durable,
        -fusible,
        *priorities,
        *identities,
    )


def _regions(
    graph: LogicalGraph,
    decisions: tuple[AdaptiveDecision, ...],
    inventory: tuple[tuple[str, Any, Any], ...],
    context: PlanningContext,
) -> tuple[AdaptiveRegion, ...]:
    by_node = {d.node_name: d.target_id for d in decisions}
    target_by_id = {name: target for name, target, _ in inventory}
    names = tuple(graph.node_names())
    parent = {name: name for name in names}

    def find(name: str) -> str:
        while parent[name] != name:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name

    def union(left: str, right: str) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    node_map = graph.node_map()
    for edge in graph.edges:
        producer, consumer = node_map[edge.producer_node], node_map[edge.consumer_node]
        if by_node[edge.producer_node] != by_node[edge.consumer_node]:
            continue
        if _is_hard_boundary(producer, consumer, context):
            continue
        union(edge.producer_node, edge.consumer_node)

    groups: dict[str, list[str]] = {}
    for name in names:
        groups.setdefault(find(name), []).append(name)
    ordered_groups = sorted(
        groups.values(), key=lambda members: min(names.index(n) for n in members)
    )
    region_identity_by_node: dict[str, str] = {}
    regions: list[AdaptiveRegion] = []
    for members in ordered_groups:
        members = sorted(members, key=names.index)
        target_id = by_node[members[0]]
        target = target_by_id[target_id]
        region_id = f"region:{_digest({'target': target.identity(), 'nodes': members, 'security': target.security_domain, 'planner': '0.52'})[:24]}"
        for member in members:
            region_identity_by_node[member] = region_id
        regions.append(
            AdaptiveRegion(
                identity=region_id,
                target_id=target_id,
                logical_nodes=tuple(members),
                fused=False,
                security_domain=target.security_domain,
                metadata={"etlantic.boundary_policy": "conservative"},
            )
        )
    # Region dependencies are canonical and refer only to region identities.
    deps: dict[str, set[str]] = {region.identity: set() for region in regions}
    for edge in graph.edges:
        left, right = (
            region_identity_by_node[edge.producer_node],
            region_identity_by_node[edge.consumer_node],
        )
        if left != right:
            deps[right].add(left)
    return tuple(
        replace(region, dependencies=tuple(sorted(deps[region.identity])))
        for region in regions
    )


def _is_hard_boundary(producer: Any, consumer: Any, context: PlanningContext) -> bool:
    """Return true when declared semantics require a physical boundary."""
    keys = (
        "etlantic.effect_boundary",
        "etlantic.retry_boundary",
        "etlantic.checkpoint_boundary",
        "etlantic.validation_required",
        "etlantic.materialization_required",
        "etlantic.publication_required",
        "etlantic.handoff_required",
    )
    del context
    return any(
        bool(dict(getattr(node, "metadata", {}) or {}).get(key))
        for node in (producer, consumer)
        for key in keys
    )


def _physical_dag(
    graph: LogicalGraph,
    decisions: tuple[AdaptiveDecision, ...],
    targets: tuple[tuple[str, Any, Any], ...],
    regions: tuple[AdaptiveRegion, ...],
) -> PhysicalDAG:
    target_map = {name: target for name, target, _ in targets}
    decision_map = {d.node_name: d for d in decisions}
    region_by_node = {
        node: region.identity for region in regions for node in region.logical_nodes
    }
    compute_ids: dict[str, str] = {}
    node_tails: dict[str, str] = {}
    unit_specs: dict[str, dict[str, Any]] = {}
    dependencies: dict[str, list[PhysicalDependency]] = {
        node.name: [] for node in graph.nodes
    }
    for node in graph.nodes:
        target = target_map[decision_map[node.name].target_id]
        compute_payload = {
            "kind": "compute",
            "node": node.name,
            "target": target.identity(),
        }
        uid = f"unit:{_digest(compute_payload)[:24]}"
        compute_ids[node.name] = uid
        node_tails[node.name] = uid
        unit_specs[uid] = {
            "kind": PhysicalUnitKind.COMPUTE,
            "target_identity": target.identity(),
            "logical_nodes": (node.name,),
            "metadata": {
                "etlantic.engine": target.engine,
                "etlantic.region": region_by_node.get(node.name),
            },
        }
    for edge in graph.edges:
        producer = decision_map[edge.producer_node]
        consumer = decision_map[edge.consumer_node]
        if producer.target_id == consumer.target_id:
            dependencies[edge.consumer_node].append(
                PhysicalDependency(compute_ids[edge.producer_node])
            )
        else:
            source = target_map[producer.target_id]
            destination = target_map[consumer.target_id]
            transfer_payload = {
                "kind": "transfer",
                "edge": [
                    edge.producer_node,
                    edge.producer_port,
                    edge.consumer_node,
                    edge.consumer_port,
                ],
                "source": source.identity(),
                "destination": destination.identity(),
            }
            transfer_id = f"unit:{_digest(transfer_payload)[:24]}"
            unit_specs[transfer_id] = {
                "kind": PhysicalUnitKind.TRANSFER,
                "target_identity": destination.identity(),
                "dependencies": (PhysicalDependency(compute_ids[edge.producer_node]),),
                "metadata": {
                    "etlantic.source_target": source.identity(),
                    "etlantic.destination_target": destination.identity(),
                    "etlantic.edge": [edge.producer_node, edge.consumer_node],
                },
            }
            dependencies[edge.consumer_node].append(PhysicalDependency(transfer_id))
            if bool(
                dict(
                    getattr(graph.node_map()[edge.consumer_node], "metadata", {}) or {}
                ).get("etlantic.collection_required")
            ):
                collection_payload = {
                    "kind": "collection",
                    "edge": transfer_id,
                    "target": destination.identity(),
                }
                collection_id = f"unit:{_digest(collection_payload)[:24]}"
                unit_specs[collection_id] = {
                    "kind": PhysicalUnitKind.COLLECTION,
                    "target_identity": destination.identity(),
                    "dependencies": (PhysicalDependency(transfer_id),),
                    "metadata": {
                        "etlantic.edge": [edge.producer_node, edge.consumer_node]
                    },
                }
                dependencies[edge.consumer_node][-1] = PhysicalDependency(collection_id)
    for node in graph.nodes:
        target = target_map[decision_map[node.name].target_id]
        node_metadata = dict(getattr(node, "metadata", {}) or {})
        tail = compute_ids[node.name]
        for flag, kind in (
            ("etlantic.validation_required", PhysicalUnitKind.VALIDATION),
            ("etlantic.materialization_required", PhysicalUnitKind.MATERIALIZATION),
            ("etlantic.reuse_artifact", PhysicalUnitKind.REUSE),
        ):
            if not node_metadata.get(flag):
                continue
            payload = {
                "kind": kind.value,
                "node": node.name,
                "target": target.identity(),
                "value": node_metadata[flag],
            }
            uid = f"unit:{_digest(payload)[:24]}"
            unit_specs[uid] = {
                "kind": kind,
                "target_identity": target.identity(),
                "dependencies": (PhysicalDependency(tail),),
                "metadata": {
                    "etlantic.logical_node": node.name,
                    "etlantic.requirement": node_metadata[flag],
                },
            }
            tail = uid
        node_tails[node.name] = tail
        if node.kind is NodeKind.SINK:
            publication_payload = {
                "kind": "publication",
                "node": node.name,
                "target": target.identity(),
            }
            uid = f"unit:{_digest(publication_payload)[:24]}"
            unit_specs[uid] = {
                "kind": PhysicalUnitKind.PUBLICATION,
                "target_identity": target.identity(),
                "dependencies": (PhysicalDependency(tail, "lifecycle"),),
                "metadata": {"etlantic.logical_node": node.name},
            }
    units: list[PhysicalUnit] = []
    producer_for_compute = {unit_id: node for node, unit_id in compute_ids.items()}
    for uid, spec in unit_specs.items():
        if spec["kind"] is PhysicalUnitKind.COMPUTE:
            name = spec["logical_nodes"][0]
            rewritten = []
            for dep in dependencies[name]:
                producer = producer_for_compute.get(dep.unit_id)
                rewritten.append(
                    PhysicalDependency(node_tails[producer], dep.kind)
                    if producer is not None and node_tails[producer] != dep.unit_id
                    else dep
                )
            spec["dependencies"] = tuple({d.unit_id: d for d in rewritten}.values())
        elif spec.get("dependencies") and spec["kind"] is PhysicalUnitKind.TRANSFER:
            # Rewrite transfer dependencies to include a producer's declared
            # boundary, while preserving validation/materialization chains.
            rewritten = []
            for dep in spec["dependencies"]:
                producer = producer_for_compute.get(dep.unit_id)
                rewritten.append(
                    PhysicalDependency(node_tails[producer], dep.kind)
                    if producer is not None and node_tails[producer] != dep.unit_id
                    else dep
                )
            spec["dependencies"] = tuple({d.unit_id: d for d in rewritten}.values())
        units.append(PhysicalUnit(identity=uid, **spec))
    order = _topological_units(units)
    return PhysicalDAG(
        units=tuple(units), logical_to_physical=compute_ids, topological_order=order
    )


def _topological_units(units: list[PhysicalUnit]) -> tuple[str, ...]:
    by_id = {u.identity: u for u in units}
    remaining = set(by_id)
    output: list[str] = []
    while remaining:
        ready = sorted(
            uid
            for uid in remaining
            if all(dep.unit_id not in remaining for dep in by_id[uid].dependencies)
        )
        if not ready:
            raise _error(
                "PMADP402", "Physical DAG contains a cycle.", path=("physical_dag",)
            )
        output.extend(ready)
        remaining.difference_update(ready)
    return tuple(output)


def _explicit_fallback(
    pipeline_cls: type[Any] | None,
    context: PlanningContext,
    graph: LogicalGraph,
    *,
    selection: dict[str, Any] | None,
    definition: Any | None,
    report: ValidationReport,
) -> Any:
    from etlantic.plan.planner import plan_pipeline

    target_id = context.profile.eligible_targets[0]
    target = context.profile.placement_targets[target_id]
    overrides = {
        name: target.engine for name in context.profile.implementation_overrides
    }
    explicit_profile = context.profile.with_updates(
        execution_strategy="explicit",
        dataframe_engine=target.engine,
        implementation_overrides=overrides,
    )
    explicit_context = PlanningContext.create(
        profile=explicit_profile, registry=context.registry
    )
    if definition is not None:
        from etlantic.plan.planner import _build_plan_from_definition

        return _build_plan_from_definition(
            definition, explicit_context, selection=selection
        )
    return plan_pipeline(pipeline_cls, context=explicit_context, selection=selection)


def _digest(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _error(
    code: str, message: str, *, path: tuple[str, ...]
) -> PipelineValidationError:
    diagnostic = Diagnostic(
        code=code, severity=Severity.ERROR, message=message, path=path, phase="policy"
    )
    return PipelineValidationError(
        f"{code}: {message}",
        report=ValidationReport.from_diagnostics([diagnostic], phases=("policy",)),
    )
