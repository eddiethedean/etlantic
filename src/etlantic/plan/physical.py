"""Versioned physical-unit records used only by adaptive plan ``/2``."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from etlantic.extensions import (
    _reject_nested_secret_material,
    _reject_nested_source_row_material,
)
from etlantic.plan.freeze import deep_freeze, mutable_copy

PHYSICAL_UNIT_SCHEMA = "etlantic.physical_unit/1"


class PhysicalUnitKind(StrEnum):
    """Closed set of unit kinds admitted by the 0.51 physical protocol."""

    COMPUTE = "compute"
    TRANSFER = "transfer"
    COLLECTION = "collection"
    VALIDATION = "validation"
    MATERIALIZATION = "materialization"
    REUSE = "reuse"
    PUBLICATION = "publication"


@dataclass(frozen=True, slots=True)
class PhysicalDependency:
    """Typed dependency between physical units."""

    unit_id: str
    kind: str = "data"

    def __post_init__(self) -> None:
        if not isinstance(self.unit_id, str) or not self.unit_id.strip():
            raise ValueError("PMADP402: physical dependency unit_id must be non-blank")
        if not isinstance(self.kind, str) or self.kind not in {
            "data",
            "control",
            "lifecycle",
        }:
            raise ValueError(
                f"PMADP400: unknown physical dependency kind {self.kind!r}"
            )

    def to_dict(self) -> dict[str, str]:
        return {"unit_id": self.unit_id, "kind": self.kind}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PhysicalDependency:
        _reject_unknown(data, {"unit_id", "kind"}, "physical dependency")
        _require_fields(data, {"unit_id", "kind"}, "physical dependency")
        return cls(unit_id=data["unit_id"], kind=data.get("kind", "data"))


@dataclass(frozen=True, slots=True)
class PhysicalUnit:
    """Secret-free executable unit descriptor for an adaptive plan."""

    identity: str
    kind: PhysicalUnitKind
    dependencies: tuple[PhysicalDependency, ...] = ()
    target_identity: str = ""
    logical_nodes: tuple[str, ...] = ()
    input_contracts: tuple[Mapping[str, Any], ...] = ()
    output_contracts: tuple[Mapping[str, Any], ...] = ()
    policy: Mapping[str, Any] = field(default_factory=dict)
    retry_policy: Mapping[str, Any] = field(default_factory=dict)
    ownership: Mapping[str, Any] = field(default_factory=dict)
    protocol_versions: Mapping[str, str] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.identity, str) or not self.identity.strip():
            raise ValueError("PMADP400: physical unit identity must be non-blank")
        try:
            kind = PhysicalUnitKind(self.kind)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"PMADP400: unknown physical unit kind {self.kind!r}"
            ) from exc
        if (
            not isinstance(self.target_identity, str)
            or not self.target_identity.strip()
        ):
            raise ValueError("PMADP201: physical unit target identity is required")
        nodes = _validated_array(
            self.logical_nodes, "physical unit logical_nodes", code="PMADP403"
        )
        if any(not isinstance(node, str) or not node.strip() for node in nodes):
            raise ValueError("PMADP403: physical unit logical_nodes must be non-blank")
        if len(set(nodes)) != len(nodes):
            raise ValueError("PMADP403: physical unit logical_nodes must be unique")
        dependency_values = _validated_array(
            self.dependencies, "physical unit dependencies", code="PMADP402"
        )
        dependencies = tuple(
            dep
            if isinstance(dep, PhysicalDependency)
            else PhysicalDependency.from_dict(dep)
            for dep in dependency_values
        )
        dependency_ids = [dep.unit_id for dep in dependencies]
        if self.identity in dependency_ids:
            raise ValueError("PMADP402: physical unit cannot depend on itself")
        if len(set(dependency_ids)) != len(dependency_ids):
            raise ValueError("PMADP402: physical unit dependencies must be unique")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "logical_nodes", nodes)
        object.__setattr__(self, "dependencies", dependencies)
        input_contracts = _validated_object_sequence(
            self.input_contracts, "physical unit input_contracts"
        )
        output_contracts = _validated_object_sequence(
            self.output_contracts, "physical unit output_contracts"
        )
        policy = _validated_object_mapping(self.policy, "physical unit policy")
        retry_policy = _validated_object_mapping(
            self.retry_policy, "physical unit retry_policy"
        )
        ownership = _validated_object_mapping(self.ownership, "physical unit ownership")
        protocol_versions = _validated_string_map(
            self.protocol_versions, "physical unit protocol_versions"
        )
        metadata = _validated_object_mapping(self.metadata, "physical unit metadata")
        envelope = {
            "input_contracts": input_contracts,
            "output_contracts": output_contracts,
            "policy": policy,
            "retry_policy": retry_policy,
            "ownership": ownership,
            "protocol_versions": protocol_versions,
            "metadata": metadata,
        }
        try:
            _reject_nested_secret_material(envelope, path="physical unit")
            _reject_nested_source_row_material(envelope, path="physical unit")
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"PMADP101: invalid physical unit envelope: {exc}"
            ) from exc
        for name, value in (
            ("input_contracts", input_contracts),
            ("output_contracts", output_contracts),
            ("policy", policy),
            ("retry_policy", retry_policy),
            ("ownership", ownership),
            ("protocol_versions", protocol_versions),
            ("metadata", metadata),
        ):
            object.__setattr__(self, name, deep_freeze(value))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": PHYSICAL_UNIT_SCHEMA,
            "identity": self.identity,
            "kind": PhysicalUnitKind(self.kind).value,
            "dependencies": [dependency.to_dict() for dependency in self.dependencies],
            "target_identity": self.target_identity,
            "logical_nodes": list(self.logical_nodes),
            "input_contracts": mutable_copy(self.input_contracts),
            "output_contracts": mutable_copy(self.output_contracts),
            "policy": mutable_copy(self.policy),
            "retry_policy": mutable_copy(self.retry_policy),
            "ownership": mutable_copy(self.ownership),
            "protocol_versions": mutable_copy(self.protocol_versions),
            "metadata": mutable_copy(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PhysicalUnit:
        _reject_unknown(
            data,
            {
                "schema",
                "identity",
                "kind",
                "dependencies",
                "target_identity",
                "logical_nodes",
                "input_contracts",
                "output_contracts",
                "policy",
                "retry_policy",
                "ownership",
                "protocol_versions",
                "metadata",
            },
            "physical unit",
        )
        _require_fields(
            data,
            set(cls.__dataclass_fields__) | {"schema"},
            "physical unit",
        )
        if data.get("schema", PHYSICAL_UNIT_SCHEMA) != PHYSICAL_UNIT_SCHEMA:
            raise ValueError(
                f"PMADP400: unsupported physical unit schema {data.get('schema')!r}"
            )
        return cls(
            identity=data["identity"],
            kind=data["kind"],
            dependencies=data.get("dependencies", ()),
            target_identity=data["target_identity"],
            logical_nodes=data.get("logical_nodes", ()),
            input_contracts=data.get("input_contracts", ()),
            output_contracts=data.get("output_contracts", ()),
            policy=data.get("policy", {}),
            retry_policy=data.get("retry_policy", {}),
            ownership=data.get("ownership", {}),
            protocol_versions=data.get("protocol_versions", {}),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True, slots=True)
class PhysicalDAG:
    """Validated physical topology and primary logical-node attribution."""

    units: tuple[PhysicalUnit, ...]
    logical_to_physical: Mapping[str, str]
    topological_order: tuple[str, ...]

    def __post_init__(self) -> None:
        units = _validated_array(self.units, "physical DAG units")
        units = tuple(
            unit if isinstance(unit, PhysicalUnit) else PhysicalUnit.from_dict(unit)
            for unit in units
        )
        ids = [unit.identity for unit in units]
        if len(set(ids)) != len(ids):
            raise ValueError("PMADP402: physical unit identities must be unique")
        unit_map = {unit.identity: unit for unit in units}
        for unit in units:
            for dependency in unit.dependencies:
                if dependency.unit_id not in unit_map:
                    raise ValueError(
                        "PMADP402: physical DAG has dangling dependency "
                        f"{dependency.unit_id!r}"
                    )
        order = _validated_array(
            self.topological_order, "physical DAG topological_order", code="PMADP402"
        )
        if any(
            not isinstance(unit_id, str) or not unit_id.strip() for unit_id in order
        ):
            raise ValueError(
                "PMADP402: physical topological order must contain unit ids"
            )
        if set(order) != set(ids) or len(order) != len(ids):
            raise ValueError(
                "PMADP402: physical topological order must cover every unit"
            )
        positions = {unit_id: index for index, unit_id in enumerate(order)}
        for unit in units:
            if any(
                positions[dep.unit_id] >= positions[unit.identity]
                for dep in unit.dependencies
            ):
                raise ValueError("PMADP402: physical DAG topological order is invalid")
        mapping = dict(self.logical_to_physical)
        if len(mapping) != len(self.logical_to_physical):
            raise ValueError("PMADP403: duplicate logical physical attribution")
        if any(not isinstance(node, str) or not node.strip() for node in mapping):
            raise ValueError(
                "PMADP403: logical_to_physical node names must be non-blank"
            )
        if any(
            not isinstance(unit_id, str) or not unit_id.strip()
            for unit_id in mapping.values()
        ):
            raise ValueError(
                "PMADP403: logical_to_physical unit ids must be non-blank strings"
            )
        if any(unit_id not in unit_map for unit_id in mapping.values()):
            raise ValueError("PMADP403: logical_to_physical references an unknown unit")
        attributed = {node for unit in units for node in unit.logical_nodes}
        if any(node not in mapping for node in attributed):
            raise ValueError(
                "PMADP403: physical attribution is missing a primary mapping"
            )
        if any(
            node not in unit_map[unit_id].logical_nodes
            for node, unit_id in mapping.items()
        ):
            raise ValueError(
                "PMADP403: logical_to_physical must match unit logical attribution"
            )
        if any(
            unit_map[unit_id].kind is not PhysicalUnitKind.COMPUTE
            for unit_id in mapping.values()
        ):
            raise ValueError(
                "PMADP403: logical_to_physical must reference compute units"
            )
        # Every declared logical predecessor must have a complete physical
        # dependency path to its consumer.  This catches tampering that merely
        # recomputes the outer plan fingerprint after disconnecting a unit.
        for node, consumer_id in mapping.items():
            consumer = unit_map[consumer_id]
            predecessors = consumer.metadata.get("etlantic.logical_predecessors", ())
            if not isinstance(predecessors, (list, tuple)):
                raise ValueError(
                    "PMADP403: logical predecessor metadata must be an array"
                )
            for predecessor in predecessors:
                if predecessor not in mapping:
                    raise ValueError(
                        "PMADP403: logical predecessor is not mapped to a physical unit"
                    )
                expected = mapping[predecessor]
                seen: set[str] = set()
                frontier = [dep.unit_id for dep in consumer.dependencies]
                reachable = False
                while frontier:
                    unit_id = frontier.pop()
                    if unit_id in seen:
                        continue
                    seen.add(unit_id)
                    if unit_id == expected:
                        reachable = True
                        break
                    frontier.extend(
                        dep.unit_id for dep in unit_map[unit_id].dependencies
                    )
                if not reachable:
                    raise ValueError(
                        f"PMADP403: logical edge {predecessor!r} -> {node!r} "
                        "has no physical dependency path"
                    )
        object.__setattr__(self, "units", units)
        object.__setattr__(self, "logical_to_physical", deep_freeze(mapping))
        object.__setattr__(self, "topological_order", order)

    def to_dict(self) -> dict[str, Any]:
        return {
            "units": [unit.to_dict() for unit in self.units],
            "logical_to_physical": mutable_copy(self.logical_to_physical),
            "topological_order": list(self.topological_order),
        }

    def validate_logical_paths(
        self, logical_edges: tuple[tuple[str, ...], ...]
    ) -> None:
        """Validate logical-edge reachability against the physical topology.

        The logical graph is authoritative.  Per-unit predecessor metadata is
        explanatory only and therefore cannot be used to decide whether a
        logical edge has a physical realization.
        """
        unit_map = {unit.identity: unit for unit in self.units}
        port_edges = {edge for edge in logical_edges if len(edge) == 4}
        if port_edges:
            for unit in self.units:
                ports = unit.metadata.get("etlantic.edge_ports")
                if ports is not None and (
                    not isinstance(ports, (list, tuple))
                    or len(ports) != 4
                    or not all(isinstance(value, str) for value in ports)
                    or tuple(ports) not in port_edges
                ):
                    raise ValueError(
                        "PMADP403: physical route references an unknown logical port edge"
                    )
        for edge in logical_edges:
            producer, consumer = edge[:2]
            producer_id = self.logical_to_physical.get(producer)
            consumer_id = self.logical_to_physical.get(consumer)
            if producer_id is None or consumer_id is None:
                raise ValueError(
                    "PMADP403: logical edge references an unmapped logical node"
                )
            # Fused historical /2 documents legitimately cover both endpoints
            # with the same compute unit.
            if producer_id == consumer_id:
                continue
            # Count edge realizations, not arbitrary transitive graph paths.
            # An intervening compute unit belongs to another logical edge;
            # ordinary logical diamonds must remain valid. Saturate at two so
            # adversarial branching cannot amplify work or integer sizes.
            paths: dict[str, int] = {producer_id: 1}
            for unit_id in self.topological_order:
                if unit_id == producer_id:
                    continue
                unit = unit_map[unit_id]
                ports = unit.metadata.get("etlantic.edge_ports")
                if len(edge) == 4 and ports is not None and tuple(ports) != edge:
                    paths[unit_id] = 0
                    continue
                if unit.kind is PhysicalUnitKind.COMPUTE and unit_id != consumer_id:
                    paths[unit_id] = 0
                    continue
                paths[unit_id] = min(
                    2,
                    sum(
                        paths.get(dependency.unit_id, 0)
                        for dependency in unit.dependencies
                        if dependency.kind == "data"
                    ),
                )
            count = paths.get(consumer_id, 0)
            if count == 0:
                raise ValueError(
                    f"PMADP403: logical edge {producer!r} -> {consumer!r} "
                    "has no physical dependency path"
                )
            if count > 1:
                raise ValueError(
                    f"PMADP403: logical edge {producer!r} -> {consumer!r} "
                    "has multiple physical dependency paths"
                )

    def validate_generated_envelope(self) -> None:
        """Validate evidence required for newly generated 0.52 physical units."""
        for unit in self.units:
            if not unit.policy or not unit.ownership or not unit.protocol_versions:
                raise ValueError(
                    "PMADP403: generated physical unit lacks policy, ownership, or protocol evidence"
                )
            if unit.kind is PhysicalUnitKind.COMPUTE and not (
                unit.input_contracts or unit.output_contracts
            ):
                raise ValueError(
                    "PMADP403: generated compute unit lacks contract bindings"
                )
            if unit.kind is PhysicalUnitKind.TRANSFER:
                contract = unit.metadata.get("etlantic.handoff_contract")
                evidence = unit.metadata.get("etlantic.handoff_evidence")
                required = {
                    "producer_target_identity",
                    "consumer_target_identity",
                    "schema_fingerprint",
                    "format",
                    "mode",
                    "durability",
                    "producer_capability_fingerprint",
                    "consumer_capability_fingerprint",
                }
                if (
                    not isinstance(contract, Mapping)
                    or not required <= set(contract)
                    or not isinstance(evidence, (list, tuple))
                    or not evidence
                ):
                    raise ValueError(
                        "PMADP403: generated transfer lacks bound handoff contract evidence"
                    )
                expected = _generated_transfer_identity(unit)
                if unit.identity != expected:
                    raise ValueError(
                        "PMADP403: generated transfer identity does not bind contracts, policy, and handoff evidence"
                    )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PhysicalDAG:
        _reject_unknown(
            data, {"units", "logical_to_physical", "topological_order"}, "physical DAG"
        )
        _require_fields(
            data,
            {"units", "logical_to_physical", "topological_order"},
            "physical DAG",
        )
        units = data.get("units", ())
        mapping = data.get("logical_to_physical", {})
        if not isinstance(mapping, Mapping):
            raise ValueError("PMADP403: logical_to_physical must be an object")
        return cls(
            units=units,
            logical_to_physical=mapping,
            topological_order=data.get("topological_order", ()),
        )


def _generated_transfer_identity(unit: PhysicalUnit) -> str:
    """Recompute the generated transfer identity from its complete envelope."""
    metadata = unit.metadata
    edge_ports = list(metadata.get("etlantic.edge_ports", ()))
    edge = (
        [edge_ports[0], edge_ports[2], edge_ports[1], edge_ports[3]]
        if len(edge_ports) == 4
        else edge_ports
    )
    payload = {
        "kind": "transfer",
        "edge": edge,
        "source": metadata.get("etlantic.source_target"),
        "destination": metadata.get("etlantic.destination_target"),
        "handoff_contract": dict(metadata.get("etlantic.handoff_contract", {})),
        "handoff_evidence": list(metadata.get("etlantic.handoff_evidence", ())),
        "input_contracts": [dict(value) for value in unit.input_contracts],
        "output_contracts": [dict(value) for value in unit.output_contracts],
        "policy": dict(unit.policy),
        "retry_policy": dict(unit.retry_policy),
        "ownership": dict(unit.ownership),
        "protocol_versions": dict(unit.protocol_versions),
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return f"unit:{hashlib.sha256(encoded).hexdigest()[:24]}"


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


def _validated_object_mapping(value: Mapping[str, Any], label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"PMADP400: {label} must be an object")
    result = dict(value)
    try:
        json.dumps(mutable_copy(result), separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"PMADP400: {label} must be JSON-serializable") from exc
    return result


def _validated_object_sequence(
    value: tuple[Mapping[str, Any], ...], label: str
) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"PMADP400: {label} must be an array")
    result: list[dict[str, Any]] = []
    for item in value:
        result.append(_validated_object_mapping(item, f"{label} item"))
    return tuple(result)
