# pyright: reportUnknownVariableType=false
"""External artifact transport and size policies for orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from etlantic.orchestration.protocol import CompilationDiagnostic
from etlantic.plan.artifacts import ArtifactRef, ArtifactStrategy

# Default max bytes allowed for inline / XCom-style payloads.
DEFAULT_MAX_INLINE_BYTES = 65_536


@dataclass(frozen=True, slots=True)
class ArtifactTransportPolicy:
    """Policy controlling how step outputs cross orchestrator task boundaries."""

    max_inline_bytes: int = DEFAULT_MAX_INLINE_BYTES
    require_durable_above: int = DEFAULT_MAX_INLINE_BYTES
    allow_in_memory: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_inline_bytes": self.max_inline_bytes,
            "require_durable_above": self.require_durable_above,
            "allow_in_memory": self.allow_in_memory,
            "metadata": dict(self.metadata),
        }


def validate_artifact_for_transport(
    artifact: ArtifactRef,
    *,
    estimated_bytes: int | None = None,
    policy: ArtifactTransportPolicy | None = None,
) -> list[CompilationDiagnostic]:
    """Return diagnostics when an artifact cannot safely cross task boundaries."""
    policy = policy or ArtifactTransportPolicy()
    diagnostics: list[CompilationDiagnostic] = []

    if artifact.strategy is ArtifactStrategy.IN_MEMORY and not policy.allow_in_memory:
        diagnostics.append(
            CompilationDiagnostic(
                code="PMORCH340",
                severity="error",
                message=(
                    f"Artifact {artifact.identity!r} uses in-memory strategy; "
                    "external orchestration requires durable or external refs "
                    "(no large payloads via XCom)."
                ),
                subject_id=artifact.identity,
            )
        )

    if (
        estimated_bytes is not None
        and estimated_bytes > policy.require_durable_above
        and artifact.strategy
        not in {ArtifactStrategy.DURABLE, ArtifactStrategy.EXTERNAL}
    ):
        diagnostics.append(
            CompilationDiagnostic(
                code="PMORCH341",
                severity="error",
                message=(
                    f"Artifact {artifact.identity!r} estimated at "
                    f"{estimated_bytes} bytes exceeds inline limit "
                    f"{policy.require_durable_above}; use a durable ArtifactRef."
                ),
                subject_id=artifact.identity,
            )
        )

    # Metadata must remain secret-free (same rule as plans/reports).
    meta_blob = str(artifact.metadata).lower()
    for needle in (
        "password",
        "passwd",
        "pwd",
        "secret_value",
        "secret",
        "api_key",
        "token",
        "authorization",
        "credential",
        "bearer",
        "aws_secret_access_key",
        "private_key",
    ):
        if needle in meta_blob:
            diagnostics.append(
                CompilationDiagnostic(
                    code="PMORCH342",
                    severity="error",
                    message=(
                        f"Artifact {artifact.identity!r} metadata appears to "
                        "contain secrets; failing closed."
                    ),
                    subject_id=artifact.identity,
                )
            )
            break

    return diagnostics


def xcom_safe_payload(artifact: ArtifactRef) -> dict[str, Any]:
    """Return a small, secret-free payload suitable for XCom / task messaging."""
    return {
        "artifact": artifact.to_dict(),
        "transport": "artifact_ref",
    }
