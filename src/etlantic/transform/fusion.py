"""Immutable data-only descriptors for the bounded Polars scan composition.

Descriptors prove syntax and wiring, not execution qualification or maturity.
No native queries, objects or filesystem access are part of this protocol.
"""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Protocol, runtime_checkable

import dtcs

from etlantic.plan.freeze import deep_freeze, mutable_copy
from etlantic.transform.compiler import (
    CompiledTransform,
    TransformCompileContext,
    TransformPlanningContext,
    TransformSupportReport,
)

FUSION_SCHEMA = "etlantic.portable_fusion/1"
SOURCE_SCHEMA = "etlantic.polars_parquet_source/1"
FUSION_SIGNATURE = "scan-filter-project-chain/1:polars-pandas"


def fusion_digest(value: Any) -> str:
    """Hash canonical data; never invoke provider serialization hooks."""
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                mutable_copy(value),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode()
        ).hexdigest()
    )


PARQUET_CAPABILITY_EVIDENCE = fusion_digest(
    {
        "schema": SOURCE_SCHEMA,
        "implementation": "bounded-local-snapshot/1",
        "types": ["boolean", "int64"],
        "columns": 8,
        "max_bytes": 256 * 1024 * 1024,
        "max_rows": 1_000_000,
        "pushdown": ["predicate", "projection"],
    }
)


def parquet_source_location(location: Any) -> PurePosixPath:
    """Validate a single logical location without resolving or opening it."""
    if type(location) is not str or not location or len(location) > 4096:
        raise ValueError("Parquet source requires a single relative file")
    if any(char in location for char in "\\:*?[]\x00") or location.startswith("~"):
        raise ValueError("Parquet source requires a single relative file")
    path = PurePosixPath(location)
    if path.is_absolute() or ".." in path.parts or path.suffix != ".parquet":
        raise ValueError("Parquet source requires a single relative file")
    return path


def _closed(value: Mapping[str, Any], fields: set[str]) -> None:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise ValueError("PMADP403: invalid closed fusion descriptor")


def _identifier(value: Any) -> None:
    if type(value) is not str or not value or len(value) > 4096:
        raise ValueError("PMADP403: invalid fusion identity")


def _contract(value: Mapping[str, Any]) -> None:
    _closed(value, {"id", "fingerprint", "fields"})
    _identifier(value["id"])
    _identifier(value["fingerprint"])
    fields = value["fields"]
    if not isinstance(fields, Mapping) or not 0 < len(fields) <= 8:
        raise ValueError("PMADP403: invalid fusion contract fields")
    for name, dtype in fields.items():
        _identifier(name)
        if dtype not in {"int64", "boolean"}:
            raise ValueError("PMADP403: unsupported fusion contract type")


def _contract_wire(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": value["id"],
        "fingerprint": value["fingerprint"],
        "etlantic.fields": [
            {"column": name, "dtype": dtype}
            for name, dtype in sorted(value["fields"].items())
        ],
    }


def _contract_from_wire(value: Mapping[str, Any]) -> dict[str, Any]:
    _closed(value, {"id", "fingerprint", "etlantic.fields"})
    records = value["etlantic.fields"]
    if not isinstance(records, (list, tuple)) or not 0 < len(records) <= 8:
        raise ValueError("PMADP403: invalid fusion schema fields")
    fields = {}
    for record in records:
        _closed(record, {"column", "dtype"})
        name = record["column"]
        _identifier(name)
        if name in fields:
            raise ValueError("PMADP403: duplicate fusion schema column")
        fields[name] = record["dtype"]
    result = {"id": value["id"], "fingerprint": value["fingerprint"], "fields": fields}
    _contract(result)
    return result


