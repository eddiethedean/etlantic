"""Public connector request / plan / session / evidence models."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from etlantic.connectors.maturity import ConnectorMaturity
from etlantic.secrets import SecretRef

SOURCE_PROTOCOL = "etlantic.source/1"
SINK_PROTOCOL = "etlantic.sink/1"
STORAGE_PROTOCOL = "etlantic.storage/1"
LANDING_CHECKPOINT_SCHEMA = "etlantic.landing_checkpoint/1"

CommitStatus = Literal["committed", "rolled_back", "unknown"]
LandingMode = Literal["snapshot", "incremental"]
ConsumePolicy = Literal["none", "ledger", "rename_done"]
EmptyMatchPolicy = Literal["fail", "allow"]


def _canonical_json(data: Mapping[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def fingerprint_public_config(config: Mapping[str, Any] | None) -> str:
    """Stable SHA-256 of secret-free public connector config."""
    payload = _canonical_json(dict(config or {}))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ConnectorInfo:
    """Static connector identity (no live imports required for manifests)."""

    name: str
    protocol: str
    version: str = "0.0.0"
    provider: str | None = None
    capabilities: tuple[str, ...] = ()
    maturity: ConnectorMaturity = ConnectorMaturity.EXPERIMENTAL
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "protocol": self.protocol,
            "version": self.version,
            "provider": self.provider,
            "capabilities": list(self.capabilities),
            "maturity": self.maturity.value,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ConnectorInfo:
        maturity_raw = data.get("maturity") or ConnectorMaturity.EXPERIMENTAL.value
        return cls(
            name=str(data["name"]),
            protocol=str(data["protocol"]),
            version=str(data.get("version") or "0.0.0"),
            provider=(
                str(data["provider"]) if data.get("provider") is not None else None
            ),
            capabilities=tuple(str(x) for x in (data.get("capabilities") or ())),
            maturity=ConnectorMaturity(str(maturity_raw)),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True, slots=True)
class ConnectorBinding:
    """Typed, secret-free connector binding (canonical structured asset)."""

    provider: str
    location: str | None = None
    format: str | None = None
    config: dict[str, Any] = field(default_factory=dict)
    mode: LandingMode | None = None
    glob: str | None = None
    root: str | None = None
    root_ref: str | None = None
    consume: ConsumePolicy | None = None
    checkpoint: str | None = None
    required_capabilities: tuple[str, ...] = ()
    secret_refs: dict[str, str] = field(default_factory=dict)
    protocol: str | None = None
    provider_version: str | None = None

    @property
    def config_fingerprint(self) -> str:
        return fingerprint_public_config(self.config)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "location": self.location,
            "format": self.format,
            "config": dict(self.config),
            "mode": self.mode,
            "glob": self.glob,
            "root": self.root,
            "root_ref": self.root_ref,
            "consume": self.consume,
            "checkpoint": self.checkpoint,
            "required_capabilities": list(self.required_capabilities),
            "secret_refs": dict(self.secret_refs),
            "protocol": self.protocol,
            "provider_version": self.provider_version,
            "config_fingerprint": self.config_fingerprint,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ConnectorBinding:
        mode = data.get("mode")
        consume = data.get("consume")
        return cls(
            provider=str(data["provider"]),
            location=(
                str(data["location"]) if data.get("location") is not None else None
            ),
            format=(str(data["format"]) if data.get("format") is not None else None),
            config=dict(data.get("config") or {}),
            mode=(str(mode) if mode is not None else None),  # type: ignore[arg-type]
            glob=(str(data["glob"]) if data.get("glob") is not None else None),
            root=(str(data["root"]) if data.get("root") is not None else None),
            root_ref=(
                str(data["root_ref"]) if data.get("root_ref") is not None else None
            ),
            consume=(str(consume) if consume is not None else None),  # type: ignore[arg-type]
            checkpoint=(
                str(data["checkpoint"]) if data.get("checkpoint") is not None else None
            ),
            required_capabilities=tuple(
                str(x) for x in (data.get("required_capabilities") or ())
            ),
            secret_refs={
                str(k): str(v) for k, v in dict(data.get("secret_refs") or {}).items()
            },
            protocol=(
                str(data["protocol"]) if data.get("protocol") is not None else None
            ),
            provider_version=(
                str(data["provider_version"])
                if data.get("provider_version") is not None
                else None
            ),
        )


@dataclass(frozen=True, slots=True)
class SourcePlan:
    """Static source plan evidence (no live file listing)."""

    provider: str
    protocol: str = SOURCE_PROTOCOL
    mode: LandingMode | None = None
    identity_scheme: str = "landing_file_sha256/1"
    listing_intent: dict[str, Any] = field(default_factory=dict)
    required_capabilities: tuple[str, ...] = ()
    config_fingerprint: str | None = None
    checkpoint_ref: str | None = None
    root_ref: str | None = None
    secret_refs: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "protocol": self.protocol,
            "mode": self.mode,
            "identity_scheme": self.identity_scheme,
            "listing_intent": dict(self.listing_intent),
            "required_capabilities": list(self.required_capabilities),
            "config_fingerprint": self.config_fingerprint,
            "checkpoint_ref": self.checkpoint_ref,
            "root_ref": self.root_ref,
            "secret_refs": list(self.secret_refs),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class SinkPlan:
    """Static sink plan evidence."""

    provider: str
    protocol: str = SINK_PROTOCOL
    write_mode: str | None = None
    required_capabilities: tuple[str, ...] = ()
    config_fingerprint: str | None = None
    root_ref: str | None = None
    secret_refs: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "protocol": self.protocol,
            "write_mode": self.write_mode,
            "required_capabilities": list(self.required_capabilities),
            "config_fingerprint": self.config_fingerprint,
            "root_ref": self.root_ref,
            "secret_refs": list(self.secret_refs),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class LandingFileIdentity:
    """Stable landing-zone file identity (no absolute host paths)."""

    root_ref: str
    relative_path: str
    size: int
    content_sha256: str
    identity_version: str = "landing_file_sha256/1"

    @property
    def identity_key(self) -> str:
        return (
            f"{self.identity_version}|{self.root_ref}|{self.relative_path}|"
            f"{self.size}|{self.content_sha256}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_ref": self.root_ref,
            "relative_path": self.relative_path,
            "size": self.size,
            "content_sha256": self.content_sha256,
            "identity_version": self.identity_version,
            "identity_key": self.identity_key,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> LandingFileIdentity:
        return cls(
            root_ref=str(data["root_ref"]),
            relative_path=str(data["relative_path"]),
            size=int(data["size"]),
            content_sha256=str(data["content_sha256"]),
            identity_version=str(
                data.get("identity_version") or "landing_file_sha256/1"
            ),
        )


@dataclass(frozen=True, slots=True)
class ReadBatch:
    """One bounded read batch from a source connector."""

    records: tuple[Any, ...] = ()
    batch_index: int = 0
    exhausted: bool = False
    identities: tuple[LandingFileIdentity, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_index": self.batch_index,
            "exhausted": self.exhausted,
            "record_count": len(self.records),
            "identities": [i.to_dict() for i in self.identities],
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class CursorProposal:
    """Staged cursor / ledger proposal before publication commit."""

    subject_id: str
    candidate: str | None = None
    identities: tuple[LandingFileIdentity, ...] = ()
    generation: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "candidate": self.candidate,
            "identities": [i.to_dict() for i in self.identities],
            "generation": self.generation,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class WriteSession:
    """Handle for a staged sink write session."""

    session_id: str
    provider: str
    protocol: str = SINK_PROTOCOL
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "provider": self.provider,
            "protocol": self.protocol,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class CommitReceipt:
    """Publication outcome: committed, rolled_back, or unknown."""

    status: CommitStatus
    session_id: str | None = None
    provider: str | None = None
    publication_id: str | None = None
    message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "session_id": self.session_id,
            "provider": self.provider,
            "publication_id": self.publication_id,
            "message": self.message,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CommitReceipt:
        status = str(data.get("status") or "unknown")
        if status not in {"committed", "rolled_back", "unknown"}:
            status = "unknown"
        return cls(
            status=status,  # type: ignore[arg-type]
            session_id=(
                str(data["session_id"]) if data.get("session_id") is not None else None
            ),
            provider=(
                str(data["provider"]) if data.get("provider") is not None else None
            ),
            publication_id=(
                str(data["publication_id"])
                if data.get("publication_id") is not None
                else None
            ),
            message=(str(data["message"]) if data.get("message") is not None else None),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True, slots=True)
class CleanupReceipt:
    """Post-commit cleanup / consume outcome."""

    status: Literal["completed", "failed", "skipped"]
    consume: ConsumePolicy | None = None
    archived: tuple[str, ...] = ()
    message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "consume": self.consume,
            "archived": list(self.archived),
            "message": self.message,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    """Outcome of reconciling an unknown publication."""

    status: CommitStatus
    publication_id: str | None = None
    message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "publication_id": self.publication_id,
            "message": self.message,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class LandingReadManifest:
    """Run-scoped landing-zone read evidence (not static plan)."""

    root_ref: str
    identities: tuple[LandingFileIdentity, ...] = ()
    file_count: int = 0
    total_bytes: int = 0
    fingerprint: str | None = None
    mode: LandingMode | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.fingerprint and self.identities:
            keys = sorted(i.identity_key for i in self.identities)
            digest = hashlib.sha256("|".join(keys).encode("utf-8")).hexdigest()
            object.__setattr__(self, "fingerprint", digest)
        if self.file_count == 0 and self.identities:
            object.__setattr__(self, "file_count", len(self.identities))
        if self.total_bytes == 0 and self.identities:
            object.__setattr__(
                self, "total_bytes", sum(i.size for i in self.identities)
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_ref": self.root_ref,
            "identities": [i.to_dict() for i in self.identities],
            "file_count": self.file_count,
            "total_bytes": self.total_bytes,
            "fingerprint": self.fingerprint,
            "mode": self.mode,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class LandingCheckpoint:
    """Incremental landing-zone ledger (`etlantic.landing_checkpoint/1`)."""

    schema: str = LANDING_CHECKPOINT_SCHEMA
    pipeline_id: str = ""
    extract_id: str = ""
    binding_id: str = ""
    binding_fingerprint: str = ""
    generation: int = 0
    committed_identities: tuple[str, ...] = ()
    last_read_manifest_fingerprint: str | None = None
    publication_id: str | None = None
    updated_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "pipeline_id": self.pipeline_id,
            "extract_id": self.extract_id,
            "binding_id": self.binding_id,
            "binding_fingerprint": self.binding_fingerprint,
            "generation": self.generation,
            "committed_identities": list(self.committed_identities),
            "last_read_manifest_fingerprint": self.last_read_manifest_fingerprint,
            "publication_id": self.publication_id,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> LandingCheckpoint:
        return cls(
            schema=str(data.get("schema") or LANDING_CHECKPOINT_SCHEMA),
            pipeline_id=str(data.get("pipeline_id") or ""),
            extract_id=str(data.get("extract_id") or ""),
            binding_id=str(data.get("binding_id") or ""),
            binding_fingerprint=str(data.get("binding_fingerprint") or ""),
            generation=int(data.get("generation") or 0),
            committed_identities=tuple(
                str(x) for x in (data.get("committed_identities") or ())
            ),
            last_read_manifest_fingerprint=(
                str(data["last_read_manifest_fingerprint"])
                if data.get("last_read_manifest_fingerprint") is not None
                else None
            ),
            publication_id=(
                str(data["publication_id"])
                if data.get("publication_id") is not None
                else None
            ),
            updated_at=(
                str(data["updated_at"]) if data.get("updated_at") is not None else None
            ),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True, slots=True)
class SchemaInspection:
    """Bounded, row-free schema / statistics inspection evidence."""

    provider: str
    fields: tuple[dict[str, Any], ...] = ()
    row_estimate: int | None = None
    byte_estimate: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "fields": [dict(f) for f in self.fields],
            "row_estimate": self.row_estimate,
            "byte_estimate": self.byte_estimate,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class ConnectorCompatibilityRecord:
    """Compatibility matrix cell for a connector distribution."""

    provider: str
    protocol: str
    core_version: str
    package_version: str
    capabilities: tuple[str, ...] = ()
    maturity: ConnectorMaturity = ConnectorMaturity.EXPERIMENTAL
    python_versions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    suite_digest: str | None = None
    verified_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "protocol": self.protocol,
            "core_version": self.core_version,
            "package_version": self.package_version,
            "capabilities": list(self.capabilities),
            "maturity": self.maturity.value,
            "python_versions": list(self.python_versions),
            "limitations": list(self.limitations),
            "suite_digest": self.suite_digest,
            "verified_at": self.verified_at,
            "metadata": dict(self.metadata),
        }


def utc_now_iso() -> str:
    """UTC ISO-8601 timestamp for checkpoint / evidence fields."""
    from datetime import UTC

    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def merge_committed_identities(
    existing: Sequence[str],
    new_identities: Sequence[LandingFileIdentity | str],
) -> tuple[str, ...]:
    """Deterministically merge committed identity keys."""
    keys: set[str] = set(str(x) for x in existing)
    for item in new_identities:
        if isinstance(item, LandingFileIdentity):
            keys.add(item.identity_key)
        else:
            keys.add(str(item))
    return tuple(sorted(keys))


__all__ = [
    "LANDING_CHECKPOINT_SCHEMA",
    "SINK_PROTOCOL",
    "SOURCE_PROTOCOL",
    "STORAGE_PROTOCOL",
    "CleanupReceipt",
    "CommitReceipt",
    "CommitStatus",
    "ConnectorBinding",
    "ConnectorCompatibilityRecord",
    "ConnectorInfo",
    "ConsumePolicy",
    "CursorProposal",
    "EmptyMatchPolicy",
    "LandingCheckpoint",
    "LandingFileIdentity",
    "LandingMode",
    "LandingReadManifest",
    "ReadBatch",
    "ReconciliationResult",
    "SchemaInspection",
    "SecretRef",
    "SinkPlan",
    "SourcePlan",
    "WriteSession",
    "fingerprint_public_config",
    "merge_committed_identities",
    "utc_now_iso",
]
