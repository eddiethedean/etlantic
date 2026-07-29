"""Schema drift models: normalized schema, observations, changes, impact (0.3)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from etlantic.contracts import Data, is_data_contract_type


class DriftImpact(StrEnum):
    """Impact vocabulary for schema changes."""

    INFORMATIONAL = "informational"
    COMPATIBLE = "compatible"
    CONDITIONALLY_COMPATIBLE = "conditionally_compatible"
    BREAKING = "breaking"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class NormalizedField:
    """Normalized field definition."""

    name: str
    logical_type: str
    required: bool = True
    nullable: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize field."""
        return {
            "name": self.name,
            "logical_type": self.logical_type,
            "required": self.required,
            "nullable": self.nullable,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class NormalizedSchema:
    """Versioned normalized schema representation."""

    identity: str
    fields: tuple[NormalizedField, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def fingerprint(self) -> str:
        """Deterministic fingerprint of logical schema (ignores physical metadata)."""
        payload = {
            "identity": self.identity,
            "fields": [
                {
                    "name": f.name,
                    "logical_type": f.logical_type,
                    "required": f.required,
                    "nullable": f.nullable,
                }
                for f in sorted(self.fields, key=lambda x: x.name)
            ],
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(raw).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Serialize schema."""
        return {
            "identity": self.identity,
            "fields": [f.to_dict() for f in self.fields],
            "fingerprint": self.fingerprint(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NormalizedSchema:
        """Deserialize a normalized schema (fingerprint is recomputed)."""
        fields = tuple(
            NormalizedField(
                name=str(item["name"]),
                logical_type=str(item.get("logical_type") or "unknown"),
                required=bool(item.get("required", True)),
                nullable=bool(item.get("nullable", False)),
                metadata=dict(item.get("metadata") or {}),
            )
            for item in (data.get("fields") or ())
            if isinstance(item, dict)
        )
        return cls(
            identity=str(data.get("identity") or ""),
            fields=fields,
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True, slots=True)
class SchemaObservation:
    """Immutable schema observation (no row data or secrets)."""

    subject_id: str
    schema: NormalizedSchema
    observed_at: str | None = None
    profile: str | None = None
    environment: str | None = None
    pipeline_id: str | None = None
    plan_id: str | None = None
    inspector: str | None = None
    confidence: float | None = None
    security_domain: str = "default"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize observation."""
        return {
            "subject_id": self.subject_id,
            "schema": self.schema.to_dict(),
            "observed_at": self.observed_at,
            "profile": self.profile,
            "environment": self.environment,
            "pipeline_id": self.pipeline_id,
            "plan_id": self.plan_id,
            "inspector": self.inspector,
            "confidence": self.confidence,
            "security_domain": self.security_domain,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class SchemaChange:
    """A semantic schema change between two states."""

    kind: str
    path: str
    previous: dict[str, Any] | None = None
    current: dict[str, Any] | None = None
    impact: DriftImpact = DriftImpact.UNKNOWN
    remediation: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize change."""
        return {
            "kind": self.kind,
            "path": self.path,
            "previous": self.previous,
            "current": self.current,
            "impact": self.impact.value,
            "remediation": self.remediation,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class SchemaChangeSet:
    """Comparison of two schema states."""

    baseline_fingerprint: str
    candidate_fingerprint: str
    changes: tuple[SchemaChange, ...]
    overall_impact: DriftImpact
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize change set."""
        return {
            "baseline_fingerprint": self.baseline_fingerprint,
            "candidate_fingerprint": self.candidate_fingerprint,
            "changes": [c.to_dict() for c in self.changes],
            "overall_impact": self.overall_impact.value,
            "metadata": dict(self.metadata),
        }


def normalize_schema_from_model(
    model: type[Data], *, identity: str | None = None
) -> NormalizedSchema:
    """Normalize a ContractModel/Data class into a logical schema."""
    if not is_data_contract_type(model):
        raise TypeError("Expected a Data / ContractModel subclass")
    fields: list[NormalizedField] = []
    for name, field_info in getattr(model, "model_fields", {}).items():
        annotation = field_info.annotation
        logical = _logical_type_name(annotation)
        required = field_info.is_required()
        nullable = _is_nullable(annotation)
        fields.append(
            NormalizedField(
                name=name,
                logical_type=logical,
                required=required,
                nullable=nullable,
            )
        )
    return NormalizedSchema(
        identity=identity or f"schema:{model.__module__}.{model.__qualname__}",
        fields=tuple(sorted(fields, key=lambda f: f.name)),
    )


def normalize_schema_from_fields(
    fields: list[dict[str, Any]],
    *,
    identity: str,
) -> NormalizedSchema:
    """Normalize a list of field mappings (operational observation path)."""
    normalized = tuple(
        sorted(
            (
                NormalizedField(
                    name=str(f["name"]),
                    logical_type=_canonicalize_logical_type(
                        str(f.get("logical_type") or f.get("type") or "unknown")
                    ),
                    required=bool(f.get("required", True)),
                    nullable=bool(f.get("nullable", False)),
                    metadata={
                        k: v
                        for k, v in f.items()
                        if k
                        not in {"name", "logical_type", "type", "required", "nullable"}
                    },
                )
                for f in fields
            ),
            key=lambda x: x.name,
        )
    )
    return NormalizedSchema(identity=identity, fields=normalized)


def diff_normalized_schemas(
    baseline: NormalizedSchema,
    candidate: NormalizedSchema,
) -> SchemaChangeSet:
    """Operational drift path: compare normalized schemas without ContractModel."""
    left = {f.name: f for f in baseline.fields}
    right = {f.name: f for f in candidate.fields}
    changes: list[SchemaChange] = []
    for name in sorted(set(left) - set(right)):
        changes.append(
            SchemaChange(
                kind="field_removed",
                path=name,
                previous=left[name].to_dict(),
                impact=DriftImpact.BREAKING,
                remediation="Restore the field or update downstream consumers.",
            )
        )
    for name in sorted(set(right) - set(left)):
        changes.append(
            SchemaChange(
                kind="field_added",
                path=name,
                current=right[name].to_dict(),
                impact=DriftImpact.COMPATIBLE,
            )
        )
    for name in sorted(set(left) & set(right)):
        a, b = left[name], right[name]
        if _canonicalize_logical_type(a.logical_type) != _canonicalize_logical_type(
            b.logical_type
        ):
            changes.append(
                SchemaChange(
                    kind="type_changed",
                    path=name,
                    previous=a.to_dict(),
                    current=b.to_dict(),
                    impact=DriftImpact.BREAKING,
                )
            )
        elif a.nullable != b.nullable or a.required != b.required:
            impact = (
                DriftImpact.CONDITIONALLY_COMPATIBLE
                if (not a.nullable and b.nullable) or (a.required and not b.required)
                else DriftImpact.BREAKING
            )
            changes.append(
                SchemaChange(
                    kind="nullability_changed",
                    path=name,
                    previous=a.to_dict(),
                    current=b.to_dict(),
                    impact=impact,
                )
            )
    overall = _overall_impact(changes)
    return SchemaChangeSet(
        baseline_fingerprint=baseline.fingerprint(),
        candidate_fingerprint=candidate.fingerprint(),
        changes=tuple(changes),
        overall_impact=overall,
    )


def diff_contract_schemas(
    previous: type[Data],
    current: type[Data],
) -> SchemaChangeSet:
    """Contract-drift path: delegate compatibility meaning to ContractModel diffs."""
    from etlantic.interchange.diff import diff_data_contracts

    baseline = normalize_schema_from_model(previous)
    candidate = normalize_schema_from_model(current)
    operational = diff_normalized_schemas(baseline, candidate)
    try:
        report = diff_data_contracts(previous, current)
        # Map toolkit findings into impact when available
        if getattr(report, "has_errors", False) or (
            hasattr(report, "errors") and report.errors
        ):
            overall = DriftImpact.BREAKING
        elif operational.changes:
            overall = operational.overall_impact
        else:
            overall = DriftImpact.INFORMATIONAL
    except Exception:
        # Fail closed: toolkit errors must not under-report breaking changes.
        overall = DriftImpact.BREAKING
    return SchemaChangeSet(
        baseline_fingerprint=baseline.fingerprint(),
        candidate_fingerprint=candidate.fingerprint(),
        changes=operational.changes,
        overall_impact=overall,
        metadata={"path": "contract"},
    )


def _overall_impact(changes: list[SchemaChange]) -> DriftImpact:
    if not changes:
        return DriftImpact.INFORMATIONAL
    order = [
        DriftImpact.BREAKING,
        DriftImpact.CONDITIONALLY_COMPATIBLE,
        DriftImpact.UNKNOWN,
        DriftImpact.COMPATIBLE,
        DriftImpact.INFORMATIONAL,
    ]
    for level in order:
        if any(c.impact is level for c in changes):
            return level
    return DriftImpact.UNKNOWN


def _logical_type_name(annotation: Any) -> str:
    origin = getattr(annotation, "__origin__", None)
    if origin is not None:
        args = getattr(annotation, "__args__", ())
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            return _logical_type_name(non_none[0])
    name = getattr(annotation, "__name__", None)
    raw = str(name).lower() if name else str(annotation).replace("typing.", "").lower()
    return _canonicalize_logical_type(raw)


def _canonicalize_logical_type(name: str) -> str:
    """Normalize Python and JSON-schema style logical type aliases."""
    aliases = {
        "int": "integer",
        "integer": "integer",
        "str": "string",
        "string": "string",
        "bool": "boolean",
        "boolean": "boolean",
        "float": "number",
        "number": "number",
        "decimal": "number",
        "double": "number",
        "null": "null",
        "none": "null",
        "dict": "object",
        "object": "object",
        "mapping": "object",
        "list": "array",
        "tuple": "array",
        "array": "array",
    }
    return aliases.get(name, name)


def _is_nullable(annotation: Any) -> bool:
    origin = getattr(annotation, "__origin__", None)
    args = getattr(annotation, "__args__", ())
    if origin is None:
        return False
    return any(a is type(None) for a in args)
