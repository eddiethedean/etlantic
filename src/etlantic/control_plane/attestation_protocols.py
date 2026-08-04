"""Attestation verification protocol (CP4)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from etlantic.control_plane.attestation_models import (
    Attestation,
    SignedSchemaObservation,
    VerificationResult,
)
from etlantic.control_plane.models import ControlPlaneContext


@runtime_checkable
class AttestationStore(Protocol):
    def put(
        self, ctx: ControlPlaneContext, *, attestation: Attestation
    ) -> Attestation: ...

    def verify_plan(
        self,
        ctx: ControlPlaneContext,
        *,
        plan_fingerprint: str,
        revision_id: str,
        policy_fingerprint: str,
        plugin_fingerprints: Sequence[str],
        sbom_digest: str | None = None,
    ) -> Sequence[VerificationResult]: ...

    def put_schema_observation(
        self, ctx: ControlPlaneContext, *, observation: SignedSchemaObservation
    ) -> SignedSchemaObservation: ...

    def verify_schema_observation(
        self,
        ctx: ControlPlaneContext,
        *,
        observation_id: str,
        expected_environment: str | None = None,
    ) -> VerificationResult: ...


__all__ = ["AttestationStore"]
