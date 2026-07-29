"""Structured plan explain output."""

from __future__ import annotations

from typing import Any

from etlantic.plan.model import PipelinePlan


def explain_plan(plan: PipelinePlan) -> dict[str, Any]:
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
