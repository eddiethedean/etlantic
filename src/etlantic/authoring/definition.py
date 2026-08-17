"""Canonical unresolved pipeline definition (schema etlantic.pipeline/1).

``PipelineDefinition`` is the authoring-complete, data-only model shared by
class authoring, functional builders, JSON documents, and visual editors.
It is intentionally distinct from resolved ``etlantic.plan/1``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from etlantic.plan.freeze import deep_freeze, immutable_mapping, mutable_copy

PIPELINE_SCHEMA = "etlantic.pipeline/1"


def _empty_map() -> MappingProxyType[str, Any]:
    return MappingProxyType({})


@dataclass(frozen=True, slots=True)
class FieldSpec:
    """A single field on an embedded data contract."""

    name: str
    type: str
    nullable: bool = False
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "nullable": self.nullable,
            "required": self.required,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> FieldSpec:
        return cls(
            name=str(data["name"]),
            type=str(data["type"]),
            nullable=bool(data.get("nullable", False)),
            required=bool(data.get("required", True)),
        )


@dataclass(frozen=True, slots=True)
class ContractDefinition:
    """Embedded data-contract schema (no Python type object)."""

    identity: str
    name: str
    version: str | None = None
    authoring_id: str | None = None
    fields: tuple[FieldSpec, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=_empty_map)

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity,
            "name": self.name,
            "version": self.version,
            "authoring_id": self.authoring_id,
            "fields": [f.to_dict() for f in self.fields],
            "metadata": mutable_copy(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ContractDefinition:
        fields_raw = data.get("fields") or ()
        return cls(
            identity=str(data["identity"]),
            name=str(data["name"]),
            version=(str(data["version"]) if data.get("version") is not None else None),
            authoring_id=(
                str(data["authoring_id"])
                if data.get("authoring_id") is not None
                else None
            ),
            fields=tuple(FieldSpec.from_dict(f) for f in fields_raw),
            metadata=immutable_mapping(dict(data.get("metadata") or {})),
        )


@dataclass(frozen=True, slots=True)
class PortDefinitionSpec:
    """Port or parameter declaration on a node or transformation."""

    name: str
    direction: str  # "input" | "output" | "parameter"
    contract_id: str | None = None
    value_type: str | None = None
    default: Any = ...
    has_default: bool = False
    value: Any = ...
    has_value: bool = False
    role: str = "valid"
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "direction": self.direction,
            "contract_id": self.contract_id,
            "value_type": self.value_type,
            "has_default": self.has_default,
            "has_value": self.has_value,
            "role": self.role,
            "required": self.required,
        }
        if self.has_default and self.default is not ...:
            payload["default"] = mutable_copy(self.default)
        if self.has_value and self.value is not ...:
            payload["value"] = mutable_copy(self.value)
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PortDefinitionSpec:
        has_default = bool(data.get("has_default", False))
        has_value = bool(data.get("has_value", False))
        return cls(
            name=str(data["name"]),
            direction=str(data["direction"]),
            contract_id=(
                str(data["contract_id"])
                if data.get("contract_id") is not None
                else None
            ),
            value_type=(
                str(data["value_type"]) if data.get("value_type") is not None else None
            ),
            default=data.get("default", ...) if has_default else ...,
            has_default=has_default,
            value=data.get("value", ...) if has_value else ...,
            has_value=has_value,
            role=str(data.get("role") or "valid"),
            required=bool(data.get("required", True)),
        )


@dataclass(frozen=True, slots=True)
class ImplementationRef:
    """Stable reference to a native or portable implementation (no callable)."""

    engine: str
    identity: str
    kind: str = "native"
    is_async: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "identity": self.identity,
            "kind": self.kind,
            "is_async": self.is_async,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ImplementationRef:
        return cls(
            engine=str(data["engine"]),
            identity=str(data["identity"]),
            kind=str(data.get("kind") or "native"),
            is_async=bool(data.get("is_async", False)),
        )


@dataclass(frozen=True, slots=True)
class TransformationDefinition:
    """Transformation interface embedded in a pipeline definition."""

    identity: str
    name: str
    version: str | None = None
    ports: tuple[PortDefinitionSpec, ...] = ()
    implementation_refs: tuple[ImplementationRef, ...] = ()
    portable_plan: Mapping[str, Any] | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_map)

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity,
            "name": self.name,
            "version": self.version,
            "ports": [p.to_dict() for p in self.ports],
            "implementation_refs": [r.to_dict() for r in self.implementation_refs],
            "portable_plan": (
                mutable_copy(self.portable_plan)
                if self.portable_plan is not None
                else None
            ),
            "metadata": mutable_copy(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> TransformationDefinition:
        portable = data.get("portable_plan")
        return cls(
            identity=str(data["identity"]),
            name=str(data["name"]),
            version=(str(data["version"]) if data.get("version") is not None else None),
            ports=tuple(
                PortDefinitionSpec.from_dict(p) for p in (data.get("ports") or ())
            ),
            implementation_refs=tuple(
                ImplementationRef.from_dict(r)
                for r in (data.get("implementation_refs") or ())
            ),
            portable_plan=(
                immutable_mapping(dict(portable))
                if isinstance(portable, Mapping)
                else None
            ),
            metadata=immutable_mapping(dict(data.get("metadata") or {})),
        )


@dataclass(frozen=True, slots=True)
class EdgeDefinition:
    """Data-flow edge between node ports."""

    producer_node: str
    producer_port: str
    consumer_node: str
    consumer_port: str
    producer_contract_id: str | None = None
    consumer_contract_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "producer_node": self.producer_node,
            "producer_port": self.producer_port,
            "consumer_node": self.consumer_node,
            "consumer_port": self.consumer_port,
            "producer_contract_id": self.producer_contract_id,
            "consumer_contract_id": self.consumer_contract_id,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> EdgeDefinition:
        return cls(
            producer_node=str(data["producer_node"]),
            producer_port=str(data["producer_port"]),
            consumer_node=str(data["consumer_node"]),
            consumer_port=str(data["consumer_port"]),
            producer_contract_id=(
                str(data["producer_contract_id"])
                if data.get("producer_contract_id") is not None
                else None
            ),
            consumer_contract_id=(
                str(data["consumer_contract_id"])
                if data.get("consumer_contract_id") is not None
                else None
            ),
        )


@dataclass(frozen=True, slots=True)
class NodeDefinition:
    """A node in an unresolved pipeline definition."""

    name: str
    kind: str  # source | step | sink | subpipeline | map | reduce | conditional | failure | compensation
    identity: str
    asset: str | None = None
    contract_id: str | None = None
    transformation_id: str | None = None
    transformation_name: str | None = None
    inputs: tuple[PortDefinitionSpec, ...] = ()
    outputs: tuple[PortDefinitionSpec, ...] = ()
    parameters: tuple[PortDefinitionSpec, ...] = ()
    nested: PipelineDefinition | None = None
    nested_pipeline_id: str | None = None
    bindings: Mapping[str, Any] = field(default_factory=_empty_map)
    metadata: Mapping[str, Any] = field(default_factory=_empty_map)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "identity": self.identity,
            "asset": self.asset,
            "contract_id": self.contract_id,
            "transformation_id": self.transformation_id,
            "transformation_name": self.transformation_name,
            "inputs": [p.to_dict() for p in self.inputs],
            "outputs": [p.to_dict() for p in self.outputs],
            "parameters": [p.to_dict() for p in self.parameters],
            "nested": self.nested.to_dict() if self.nested is not None else None,
            "nested_pipeline_id": self.nested_pipeline_id,
            "bindings": mutable_copy(self.bindings),
            "metadata": mutable_copy(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> NodeDefinition:
        nested_raw = data.get("nested")
        nested = None
        if isinstance(nested_raw, Mapping):
            from etlantic.authoring.upgrade import upgrade_pipeline_dict

            upgraded = upgrade_pipeline_dict(dict(nested_raw))
            nested = PipelineDefinition.from_dict(upgraded)
            if nested.schema != PIPELINE_SCHEMA:
                raise ValueError(
                    f"Nested pipeline schema {nested.schema!r} is not "
                    f"{PIPELINE_SCHEMA!r}"
                )
        return cls(
            name=str(data["name"]),
            kind=str(data["kind"]),
            identity=str(data["identity"]),
            asset=(str(data["asset"]) if data.get("asset") is not None else None),
            contract_id=(
                str(data["contract_id"])
                if data.get("contract_id") is not None
                else None
            ),
            transformation_id=(
                str(data["transformation_id"])
                if data.get("transformation_id") is not None
                else None
            ),
            transformation_name=(
                str(data["transformation_name"])
                if data.get("transformation_name") is not None
                else None
            ),
            inputs=tuple(
                PortDefinitionSpec.from_dict(p) for p in (data.get("inputs") or ())
            ),
            outputs=tuple(
                PortDefinitionSpec.from_dict(p) for p in (data.get("outputs") or ())
            ),
            parameters=tuple(
                PortDefinitionSpec.from_dict(p) for p in (data.get("parameters") or ())
            ),
            nested=nested,
            nested_pipeline_id=(
                str(data["nested_pipeline_id"])
                if data.get("nested_pipeline_id") is not None
                else None
            ),
            bindings=immutable_mapping(dict(data.get("bindings") or {})),
            metadata=immutable_mapping(dict(data.get("metadata") or {})),
        )


@dataclass(frozen=True, slots=True)
class PipelineDefinition:
    """Immutable, unresolved, authoring-complete pipeline model.

    Shared by class authoring, functional builders, JSON documents, and visual
    editors. Distinct from resolved ``etlantic.plan/1`` (``PipelinePlan``).
    """

    pipeline_id: str
    pipeline_name: str
    schema: str = PIPELINE_SCHEMA
    version: str | None = None
    fingerprint: str | None = None
    contracts: tuple[ContractDefinition, ...] = ()
    transformations: tuple[TransformationDefinition, ...] = ()
    nodes: tuple[NodeDefinition, ...] = ()
    edges: tuple[EdgeDefinition, ...] = ()
    profile_ref: str | None = None
    policy_refs: Mapping[str, Any] = field(default_factory=_empty_map)
    reliability: Mapping[str, Any] = field(default_factory=_empty_map)
    provenance: Mapping[str, Any] = field(default_factory=_empty_map)
    extensions: Mapping[str, Any] = field(default_factory=_empty_map)
    metadata: Mapping[str, Any] = field(default_factory=_empty_map)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict (includes fingerprint when set).

        Returns:
            Mapping suitable for JSON codecs. Prefer
            ``etlantic.authoring.pipeline_to_dict`` when sealing a fingerprint.
        """
        return {
            "schema": self.schema,
            "pipeline_id": self.pipeline_id,
            "pipeline_name": self.pipeline_name,
            "version": self.version,
            "fingerprint": self.fingerprint,
            "contracts": [c.to_dict() for c in self.contracts],
            "transformations": [t.to_dict() for t in self.transformations],
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "profile_ref": self.profile_ref,
            "policy_refs": mutable_copy(self.policy_refs),
            "reliability": mutable_copy(self.reliability),
            "provenance": mutable_copy(self.provenance),
            "extensions": mutable_copy(self.extensions),
            "metadata": mutable_copy(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PipelineDefinition:
        """Deserialize from a dict without fingerprint verify or schema upgrade.

        Args:
            data: Mapping with at least ``pipeline_id`` and ``pipeline_name``.

        Returns:
            An immutable ``PipelineDefinition``.

        Raises:
            KeyError: If required keys (including ``schema``) are missing.
            TypeError: If nested values have unexpected types.

        Note:
            Prefer ``etlantic.authoring.pipeline_from_dict`` for verified
            interchange (upgrade + fingerprint). ``from_dict`` requires an
            explicit ``schema`` and does not invent the current schema id.
        """
        if "schema" not in data or data["schema"] in (None, ""):
            raise KeyError("schema")
        defn = cls(
            schema=str(data["schema"]),
            pipeline_id=str(data["pipeline_id"]),
            pipeline_name=str(data["pipeline_name"]),
            version=(str(data["version"]) if data.get("version") is not None else None),
            fingerprint=(
                str(data["fingerprint"])
                if data.get("fingerprint") is not None
                else None
            ),
            contracts=tuple(
                ContractDefinition.from_dict(c) for c in (data.get("contracts") or ())
            ),
            transformations=tuple(
                TransformationDefinition.from_dict(t)
                for t in (data.get("transformations") or ())
            ),
            nodes=tuple(NodeDefinition.from_dict(n) for n in (data.get("nodes") or ())),
            edges=tuple(EdgeDefinition.from_dict(e) for e in (data.get("edges") or ())),
            profile_ref=(
                str(data["profile_ref"])
                if data.get("profile_ref") is not None
                else None
            ),
            policy_refs=immutable_mapping(dict(data.get("policy_refs") or {})),
            reliability=immutable_mapping(dict(data.get("reliability") or {})),
            provenance=immutable_mapping(dict(data.get("provenance") or {})),
            extensions=immutable_mapping(dict(data.get("extensions") or {})),
            metadata=immutable_mapping(dict(data.get("metadata") or {})),
        )
        object.__setattr__(defn, "policy_refs", deep_freeze(defn.policy_refs))
        object.__setattr__(defn, "reliability", deep_freeze(defn.reliability))
        object.__setattr__(defn, "provenance", deep_freeze(defn.provenance))
        object.__setattr__(defn, "extensions", deep_freeze(defn.extensions))
        object.__setattr__(defn, "metadata", deep_freeze(defn.metadata))
        return defn

    def with_fingerprint(self, fingerprint: str) -> PipelineDefinition:
        """Return a copy with ``fingerprint`` set.

        Args:
            fingerprint: SHA-256 hex digest from ``pipeline_fingerprint``.

        Returns:
            A new frozen ``PipelineDefinition`` with the fingerprint sealed.
        """
        return PipelineDefinition(
            schema=self.schema,
            pipeline_id=self.pipeline_id,
            pipeline_name=self.pipeline_name,
            version=self.version,
            fingerprint=fingerprint,
            contracts=self.contracts,
            transformations=self.transformations,
            nodes=self.nodes,
            edges=self.edges,
            profile_ref=self.profile_ref,
            policy_refs=self.policy_refs,
            reliability=self.reliability,
            provenance=self.provenance,
            extensions=self.extensions,
            metadata=self.metadata,
        )


# Forward reference for nested PipelineDefinition on NodeDefinition
NodeDefinition.__annotations__["nested"] = PipelineDefinition | None
