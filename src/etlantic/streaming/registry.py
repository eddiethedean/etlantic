"""Schema-registry provider protocol and in-memory implementation (046-G)."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from etlantic.diagnostics import Diagnostic
from etlantic.streaming.diagnostics import reg_diagnostic

REGISTRY_PROTOCOL = "etlantic.schema-registry/1"


class SchemaFormat(StrEnum):
    AVRO = "avro"
    PROTOBUF = "protobuf"
    JSON_SCHEMA = "json_schema"


class CompatibilityMode(StrEnum):
    BACKWARD = "backward"
    FORWARD = "forward"
    FULL = "full"
    NONE = "none"


class RegistryOutagePolicy(StrEnum):
    FAIL_CLOSED = "fail_closed"


@dataclass(frozen=True, slots=True)
class SchemaIdentity:
    """Subject/version identity (fingerprints, not schema documents)."""

    subject: str
    version: int
    format: SchemaFormat
    fingerprint: str
    compatibility: CompatibilityMode = CompatibilityMode.BACKWARD

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "version": self.version,
            "format": self.format.value,
            "fingerprint": self.fingerprint,
            "compatibility": self.compatibility.value,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SchemaIdentity:
        return cls(
            subject=str(data["subject"]),
            version=int(data["version"]),
            format=SchemaFormat(str(data["format"])),
            fingerprint=str(data["fingerprint"]),
            compatibility=CompatibilityMode(
                str(data.get("compatibility") or "backward")
            ),
        )


def schema_fingerprint(document: str, *, format: SchemaFormat) -> str:
    """SHA-256 of a schema document used only as identity (not stored in reports)."""
    payload = f"{format.value}\n{document}".encode()
    return hashlib.sha256(payload).hexdigest()


@runtime_checkable
class SchemaRegistryProvider(Protocol):
    """Lookup / compatibility / outage policy (no payloads in ETLantic artifacts)."""

    protocol: str

    def lookup(self, subject: str, version: int | None = None) -> SchemaIdentity:
        """Return identity for a subject (latest when version is None)."""
        ...

    def check_compatibility(
        self,
        subject: str,
        candidate_fingerprint: str,
    ) -> bool:
        """Return True when candidate is compatible with the subject's mode."""
        ...

    def register(
        self,
        subject: str,
        fingerprint: str,
        *,
        format: SchemaFormat,
        compatibility: CompatibilityMode = CompatibilityMode.BACKWARD,
    ) -> SchemaIdentity:
        """Register a schema identity (fingerprint only)."""
        ...


@dataclass
class InMemorySchemaRegistry:
    """Fail-closed in-memory registry (wire protocol; no HTTP client)."""

    protocol: str = REGISTRY_PROTOCOL
    outage: bool = False
    stale: bool = False
    _subjects: dict[str, list[SchemaIdentity]] = field(default_factory=dict)

    def set_outage(self, value: bool = True) -> None:
        self.outage = value

    def set_stale(self, value: bool = True) -> None:
        self.stale = value

    def _fail(self, key: str, message: str) -> Diagnostic:
        return reg_diagnostic(key, message, path=("schema_registry",))

    def lookup(self, subject: str, version: int | None = None) -> SchemaIdentity:
        if self.outage:
            raise LookupError(
                self._fail(
                    "unavailable",
                    f"Schema registry unavailable for subject {subject!r}",
                ).message
            )
        if self.stale:
            raise LookupError(
                self._fail(
                    "stale_cache",
                    f"Schema registry cache stale for subject {subject!r}",
                ).message
            )
        versions = self._subjects.get(subject) or []
        if not versions:
            raise LookupError(
                self._fail(
                    "unavailable",
                    f"Unknown schema subject {subject!r}",
                ).message
            )
        if version is None:
            return versions[-1]
        for item in versions:
            if item.version == version:
                return item
        raise LookupError(
            self._fail(
                "ambiguous",
                f"Unknown version {version} for subject {subject!r}",
            ).message
        )

    def check_compatibility(self, subject: str, candidate_fingerprint: str) -> bool:
        if self.outage:
            return False
        versions = self._subjects.get(subject) or []
        if not versions:
            return True
        latest = versions[-1]
        if latest.compatibility is CompatibilityMode.NONE:
            return True
        return candidate_fingerprint == latest.fingerprint or any(
            item.fingerprint == candidate_fingerprint for item in versions
        )

    def register(
        self,
        subject: str,
        fingerprint: str,
        *,
        format: SchemaFormat,
        compatibility: CompatibilityMode = CompatibilityMode.BACKWARD,
    ) -> SchemaIdentity:
        if self.outage:
            raise LookupError(
                self._fail(
                    "unavailable", "Schema registry unavailable; refusing register"
                ).message
            )
        if not self.check_compatibility(subject, fingerprint):
            raise ValueError(
                self._fail(
                    "incompatible",
                    f"Fingerprint {fingerprint[:12]}… incompatible with {subject!r}",
                ).message
            )
        versions = self._subjects.setdefault(subject, [])
        next_version = (versions[-1].version + 1) if versions else 1
        identity = SchemaIdentity(
            subject=subject,
            version=next_version,
            format=format,
            fingerprint=fingerprint,
            compatibility=compatibility,
        )
        versions.append(identity)
        return identity
