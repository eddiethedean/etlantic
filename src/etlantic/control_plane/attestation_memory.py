"""In-memory attestation and signed schema observation store (CP4)."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Sequence
from copy import deepcopy

from etlantic.control_plane.attestation_models import (
    Attestation,
    SignedSchemaObservation,
    VerificationResult,
    sign_payload,
    verify_signature,
)
from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.models import ControlPlaneContext


def _scope(ctx: ControlPlaneContext) -> tuple[str, str]:
    return ctx.tenant.tenant_id, ctx.workspace.workspace_id


_TEST_SIGNING_SECRET = b"etlantic-cp4-test-secret"


class MemoryAttestationStore:
    def __init__(self, *, signing_secret: bytes) -> None:
        if not signing_secret:
            raise ControlPlaneError(
                "attestation signing_secret is required",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        self.signing_secret = signing_secret
        self._attestations: dict[tuple[str, str, str], Attestation] = {}
        self._by_subject: dict[tuple[str, str, str, str], str] = {}
        self._observations: dict[tuple[str, str, str], SignedSchemaObservation] = {}
        self._revoked: set[str] = set()
        self._lock = threading.RLock()

    @classmethod
    def for_tests(cls) -> MemoryAttestationStore:
        """Insecure fixed secret for unit/conformance tests only."""
        return cls(signing_secret=_TEST_SIGNING_SECRET)

    def sign(self, attestation: Attestation) -> Attestation:
        from dataclasses import replace

        sig = sign_payload(self.signing_secret, attestation.signing_payload())
        return replace(attestation, signature=sig)

    def put(self, ctx: ControlPlaneContext, *, attestation: Attestation) -> Attestation:
        with self._lock:
            scoped = attestation
            if attestation.tenant_id is None:
                from dataclasses import replace

                scoped = replace(
                    attestation,
                    tenant_id=ctx.tenant.tenant_id,
                    workspace_id=ctx.workspace.workspace_id,
                    environment=ctx.environment.name,
                )
            if not verify_signature(
                self.signing_secret, scoped.signing_payload(), scoped.signature
            ):
                raise ControlPlaneError.forbidden("invalid attestation signature")
            key = (*_scope(ctx), scoped.attestation_id)
            self._attestations[key] = scoped
            self._by_subject[
                (*_scope(ctx), scoped.kind, scoped.subject_fingerprint)
            ] = scoped.attestation_id
            return deepcopy(scoped)

    def revoke(self, ctx: ControlPlaneContext, *, attestation_id: str) -> None:
        with self._lock:
            self._revoked.add(attestation_id)

    def verify_plan(
        self,
        ctx: ControlPlaneContext,
        *,
        plan_fingerprint: str,
        revision_id: str,
        policy_fingerprint: str,
        plugin_fingerprints: Sequence[str],
        sbom_digest: str | None = None,
    ) -> Sequence[VerificationResult]:
        with self._lock:
            results: list[VerificationResult] = []
            checks = [
                ("plan", plan_fingerprint),
                ("revision", revision_id),
                ("policy_bundle", policy_fingerprint),
            ]
            for plugin in plugin_fingerprints:
                checks.append(("plugin", plugin))
            if sbom_digest is not None:
                checks.append(("sbom", sbom_digest))
            for kind, subject in checks:
                aid = self._by_subject.get((*_scope(ctx), kind, subject))
                if aid is None:
                    results.append(
                        VerificationResult(
                            ok=False,
                            reasons=(f"missing {kind} attestation",),
                        )
                    )
                    continue
                if aid in self._revoked:
                    results.append(
                        VerificationResult(
                            ok=False,
                            reasons=(f"revoked {kind} attestation",),
                            attestation_id=aid,
                        )
                    )
                    continue
                att = self._attestations.get((*_scope(ctx), aid))
                if att is None or not verify_signature(
                    self.signing_secret, att.signing_payload(), att.signature
                ):
                    results.append(
                        VerificationResult(
                            ok=False,
                            reasons=(f"tampered {kind} attestation",),
                            attestation_id=aid,
                        )
                    )
                    continue
                results.append(
                    VerificationResult(ok=True, reasons=(), attestation_id=aid)
                )
            return results

    def put_schema_observation(
        self, ctx: ControlPlaneContext, *, observation: SignedSchemaObservation
    ) -> SignedSchemaObservation:
        with self._lock:
            if (
                observation.tenant_id != ctx.tenant.tenant_id
                or observation.workspace_id != ctx.workspace.workspace_id
            ):
                raise ControlPlaneError.forbidden("observation scope mismatch")
            if not verify_signature(
                self.signing_secret,
                observation.signing_payload(),
                observation.signature,
            ):
                raise ControlPlaneError.forbidden("invalid observation signature")
            self._observations[(*_scope(ctx), observation.observation_id)] = observation
            return deepcopy(observation)

    def verify_schema_observation(
        self,
        ctx: ControlPlaneContext,
        *,
        observation_id: str,
        expected_environment: str | None = None,
    ) -> VerificationResult:
        with self._lock:
            obs = self._observations.get((*_scope(ctx), observation_id))
            if obs is None:
                # Cross-tenant lookup must not enumerate.
                return VerificationResult(ok=False, reasons=("observation not found",))
            if not verify_signature(
                self.signing_secret, obs.signing_payload(), obs.signature
            ):
                return VerificationResult(
                    ok=False,
                    reasons=("forged or tampered observation",),
                    attestation_id=observation_id,
                )
            if (
                expected_environment is not None
                and obs.environment != expected_environment
            ):
                return VerificationResult(
                    ok=False,
                    reasons=("cross-environment observation rejected",),
                    attestation_id=observation_id,
                )
            return VerificationResult(ok=True, attestation_id=observation_id)

    def make_attestation(
        self,
        ctx: ControlPlaneContext,
        *,
        kind: str,
        subject_fingerprint: str,
        sbom_digest: str | None = None,
    ) -> Attestation:
        att = Attestation(
            attestation_id=str(uuid.uuid4()),
            kind=kind,  # type: ignore[arg-type]
            subject_fingerprint=subject_fingerprint,
            signature="",
            signer_id="memory",
            tenant_id=ctx.tenant.tenant_id,
            workspace_id=ctx.workspace.workspace_id,
            environment=ctx.environment.name,
            sbom_digest=sbom_digest,
        )
        return self.sign(att)

    def make_schema_observation(
        self,
        ctx: ControlPlaneContext,
        *,
        schema_fingerprint: str,
        environment: str | None = None,
    ) -> SignedSchemaObservation:
        obs = SignedSchemaObservation(
            observation_id=str(uuid.uuid4()),
            tenant_id=ctx.tenant.tenant_id,
            workspace_id=ctx.workspace.workspace_id,
            environment=environment or ctx.environment.name,
            schema_fingerprint=schema_fingerprint,
            signature="",
            signer_id="memory",
        )
        from dataclasses import replace

        sig = sign_payload(self.signing_secret, obs.signing_payload())
        return replace(obs, signature=sig)


__all__ = ["MemoryAttestationStore"]
