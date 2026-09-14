"""Adapters that present an executable adaptive plan to the local host.

The adaptive wire model intentionally stays independent from the historical
``PipelinePlan`` model.  This module contains the narrow, in-process adapter
used by the physical scheduler; it does not alter or re-plan the stored DAG.
"""

from __future__ import annotations

import base64
import importlib
import json
from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from etlantic.plan.freeze import mutable_copy
from etlantic.plan.model import PhysicalUnit, PipelinePlan
from etlantic.plan.regions import ExecutionRegion, MaterializationBoundary
from etlantic.registry import ImplementationDescriptor


def stored_implementations(adaptive_plan: Any) -> dict[str, ImplementationDescriptor]:
    """Decode only fingerprinted portable records; live authoring is not authority."""
    implementations: dict[str, ImplementationDescriptor] = {}
    records = adaptive_plan.metadata.get("etlantic.implementations") or ()
    for record in records:
        if not isinstance(record, Mapping) or record.get("kind") != "step":
            continue
        raw = mutable_copy(record.get("implementation") or {})
        allowed = {
            "transformation_id",
            "engine",
            "identity",
            "is_async",
            "kind",
            "ir_fingerprint",
            "compiler_name",
            "compiler_version",
            "compiler_protocol",
            "requirements",
            "support_summary",
            "fallback_reason",
            "portable_plan",
            "metadata",
            "compiler_evidence_fingerprint",
            "portable_plan_json",
            "support_summary_json",
            "portable_plan_fingerprint",
        }
        if set(raw) - allowed:
            raise ValueError("Stored portable descriptor contains unknown fields")
        for encoded_key, decoded_key in (
            ("portable_plan_json", "portable_plan"),
            ("support_summary_json", "support_summary"),
        ):
            encoded = raw.get(encoded_key)
            if encoded is not None:
                raw[decoded_key] = json.loads(
                    base64.b64decode(encoded, validate=True).decode()
                )
        descriptor = ImplementationDescriptor.from_dict(raw)
        if descriptor.kind != "portable_compiled" or not descriptor.portable_plan:
            raise ValueError("Adaptive step requires a stored portable definition")
        implementations[str(record["node_name"])] = descriptor
    return implementations


def resolve_contract_type(contract_id: str | None) -> type[Any] | None:
    if not contract_id or ":" not in contract_id:
        return None
    module_name, qualname = contract_id.split(":", 1)
    try:
        value: Any = importlib.import_module(module_name)
        for part in qualname.split("."):
            value = getattr(value, part)
        return value if isinstance(value, type) else None
    except (ImportError, AttributeError):
        return None


def pipeline_plan_for_adaptive(
    adaptive_plan: Any,
    *,
    runtime: Any,
    pipeline_cls: type[Any] | None,
    contract_pins: Mapping[str, type[Any]] | None = None,
    binding_pins: Mapping[str, Any] | None = None,
) -> PipelinePlan:
    """Build the read-only host view required by :class:`LocalOrchestrator`.

    Implementation descriptors are decoded from the fingerprinted stored records.  No plugin discovery,
    compilation, or execution occurs here.
    """
    target_by_id = {
        target.target_id: target for target in adaptive_plan.inventory.targets
    }
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

    implementations = stored_implementations(adaptive_plan)

    target_by_identity = {
        target.identity: target for target in adaptive_plan.inventory.targets
    }
    physical_units = tuple(adaptive_plan.physical_dag.units)
    logical_to_physical = dict(adaptive_plan.physical_dag.logical_to_physical)
    execution = dict(adaptive_plan.metadata).get("etlantic.runtime") or {}
    request_meta = execution.get("request") if isinstance(execution, Mapping) else {}
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
    logical_graph = adaptive_plan.logical_graph
    if pipeline_cls is None or contract_pins is not None:

        def resolve_type(contract_id: str | None) -> type[Any] | None:
            if contract_id is None:
                return None
            return (
                contract_pins.get(contract_id)
                if contract_pins is not None
                else resolve_contract_type(contract_id)
            )

        def resolve_port(port: Any) -> Any:
            return replace(port, contract_type=resolve_type(port.contract_id))

        logical_graph = replace(
            logical_graph,
            nodes=tuple(
                replace(
                    node,
                    contract_type=resolve_type(node.contract_id),
                    inputs=tuple(resolve_port(port) for port in node.inputs),
                    outputs=tuple(resolve_port(port) for port in node.outputs),
                )
                for node in logical_graph.nodes
            ),
        )

    return PipelinePlan(
        schema="etlantic.plan/1",
        plan_id=adaptive_plan.plan_id,
        pipeline_id=adaptive_plan.pipeline_id,
        pipeline_name=adaptive_plan.pipeline_name,
        profile_name=adaptive_plan.profile_name,
        fingerprint=adaptive_plan.fingerprint,
        logical_graph=logical_graph,
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
        bindings=dict(binding_pins or {}),
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
