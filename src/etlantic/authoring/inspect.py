"""Public definition inspection, rewrite, and provenance helpers (0.35).

These APIs are bounded and secret-free: they never resolve secrets, never
import untrusted code, never retain source rows, and never mutate target
storage. Medallantic migration tooling and facades should prefer these names
over private authoring internals.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from hashlib import sha256
from types import MappingProxyType
from typing import Any, Literal

from etlantic.authoring.definition import PipelineDefinition
from etlantic.authoring.edits import EditCommand, EditResult, apply_edit
from etlantic.authoring.serialize import pipeline_fingerprint
from etlantic.extensions import (
    facade_provenance,
    validate_extension_metadata,
)
from etlantic.plan.freeze import immutable_mapping

# Facade compatibility negotiation version (Medallantic ↔ ETLantic).
FACADE_PROTOCOL_VERSION = "1"

DEFINITION_PROVENANCE_EXTENSION_KEY = "etlantic.definition_provenance"

_FORBIDDEN_SUMMARY_KEYS = frozenset(
    {
        "rows",
        "records",
        "data",
        "payload",
        "password",
        "secret",
        "token",
        "credential",
        "dsn",
        "connection_string",
    }
)


@dataclass(frozen=True, slots=True)
class DefinitionInspection:
    """Secret-free structural summary of a ``PipelineDefinition``."""

    schema: str
    pipeline_id: str
    pipeline_name: str
    fingerprint: str | None
    node_names: tuple[str, ...]
    node_kinds: Mapping[str, str]
    assets: tuple[str, ...]
    contract_fingerprints: Mapping[str, str]
    edge_count: int
    facade_protocol_version: str | None = None
    generator_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the inspection (JSON-friendly, no source rows)."""
        return {
            "schema": self.schema,
            "pipeline_id": self.pipeline_id,
            "pipeline_name": self.pipeline_name,
            "fingerprint": self.fingerprint,
            "node_names": list(self.node_names),
            "node_kinds": dict(self.node_kinds),
            "assets": list(self.assets),
            "contract_fingerprints": dict(self.contract_fingerprints),
            "edge_count": self.edge_count,
            "facade_protocol_version": self.facade_protocol_version,
            "generator_id": self.generator_id,
        }


@dataclass(frozen=True, slots=True)
class DefinitionProvenance:
    """Generated-definition provenance stored under extension namespaces."""

    generator_id: str
    source_fingerprint: str | None = None
    facade_protocol_version: str = FACADE_PROTOCOL_VERSION
    facade_identity: str | None = None
    extras: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "generator_id": self.generator_id,
            "source_fingerprint": self.source_fingerprint,
            "facade_protocol_version": self.facade_protocol_version,
        }
        if self.facade_identity is not None:
            payload["facade_identity"] = self.facade_identity
        if self.extras:
            payload["extras"] = dict(self.extras)
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DefinitionProvenance:
        extras = data.get("extras") or {}
        if not isinstance(extras, Mapping):
            raise TypeError("extras must be a mapping")
        return cls(
            generator_id=str(data["generator_id"]),
            source_fingerprint=(
                str(data["source_fingerprint"])
                if data.get("source_fingerprint") is not None
                else None
            ),
            facade_protocol_version=str(
                data.get("facade_protocol_version") or FACADE_PROTOCOL_VERSION
            ),
            facade_identity=(
                str(data["facade_identity"])
                if data.get("facade_identity") is not None
                else None
            ),
            extras=immutable_mapping(dict(extras)),
        )


def negotiate_facade_protocol(
    requested: str | None,
    *,
    supported: Sequence[str] = (FACADE_PROTOCOL_VERSION,),
) -> str:
    """Negotiate facade protocol version; fail closed on mismatch.

    Args:
        requested: Client/facade requested protocol version (or None for latest).
        supported: Host-supported protocol versions (newest last).

    Returns:
        The negotiated protocol version string.

    Raises:
        ValueError: When ``requested`` is not in ``supported``.
    """
    if not supported:
        raise ValueError("supported facade protocol versions must be non-empty")
    if requested is None:
        return str(supported[-1])
    req = str(requested)
    if req not in {str(v) for v in supported}:
        raise ValueError(
            f"Unsupported facade protocol version {req!r}; "
            f"supported={list(supported)!r}"
        )
    return req


def _contract_fingerprint(contract_identity: str, fields: Sequence[Any]) -> str:
    parts = [contract_identity]
    for field_spec in fields:
        parts.append(
            f"{getattr(field_spec, 'name', '')}:"
            f"{getattr(field_spec, 'type', '')}:"
            f"{int(bool(getattr(field_spec, 'nullable', False)))}:"
            f"{int(bool(getattr(field_spec, 'required', True)))}"
        )
    digest = sha256("|".join(parts).encode("utf-8")).hexdigest()
    return digest


def _read_extension_provenance(
    defn: PipelineDefinition,
) -> DefinitionProvenance | None:
    blob = dict(defn.extensions or {}).get(DEFINITION_PROVENANCE_EXTENSION_KEY)
    if isinstance(blob, Mapping) and blob.get("generator_id"):
        return DefinitionProvenance.from_dict(blob)
    return None


