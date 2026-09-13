"""Adapters that present an executable adaptive plan to the local host.

The adaptive wire model intentionally stays independent from the historical
``PipelinePlan`` model.  This module contains the narrow, in-process adapter
used by the physical scheduler; it does not alter or re-plan the stored DAG.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from etlantic.plan.freeze import mutable_copy
from etlantic.plan.model import PhysicalUnit, PipelinePlan
from etlantic.plan.regions import ExecutionRegion, MaterializationBoundary
from etlantic.registry import ImplementationDescriptor
from etlantic.transform.compiler import TransformPlanningContext


def pipeline_plan_for_adaptive(
    adaptive_plan: Any, *, runtime: Any, pipeline_cls: type[Any] | None
) -> PipelinePlan:
    """Build the read-only host view required by :class:`LocalOrchestrator`.

    Implementation descriptors are resolved from the already-scoped runtime
    registry or from the authored transformation class.  No plugin discovery,
    compilation, or execution occurs here.
    """
    target_by_id = {
        target.target_id: target for target in adaptive_plan.inventory.targets
    }
    decisions = {decision.node_name: decision for decision in adaptive_plan.decisions}
    regions = tuple(
        ExecutionRegion(
            identity=region.identity,
            engine=target_by_id[region.target_id].engine,
            node_names=tuple(region.logical_nodes),
            security_domain=region.security_domain,
            metadata=mutable_copy(region.metadata),
        )
        for region in adaptive_plan.regions
    )

    implementations: dict[str, ImplementationDescriptor] = {}
    members = getattr(pipeline_cls, "__pipeline_members__", {}) if pipeline_cls else {}
    stored_records = dict(adaptive_plan.metadata).get("etlantic.implementations") or ()
    stored_by_node = {
        str(record.get("node_name")): record
        for record in stored_records
        if isinstance(record, dict) and record.get("node_name")
    }
    for node in adaptive_plan.logical_graph.nodes:
        if node.kind.value != "step":
            continue
        target = target_by_id[decisions[node.name].target_id]
        engine = target.engine
        key = f"{node.transformation_id}::{engine}"
        descriptor = getattr(runtime, "registry", None)
        descriptor = (
            getattr(descriptor, "implementations", {}).get(key)
            if descriptor is not None
            else None
        )
        if descriptor is None:
            stored = stored_by_node.get(node.name, {})
            implementation = (
                stored.get("implementation") if isinstance(stored, dict) else None
            )
            if isinstance(implementation, dict):
                descriptor = ImplementationDescriptor.from_dict(implementation)
        if descriptor is None:
            member = members.get(node.name)
            transform = getattr(member, "transformation", None)
            if transform is not None:
                portable = getattr(transform, "portable_definition", lambda: None)()
                if portable is not None and engine == "local":
                    from etlantic.transform.discovery import (
                        discover_transform_compilers_for_profile,
                    )

                    compiler = discover_transform_compilers_for_profile(
                        getattr(runtime, "_active_profile", None)
                        or adaptive_plan.profile_name
                    ).get("local")
                    if compiler is not None:
                        info = compiler.info
                        analysis = compiler.analyze(
                            portable.plan,
                            context=TransformPlanningContext(
                                adaptive_plan.pipeline_id,
                                node.name,
                                adaptive_plan.profile_name,
                                engine,
                            ),
                            requirements=portable.requirements,
                        )
                        descriptor = ImplementationDescriptor(
                            transformation_id=node.transformation_id or "unknown",
                            engine=engine,
                            identity=f"portable:{info.name}@{portable.fingerprint[:16]}",
                            is_async=True,
                            kind="portable_compiled",
                            ir_fingerprint=portable.fingerprint,
                            compiler_name=info.name,
                            compiler_version=info.version,
                            compiler_protocol=info.compiler_protocol,
                            compiler_evidence_fingerprint=info.evidence_fingerprint,
                            requirements={
                                k: list(v) for k, v in portable.requirements.items()
                            },
                            support_summary=analysis.to_requirement_support(
                                target={
                                    "engine": info.engine,
                                    "compiler": info.name,
                                    "version": info.version,
                                    "protocol": info.compiler_protocol,
                                    "package": info.package or info.name,
                                    "implementation": info.implementation or info.name,
                                }
                            ),
                            portable_plan=mutable_copy(portable.plan),
                        )
                if descriptor is None:
                    record = transform.implementations().get(engine)
                    if record is not None:
                        descriptor = ImplementationDescriptor(
                            transformation_id=node.transformation_id or "unknown",
                            engine=engine,
                            identity=record.identity,
                            is_async=record.is_async,
                            kind="native",
                        )
        if descriptor is not None:
            implementations[node.name] = descriptor

    target_by_identity = {
        target.identity: target for target in adaptive_plan.inventory.targets
    }
    physical_units = tuple(adaptive_plan.physical_dag.units)
    logical_to_physical = dict(adaptive_plan.physical_dag.logical_to_physical)
    execution = dict(adaptive_plan.metadata).get("etlantic.runtime") or {}
    request_meta = execution.get("request") if isinstance(execution, dict) else {}
    settings = {
        "concurrency": (request_meta or {}).get("metadata", {}).get("concurrency", 4)
    }
    boundaries: list[MaterializationBoundary] = []
    for unit in physical_units:
        if unit.kind.value != "transfer":
            continue
        edge = unit.metadata.get("etlantic.edge_ports")
        interchange = unit.metadata.get("etlantic.interchange")
        if not isinstance(edge, (list, tuple)) or len(edge) != 4:
            continue
        boundaries.append(
            MaterializationBoundary(
                identity=unit.identity,
                producer_node=str(edge[0]),
                producer_port=str(edge[2]),
                reason="cross_engine",
                security_domain=adaptive_plan.security_domain,
                metadata={
                    "interchange": mutable_copy(interchange)
                    if isinstance(interchange, Mapping)
                    else None,
                    "consumer_node": str(edge[1]),
                    "consumer_port": str(edge[3]),
                },
            )
        )
    return PipelinePlan(
        schema="etlantic.plan/1",
        plan_id=adaptive_plan.plan_id,
        pipeline_id=adaptive_plan.pipeline_id,
        pipeline_name=adaptive_plan.pipeline_name,
        profile_name=adaptive_plan.profile_name,
        fingerprint=adaptive_plan.fingerprint,
        logical_graph=adaptive_plan.logical_graph,
        regions=regions,
        physical_units=tuple(
            PhysicalUnit(
                identity=unit.identity,
                region_id=str(unit.metadata.get("etlantic.region") or unit.identity),
                logical_nodes=tuple(unit.logical_nodes),
                engine=target_by_identity[unit.target_identity].engine,
                metadata={
                    **mutable_copy(unit.metadata),
                    "etlantic.physical_kind": unit.kind.value,
                    "etlantic.target_identity": unit.target_identity,
                    "etlantic.dependencies": [
                        dependency.to_dict() for dependency in unit.dependencies
                    ],
                },
            )
            for unit in physical_units
        ),
        materialization_boundaries=tuple(boundaries),
        logical_to_physical=logical_to_physical,
        implementations=implementations,
        bindings=dict(
            getattr(getattr(runtime, "registry", None), "bindings", {}) or {}
        ),
        selected_nodes=tuple(
            adaptive_plan.selected_nodes or adaptive_plan.logical_graph.node_names()
        ),
        security_domain=adaptive_plan.security_domain,
        profile_snapshot=mutable_copy(adaptive_plan.profile_snapshot),
        execution_settings=settings,
        metadata={
            "etlantic.adaptive": True,
            "physical_dag": adaptive_plan.physical_dag.to_dict(),
        },
    )


__all__ = ["pipeline_plan_for_adaptive"]
