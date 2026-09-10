"""Versioned physical-unit records used only by adaptive plan ``/2``."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

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
        if self.kind not in {"data", "control", "lifecycle"}:
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
        if isinstance(self.logical_nodes, (str, bytes)):
            raise ValueError("PMADP403: physical unit logical_nodes must be an array")
        nodes = tuple(self.logical_nodes)
        if any(not isinstance(node, str) or not node.strip() for node in nodes):
            raise ValueError("PMADP403: physical unit logical_nodes must be non-blank")
        if len(set(nodes)) != len(nodes):
            raise ValueError("PMADP403: physical unit logical_nodes must be unique")
        if isinstance(self.dependencies, (str, bytes)):
            raise ValueError("PMADP402: physical unit dependencies must be an array")
        dependencies = tuple(
            dep
            if isinstance(dep, PhysicalDependency)
            else PhysicalDependency.from_dict(dep)
            for dep in self.dependencies
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
            dependencies=tuple(
                PhysicalDependency.from_dict(item)
                for item in data.get("dependencies", ())
            ),
            target_identity=data["target_identity"],
            logical_nodes=tuple(data.get("logical_nodes", ())),
            input_contracts=tuple(data.get("input_contracts", ())),
            output_contracts=tuple(data.get("output_contracts", ())),
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
        units = tuple(
            unit if isinstance(unit, PhysicalUnit) else PhysicalUnit.from_dict(unit)
            for unit in self.units
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
        order = tuple(self.topological_order)
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
        object.__setattr__(self, "units", units)
        object.__setattr__(self, "logical_to_physical", deep_freeze(mapping))
        object.__setattr__(self, "topological_order", order)

    def to_dict(self) -> dict[str, Any]:
        return {
            "units": [unit.to_dict() for unit in self.units],
            "logical_to_physical": mutable_copy(self.logical_to_physical),
            "topological_order": list(self.topological_order),
        }

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
        units = tuple(PhysicalUnit.from_dict(item) for item in data.get("units", ()))
        mapping = data.get("logical_to_physical", {})
        if not isinstance(mapping, Mapping):
            raise ValueError("PMADP403: logical_to_physical must be an object")
        return cls(
            units=units,
            logical_to_physical=mapping,
            topological_order=tuple(data.get("topological_order", ())),
        )


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
    if isinstance(value, (str, bytes)):
        raise ValueError(f"PMADP400: {label} must be an array")
    result: list[dict[str, Any]] = []
    for item in value:
        result.append(_validated_object_mapping(item, f"{label} item"))
    return tuple(result)