def inspect_definition(defn: PipelineDefinition) -> DefinitionInspection:
    """Return a secret-free structural summary of a pipeline definition.

    Does not resolve secrets, import callables, read source rows, or mutate
    storage. Contract summaries are fingerprints only.

    Args:
        defn: Immutable pipeline definition.

    Returns:
        ``DefinitionInspection`` suitable for migration reports and tooling.
    """
    if not isinstance(defn, PipelineDefinition):
        raise TypeError(
            f"inspect_definition expects PipelineDefinition, got {type(defn)!r}"
        )
    node_names = tuple(n.name for n in defn.nodes)
    node_kinds = {n.name: str(n.kind) for n in defn.nodes}
    assets = tuple(sorted({n.asset for n in defn.nodes if n.asset}))
    contract_fps = {
        c.identity: _contract_fingerprint(c.identity, c.fields) for c in defn.contracts
    }
    prov = _read_extension_provenance(defn)
    facade_proto: str | None = None
    generator_id: str | None = None
    if prov is not None:
        facade_proto = prov.facade_protocol_version
        generator_id = prov.generator_id
    elif defn.provenance:
        raw_prov = dict(defn.provenance)
        if raw_prov.get("kind") == "facade":
            facade_proto = str(
                raw_prov.get("facade_protocol_version") or FACADE_PROTOCOL_VERSION
            )
    summary = DefinitionInspection(
        schema=str(defn.schema),
        pipeline_id=str(defn.pipeline_id),
        pipeline_name=str(defn.pipeline_name),
        fingerprint=defn.fingerprint or pipeline_fingerprint(defn),
        node_names=node_names,
        node_kinds=MappingProxyType(node_kinds),
        assets=assets,
        contract_fingerprints=MappingProxyType(contract_fps),
        edge_count=len(defn.edges),
        facade_protocol_version=facade_proto,
        generator_id=generator_id,
    )
    # Guard: ensure summary dict stays free of forbidden bulk/secret keys.
    as_dict = summary.to_dict()
    for key in as_dict:
        if str(key).lower() in _FORBIDDEN_SUMMARY_KEYS:
            raise ValueError(f"Inspection summary must not include key {key!r}")
    return summary


def rewrite_definition(
    defn: PipelineDefinition,
    edits: Sequence[EditCommand] | EditCommand,
    *,
    expected_token: str | None = None,
) -> EditResult:
    """Apply one or more documented ``EditCommand``s and refresh the fingerprint.

    Fails closed on invalid edits and optimistic-concurrency mismatches.
    Does not resolve secrets or import untrusted code.

    Args:
        defn: Current pipeline definition.
        edits: A single command or an ordered sequence of commands.
        expected_token: Optional concurrency token for the first edit.

    Returns:
        ``EditResult`` for the final definition after all edits.
    """
    if not isinstance(defn, PipelineDefinition):
        raise TypeError(
            f"rewrite_definition expects PipelineDefinition, got {type(defn)!r}"
        )
    commands: Sequence[EditCommand]
    commands = (edits,) if isinstance(edits, EditCommand) else tuple(edits)
    if not commands:
        raise ValueError("rewrite_definition requires at least one EditCommand")
    current = defn
    token = expected_token
    result: EditResult | None = None
    for command in commands:
        if not isinstance(command, EditCommand):
            raise TypeError(
                f"edits must be EditCommand instances, got {type(command)!r}"
            )
        result = apply_edit(current, command, expected_token=token)
        current = result.definition
        token = result.fingerprint
    assert result is not None
    return result


def definition_provenance(
    defn: PipelineDefinition | None = None,
    *,
    generator_id: str | None = None,
    source_fingerprint: str | None = None,
    facade_protocol_version: str | None = None,
    facade_identity: str | None = None,
    extras: Mapping[str, Any] | None = None,
    action: Literal["attach", "read"] = "attach",
) -> PipelineDefinition | DefinitionProvenance | None:
    """Attach or read generated-definition provenance in extension namespaces.

    Provenance is stored under ``extensions['etlantic.definition_provenance']``
    only (plus optional ``PipelineDefinition.provenance`` facade stamp). Never
    stores source rows or secret material.

    Args:
        defn: Definition to attach to or read from.
        generator_id: Required when ``action='attach'``.
        source_fingerprint: Fingerprint of the migration source artifact.
        facade_protocol_version: Negotiated facade protocol (default ``1``).
        facade_identity: Optional facade package identity (e.g. ``medallantic``).
        extras: Optional JSON-serializable extras (namespaced validation applied).
        action: ``attach`` returns an updated definition; ``read`` returns
            ``DefinitionProvenance`` or ``None``.

    Returns:
        Updated ``PipelineDefinition``, ``DefinitionProvenance``, or ``None``.
    """
    if action == "read":
        if defn is None:
            raise TypeError("definition_provenance(action='read') requires defn")
        return _read_extension_provenance(defn)

    if defn is None:
        raise TypeError("definition_provenance(action='attach') requires defn")
    if not generator_id:
        raise ValueError("generator_id is required when attaching provenance")
    proto = negotiate_facade_protocol(
        facade_protocol_version,
        supported=(FACADE_PROTOCOL_VERSION,),
    )
    prov = DefinitionProvenance(
        generator_id=str(generator_id),
        source_fingerprint=source_fingerprint,
        facade_protocol_version=proto,
        facade_identity=facade_identity,
        extras=immutable_mapping(dict(extras or {})),
    )
    payload = prov.to_dict()
    validate_extension_metadata(
        {DEFINITION_PROVENANCE_EXTENSION_KEY: payload},
        path="extensions",
        strict=True,
    )
    extensions = dict(defn.extensions or {})
    extensions[DEFINITION_PROVENANCE_EXTENSION_KEY] = payload
    provenance_map = dict(defn.provenance or {})
    if facade_identity:
        provenance_map.update(
            facade_provenance(identity=str(facade_identity), version=None)
        )
        provenance_map["facade_protocol_version"] = proto
    updated = replace(
        defn,
        extensions=immutable_mapping(extensions),
        provenance=immutable_mapping(provenance_map),
        fingerprint=None,
    )
    return updated.with_fingerprint(pipeline_fingerprint(updated))