@dataclass(frozen=True, slots=True)
class FusionMember:
    """One original portable transformation and its typed logical route."""

    logical_node: str
    upstream_node: str
    upstream_port: str
    input_port: str
    output_port: str
    input_contract: Mapping[str, Any]
    output_contract: Mapping[str, Any]
    definition: Mapping[str, Any]
    ir_fingerprint: str

    def __post_init__(self) -> None:
        for value in (
            self.logical_node,
            self.upstream_node,
            self.upstream_port,
            self.input_port,
            self.output_port,
            self.ir_fingerprint,
        ):
            _identifier(value)
        _contract(self.input_contract)
        _contract(self.output_contract)
        from etlantic.planning.adaptive_budget import canonical_size

        if canonical_size(self.definition) > 256 * 1024:
            raise ValueError("PMADP403: fusion member exceeds descriptor bounds")
        definition = mutable_copy(self.definition)
        _closed(
            definition,
            {
                "planIdentity",
                "profile",
                "specificationVersion",
                "registryVersions",
                "transformation",
                "inputs",
                "outputs",
                "parameters",
                "actions",
                "rules",
                "lineage",
                "requirements",
                "errorMode",
            },
        )
        if len(json.dumps(definition).encode()) > 256 * 1024:
            raise ValueError("PMADP403: fusion member exceeds descriptor bounds")
        if dtcs.plan_fingerprint(definition) != self.ir_fingerprint:
            raise ValueError("PMADP403: fusion member IR fingerprint mismatch")
        if (
            definition.get("planIdentity") != "dtcs.transform-plan/2"
            or set(definition.get("inputs", {})) != {self.input_port}
            or set(definition.get("outputs", {})) != {self.output_port}
            or definition.get("rules")
            or definition.get("lineage")
            or definition.get("errorMode") != "fail"
            or len(definition.get("actions", [])) != 1
        ):
            raise ValueError("PMADP403: unsupported fusion member shape")
        action = definition["actions"][0]
        _closed(action, {"id", "kind", "objectRef"})
        kind = action.get("kind", {})
        if (
            kind.get("target") != self.input_port
            or kind.get("id") != action.get("id")
            or set(kind) != {"id", "kind", "action", "target", "parameters"}
            or kind.get("kind") != "semanticAction"
            or action.get("objectRef") != f"semanticActions.{action.get('id')}"
        ):
            raise ValueError("PMADP403: unsupported fusion action route")
        expected = [
            {"from": self.input_port, "reason": "fieldRead", "to": action["id"]},
            {"from": action["id"], "reason": "lineage", "to": self.output_port},
        ]
        if definition.get("requirements", {}).get("dependencies") != expected:
            raise ValueError("PMADP403: invalid fusion member lineage")
        for field in ("input_contract", "output_contract", "definition"):
            object.__setattr__(self, field, deep_freeze(getattr(self, field)))

    def to_dict(self) -> dict[str, Any]:
        """Encode the original IR using the stored implementation wire convention."""
        return {
            "logical_node": self.logical_node,
            "upstream_node": self.upstream_node,
            "upstream_port": self.upstream_port,
            "input_port": self.input_port,
            "output_port": self.output_port,
            "input_contract": _contract_wire(self.input_contract),
            "output_contract": _contract_wire(self.output_contract),
            "portable_plan_json": base64.b64encode(
                json.dumps(
                    mutable_copy(self.definition),
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).decode(),
            "ir_fingerprint": self.ir_fingerprint,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> FusionMember:
        fields = {
            "logical_node",
            "upstream_node",
            "upstream_port",
            "input_port",
            "output_port",
            "input_contract",
            "output_contract",
            "portable_plan_json",
            "ir_fingerprint",
        }
        _closed(value, fields)
        encoded = value["portable_plan_json"]
        if type(encoded) is not str or len(encoded) > 350_000:
            raise ValueError("PMADP403: invalid encoded fusion member")
        try:
            definition = json.loads(base64.b64decode(encoded, validate=True))
        except (ValueError, UnicodeError):
            raise ValueError("PMADP403: invalid encoded fusion member") from None
        return cls(
            **{
                k: value[k]
                for k in fields
                - {"portable_plan_json", "input_contract", "output_contract"}
            },
            input_contract=_contract_from_wire(value["input_contract"]),
            output_contract=_contract_from_wire(value["output_contract"]),
            definition=definition,
        )


@dataclass(frozen=True, slots=True)
class FusionDescriptor:
    """Exact source/filter/project composition with frozen identities and proofs."""

    source_node: str
    source_port: str
    source_binding: Mapping[str, Any]
    source_contract: Mapping[str, Any]
    target_identity: str
    compiler_name: str
    compiler_version: str
    compiler_evidence: str
    policy_digest: str
    members: tuple[FusionMember, ...]
    parameters: Mapping[str, int]
    proof_references: tuple[str, ...] = (PARQUET_CAPABILITY_EVIDENCE,)
    schema: str = FUSION_SCHEMA
    snapshot_strategy: str = "bounded-local-snapshot/1"

    def __post_init__(self) -> None:
        for value in (
            self.source_node,
            self.source_port,
            self.target_identity,
            self.compiler_name,
            self.compiler_version,
            self.compiler_evidence,
            self.policy_digest,
        ):
            _identifier(value)
        if (
            self.schema != FUSION_SCHEMA
            or self.snapshot_strategy != "bounded-local-snapshot/1"
        ):
            raise ValueError("PMADP403: invalid fusion protocol")
        _contract(self.source_contract)
        _closed(
            self.source_binding,
            {
                "binding",
                "provider",
                "kind",
                "location",
                "secret_ref",
                "metadata",
                "provider_version",
                "config_fingerprint",
                "format",
                "config",
                "root_ref",
            },
        )
        members = tuple(self.members)
        if len(members) != 2 or any(type(m) is not FusionMember for m in members):
            raise ValueError("PMADP403: fusion requires exactly two portable members")
        first, second = members
        if len({self.source_node, first.logical_node, second.logical_node}) != 3 or (
            first.upstream_node != self.source_node
            or first.upstream_port != self.source_port
            or second.upstream_node != first.logical_node
            or second.upstream_port != first.output_port
            or first.input_contract != self.source_contract
            or first.output_contract != first.input_contract
            or second.input_contract != first.output_contract
        ):
            raise ValueError("PMADP403: invalid typed fusion member route")
        binding = self.source_binding
        parquet_source_location(binding.get("location"))
        if binding.get("root_ref") != "workspace" or set(
            binding.get("metadata", {})
        ) != {"etlantic.parquet_capability_evidence"}:
            raise ValueError("PMADP403: unsupported fusion source root/metadata")
        config = binding.get("config", {})
        _closed(config, {"schema", "max_bytes", "max_rows"})
        if config["schema"] != SOURCE_SCHEMA:
            raise ValueError("PMADP403: invalid fusion source configuration")
        for key, maximum in (("max_bytes", 268435456), ("max_rows", 1000000)):
            if type(config[key]) is not int or not 0 < config[key] <= maximum:
                raise ValueError("PMADP403: invalid fusion source bounds")
        if (
            binding.get("provider") != "polars-parquet"
            or binding.get("format") != "parquet"
            or type(binding.get("provider_version")) is not str
            or not binding.get("provider_version")
            or binding.get("config_fingerprint") != fusion_digest(config)
            or binding.get("secret_ref") is not None
            or self.proof_references != (PARQUET_CAPABILITY_EVIDENCE,)
            or binding.get("metadata", {}).get("etlantic.parquet_capability_evidence")
            != PARQUET_CAPABILITY_EVIDENCE
        ):
            raise ValueError("PMADP403: fusion source identity/evidence mismatch")
        _check_operations(first, second, self.parameters)
        for field in ("source_binding", "source_contract", "parameters"):
            object.__setattr__(self, field, deep_freeze(getattr(self, field)))
        object.__setattr__(self, "members", members)

    @property
    def logical_nodes(self) -> tuple[str, ...]:
        return (self.source_node, *(member.logical_node for member in self.members))

    @property
    def internal_edges(self) -> tuple[tuple[str, str, str, str], ...]:
        return tuple(
            (m.upstream_node, m.logical_node, m.upstream_port, m.input_port)
            for m in self.members
        )

    @property
    def fingerprint(self) -> str:
        return fusion_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "snapshot_strategy": self.snapshot_strategy,
            "source_node": self.source_node,
            "source_port": self.source_port,
            "source_binding": mutable_copy(self.source_binding),
            "source_contract": _contract_wire(self.source_contract),
            "target_identity": self.target_identity,
            "compiler_name": self.compiler_name,
            "compiler_version": self.compiler_version,
            "compiler_evidence": self.compiler_evidence,
            "policy_digest": self.policy_digest,
            "members": {m.logical_node: m.to_dict() for m in self.members},
            "member_order": [m.logical_node for m in self.members],
            "parameters": mutable_copy(self.parameters),
            "proof_references": list(self.proof_references),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> FusionDescriptor:
        fields = {
            "schema",
            "snapshot_strategy",
            "source_node",
            "source_port",
            "source_binding",
            "source_contract",
            "target_identity",
            "compiler_name",
            "compiler_version",
            "compiler_evidence",
            "policy_digest",
            "members",
            "member_order",
            "parameters",
            "proof_references",
        }
        _closed(value, fields)
        order = value["member_order"]
        members = value["members"]
        if (
            not isinstance(order, (list, tuple))
            or len(order) != 2
            or any(type(name) is not str for name in order)
            or len(set(order)) != 2
            or not isinstance(members, Mapping)
            or set(members) != set(order)
        ):
            raise ValueError("PMADP403: invalid fusion member order")
        return cls(
            **{
                k: value[k]
                for k in fields
                - {"members", "member_order", "proof_references", "source_contract"}
            },
            source_contract=_contract_from_wire(value["source_contract"]),
            members=tuple(
                FusionMember.from_dict(value["members"][name])
                for name in value["member_order"]
            ),
            proof_references=tuple(value["proof_references"]),
        )


def _check_operations(
    first: FusionMember, second: FusionMember, parameters: Mapping[str, int]
) -> None:
    filter_kind = first.definition["actions"][0]["kind"]
    project_kind = second.definition["actions"][0]["kind"]
    predicate = filter_kind["parameters"].get("predicate", {})
    left, right = predicate.get("left", {}), predicate.get("right", {})
    if (
        filter_kind["action"] != "dtcs:filter"
        or set(filter_kind["parameters"]) != {"predicate"}
        or set(predicate) != {"kind", "op", "left", "right"}
        or predicate["kind"] != "binary"
        or predicate["op"] != "eq"
        or set(left) != {"kind", "target"}
        or left.get("kind") != "fieldRef"
        or first.input_contract["fields"].get(left.get("target")) != "int64"
        or set(right) != {"kind", "scope", "target"}
        or right.get("kind") != "fieldRef"
        or right.get("scope") != "parameter"
        or set(parameters) != {right.get("target")}
        or any(
            type(v) is not int or not -(2**63) <= v < 2**63 for v in parameters.values()
        )
        or first.definition.get("parameters")
        or second.definition.get("parameters")
        or project_kind["action"] != "dtcs:project"
        or set(project_kind["parameters"]) != {"fields"}
    ):
        raise ValueError("PMADP403: unsupported fusion operation or parameter")
    fields = project_kind["parameters"]["fields"]
    if (
        not isinstance(fields, (list, tuple))
        or not fields
        or any(type(name) is not str for name in fields)
        or len(set(fields)) != len(fields)
        or any(name not in second.input_contract["fields"] for name in fields)
        or set(second.output_contract["fields"]) != set(fields)
        or any(
            second.output_contract["fields"][name]
            != second.input_contract["fields"][name]
            for name in fields
        )
        or len(fields) >= len(second.input_contract["fields"])
    ):
        raise ValueError("PMADP403: unsupported fusion projection")


def compose_fusion_definition(descriptor: FusionDescriptor) -> dict[str, Any]:
    """Alpha-rename only bound identities; never rewrite user column names."""
    first, second = descriptor.members
    definition = mutable_copy(first.definition)
    definition["transformation"] = f"fusion:{descriptor.fingerprint}"
    input_id, filter_id, project_id = "fusion_source", "fusion_filter", "fusion_project"
    definition["inputs"] = {
        input_id: {
            **definition["inputs"][first.input_port],
            "id": input_id,
        }
    }
    actions = []
    for member, target, identity in (
        (first, input_id, filter_id),
        (second, filter_id, project_id),
    ):
        action = mutable_copy(member.definition["actions"][0])
        action.update(id=identity, objectRef=f"semanticActions.{identity}")
        action["kind"].update(id=identity, target=target)
        actions.append(action)
    definition["actions"] = actions
    definition["outputs"] = mutable_copy(second.definition["outputs"])
    definition["requirements"]["dependencies"] = [
        {"from": input_id, "to": filter_id, "reason": "fieldRead"},
        {"from": filter_id, "to": project_id, "reason": "fieldRead"},
        {"from": project_id, "to": second.output_port, "reason": "lineage"},
    ]
    return definition


@runtime_checkable
class PortableFusionCompiler(Protocol):
    """Optional additive protocol; ordinary compiler support is unchanged."""

    def analyze_fusion(
        self, descriptor: FusionDescriptor, *, context: TransformPlanningContext
    ) -> TransformSupportReport: ...

    def compile_fusion(
        self, descriptor: FusionDescriptor, *, context: TransformCompileContext
    ) -> CompiledTransform: ...


__all__ = ["FusionDescriptor", "FusionMember", "PortableFusionCompiler"]
