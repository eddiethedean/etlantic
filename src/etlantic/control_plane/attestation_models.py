"""Supply-chain attestation models (CP4)."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from etlantic.control_plane.redaction import redact_control_plane_payload

ATTESTATION_SCHEMA = "etlantic.control_plane.attestation/1"
VERIFICATION_RESULT_SCHEMA = "etlantic.control_plane.verification_result/1"
SIGNED_SCHEMA_OBSERVATION_SCHEMA = "etlantic.control_plane.signed_schema_observation/1"

AttestationKind = Literal[
    "plan", "revision", "plugin", "policy_bundle", "sbom", "schema_observation"
]


def _now() -> datetime:
    return datetime.now(UTC)


def sign_payload(secret: bytes, payload: str) -> str:
    return hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_signature(secret: bytes, payload: str, signature: str) -> bool:
    expected = sign_payload(secret, payload)
    return hmac.compare_digest(expected, signature)


@dataclass(frozen=True, slots=True)
class Attestation:
    attestation_id: str
    kind: AttestationKind
    subject_fingerprint: str
    signature: str
    signer_id: str
    tenant_id: str | None = None
    workspace_id: str | None = None
    environment: str | None = None
    sbom_digest: str | None = None
    created_at: datetime = field(default_factory=_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": ATTESTATION_SCHEMA,
            "attestation_id": self.attestation_id,
            "kind": self.kind,
            "subject_fingerprint": self.subject_fingerprint,
            "signature": self.signature,
            "signer_id": self.signer_id,
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "environment": self.environment,
            "sbom_digest": self.sbom_digest,
            "created_at": self.created_at.isoformat(),
            "metadata": redact_control_plane_payload(dict(self.metadata)),
        }

    def signing_payload(self) -> str:
        return "|".join(
            [
                self.kind,
                self.subject_fingerprint,
                self.signer_id,
                self.tenant_id or "",
                self.workspace_id or "",
                self.environment or "",
                self.sbom_digest or "",
            ]
        )


@dataclass(frozen=True, slots=True)
class VerificationResult:
    ok: bool
    reasons: tuple[str, ...] = ()
    attestation_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": VERIFICATION_RESULT_SCHEMA,
            "ok": self.ok,
            "reasons": list(self.reasons),
            "attestation_id": self.attestation_id,
        }


@dataclass(frozen=True, slots=True)
class SignedSchemaObservation:
    observation_id: str
    tenant_id: str
    workspace_id: str
    environment: str
    schema_fingerprint: str
    signature: str
    signer_id: str
    created_at: datetime = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SIGNED_SCHEMA_OBSERVATION_SCHEMA,
            "observation_id": self.observation_id,
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "environment": self.environment,
            "schema_fingerprint": self.schema_fingerprint,
            "signature": self.signature,
            "signer_id": self.signer_id,
            "created_at": self.created_at.isoformat(),
        }

    def signing_payload(self) -> str:
        return "|".join(
            [
                self.tenant_id,
                self.workspace_id,
                self.environment,
                self.schema_fingerprint,
                self.signer_id,
            ]
        )


def require_verified(results: Sequence[VerificationResult]) -> None:
    from etlantic.control_plane.errors import ControlPlaneError

    bad = [r for r in results if not r.ok]
    if bad:
        raise ControlPlaneError.forbidden(
            "attestation verification failed",
            extensions={"reasons": [x for r in bad for x in r.reasons]},
        )


__all__ = [
    "ATTESTATION_SCHEMA",
    "SIGNED_SCHEMA_OBSERVATION_SCHEMA",
    "VERIFICATION_RESULT_SCHEMA",
    "Attestation",
    "AttestationKind",
    "SignedSchemaObservation",
    "VerificationResult",
    "require_verified",
    "sign_payload",
    "verify_signature",
]
