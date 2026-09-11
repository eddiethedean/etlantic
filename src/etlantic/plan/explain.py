"""Structured plan explain output."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any

from etlantic.plan.adaptive_model import AdaptivePipelinePlan, PlanDocument


def explain_plan(plan: PlanDocument) -> dict[str, Any]:
    """Return a structured, tooling-friendly explanation of a plan.

    Suitable for CLI ``etlantic plan explain``, IDE tooling, and debugging.
    Does not mutate or re-plan the pipeline.

    Args:
        plan: Resolved plan to summarize.

    Returns:
        JSON-serializable dict with keys such as ``steps``, ``regions``,
        ``materialization_boundaries``, ``capability_decisions``, and
        ``fingerprint``.
    """
    if isinstance(plan, AdaptivePipelinePlan):
        return _explain_adaptive(plan)

    region_by_node: dict[str, str] = {}
    for region in plan.regions:
        for name in region.node_names:
            region_by_node[name] = region.identity

    collection_points = [
        b.to_dict()
        for b in plan.materialization_boundaries
        if b.reason
        in {
            "collection_point",
            "sink_publication",
            "cross_engine",
            "validation_boundary",
        }
    ]
    conversion_boundaries = [
        {
            **b.to_dict(),
            "interchange": b.metadata.get("interchange"),
        }
        for b in plan.materialization_boundaries
        if b.reason == "cross_engine"
    ]

    steps = []
    for node in plan.logical_graph.nodes:
        if plan.selected_nodes is not None and node.name not in plan.selected_nodes:
            continue
        unit_id = plan.logical_to_physical.get(node.name)
        unit = next((u for u in plan.physical_units if u.identity == unit_id), None)
        out_res = [
            o.to_dict() for o in plan.output_resolutions if o.node_name == node.name
        ]
        steps.append(
            {
                "node": node.name,
                "kind": node.kind.value,
                "region": region_by_node.get(node.name),
                "physical_unit": unit_id,
                "engine": unit.engine if unit is not None else None,
                "ownership": (
                    (unit.metadata or {}).get("ownership") if unit is not None else None
                ),
                "implementation": (
                    plan.implementations[node.name].to_dict()
                    if node.name in plan.implementations
                    else None
                ),
                "implementation_kind": (
                    plan.implementations[node.name].kind
                    if node.name in plan.implementations
                    else None
                ),
                "ir_fingerprint": (
                    plan.implementations[node.name].ir_fingerprint
                    if node.name in plan.implementations
                    else None
                ),
                "compiler": (
                    {
                        "name": plan.implementations[node.name].compiler_name,
                        "version": plan.implementations[node.name].compiler_version,
                        "protocol": plan.implementations[node.name].compiler_protocol,
                        "selection_reason": (
                            plan.implementations[node.name].fallback_reason
                            or "portable_compiled"
                        ),
                        "support_summary": plan.implementations[node.name].metadata.get(
                            "support_summary"
                        )
                        if plan.implementations[node.name].metadata
                        else None,
                        "capabilities": plan.implementations[node.name].metadata.get(
                            "compiler_capabilities"
                        )
                        if plan.implementations[node.name].metadata
                        else None,
                    }
                    if node.name in plan.implementations
                    and plan.implementations[node.name].kind == "portable_compiled"
                    else None
                ),
                "requirements": (
                    plan.implementations[node.name].requirements
                    if node.name in plan.implementations
                    else None
                ),
                "fallback_reason": (
                    plan.implementations[node.name].fallback_reason
                    if node.name in plan.implementations
                    else None
                ),
                "binding": node.binding,
                "asset": node.binding,
                "outputs": out_res,
            }
        )

    return {
        "plan_id": plan.plan_id,
        "pipeline_id": plan.pipeline_id,
        "profile": plan.profile_name,
        "fingerprint": plan.fingerprint,
        "security_domain": plan.security_domain,
        "dataframe_protocol": plan.metadata.get("dataframe_protocol"),
        "sql_protocol": plan.metadata.get("sql_protocol"),
        "sql_fusion": plan.metadata.get("sql_fusion"),
        "sql_transaction_scopes": plan.metadata.get("sql_transaction_scopes"),
        "sql_schema_mutations": plan.metadata.get("sql_schema_mutations"),
        "spark_protocol": plan.metadata.get("spark_protocol"),
        "spark_fusion": plan.metadata.get("spark_fusion"),
        "spark_streaming_stability": plan.metadata.get("spark_streaming_stability"),
        "regions": [r.to_dict() for r in plan.regions],
        "materialization_boundaries": [
            b.to_dict() for b in plan.materialization_boundaries
        ],
        "collection_points": collection_points,
        "conversion_boundaries": conversion_boundaries,
        "output_resolutions": [o.to_dict() for o in plan.output_resolutions],
        "capability_decisions": list(plan.capability_decisions),
        "steps": steps,
        "selected_nodes": (
            list(plan.selected_nodes) if plan.selected_nodes is not None else None
        ),
    }


def _explain_adaptive(plan: AdaptivePipelinePlan) -> dict[str, Any]:
    """Project stored adaptive evidence without replanning."""
    decisions = {item.node_name: item.to_dict() for item in plan.decisions}
    alternatives: dict[str, list[dict[str, Any]]] = {}
    for candidate in plan.candidates:
        alternatives.setdefault(candidate.node_name, []).append(candidate.to_dict())
    payload = {
        "plan_id": plan.plan_id,
        "pipeline_id": plan.pipeline_id,
        "profile": plan.profile_name,
        "fingerprint": plan.fingerprint,
        "schema": plan.schema,
        "security_domain": plan.security_domain,
        "planning_only": True,
        "objective": list(plan.objective),
        "inventory": plan.inventory.to_dict(),
        "decisions": list(decisions.values()),
        "alternatives": alternatives,
        "regions": [region.to_dict() for region in plan.regions],
        "physical_dag": plan.physical_dag.to_dict(),
        "selected_nodes": list(plan.selected_nodes)
        if plan.selected_nodes is not None
        else None,
        "metadata": dict(plan.metadata),
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    if len(encoded) <= 4 * 1024 * 1024:
        return payload
    # Explain is a projection of stored evidence; when bounded output would be
    # exceeded, return a deterministic summary without replanning or loading.
    return {
        "plan_id": plan.plan_id,
        "pipeline_id": plan.pipeline_id,
        "profile": plan.profile_name,
        "fingerprint": plan.fingerprint,
        "schema": plan.schema,
        "security_domain": plan.security_domain,
        "planning_only": True,
        "truncated": True,
        "diagnostic": {
            "code": "PMADP305",
            "message": "Adaptive explain detail exceeds the 4 MiB UTF-8 limit.",
        },
        "objective": list(plan.objective),
        "selected_targets": {item.node_name: item.target_id for item in plan.decisions},
        "counts": {
            "nodes": len(plan.logical_graph.nodes),
            "candidates": len(plan.candidates),
            "regions": len(plan.regions),
            "physical_units": len(plan.physical_dag.units),
        },
        "omitted_sha256": hashlib.sha256(encoded).hexdigest(),
        "rejection_reason_counts": dict(
            sorted(
                Counter(
                    code
                    for candidate in plan.candidates
                    for code in candidate.reason_codes
                ).items()
            )
        ),
    }
