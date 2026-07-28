"""Artifact references and materialization strategies for PipelinePlan."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from etlantic.plan.freeze import mutable_copy


class ArtifactStrategy(StrEnum):
    """How a logical OutputRef is realized for consumers."""

    IN_MEMORY = "in_memory"
    LAZY = "lazy"
    DURABLE = "durable"
    EXTERNAL = "external"


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """Runtime/durable artifact identity (secret-free)."""

    identity: str
    logical_output: str
    strategy: ArtifactStrategy
    security_domain: str = "default"
    cache_key: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize artifact reference."""
        return {
            "identity": self.identity,
            "logical_output": self.logical_output,
            "strategy": self.strategy.value,
            "security_domain": self.security_domain,
            "cache_key": self.cache_key,
            "metadata": mutable_copy(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, strict: bool = False) -> ArtifactRef:
        """Deserialize artifact reference."""
        from etlantic.extensions import validate_extension_metadata
        from etlantic.plan.freeze import deep_freeze

        metadata = dict(data.get("metadata") or {})
        validate_extension_metadata(
            metadata, path="artifact.metadata", strict=strict
        )
        artifact = cls(
            identity=str(data["identity"]),
            logical_output=str(data["logical_output"]),
            strategy=ArtifactStrategy(str(data["strategy"])),
            security_domain=str(data.get("security_domain") or "default"),
            cache_key=data.get("cache_key"),
            metadata=metadata,
        )
        object.__setattr__(artifact, "metadata", deep_freeze(artifact.metadata))
        return artifact


def _seg(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in str(value))


def artifact_identity(
    *,
    pipeline_id: str,
    node_name: str,
    port_name: str,
    security_domain: str,
    tenant: str = "default",
    environment: str = "default",
    run_id: str | None = None,
    authorization: str = "default",
    contract_version: str | None = None,
) -> str:
    """Deterministic artifact identity including isolation dimensions (0.20)."""
    parts = [
        "artifact",
        _seg(security_domain),
        _seg(tenant),
        _seg(environment),
        _seg(authorization),
    ]
    if run_id:
        parts.append(_seg(run_id))
    if contract_version:
        parts.append(f"cv-{_seg(contract_version)}")
    parts.append(_seg(pipeline_id))
    parts.append(f"{_seg(node_name)}.{_seg(port_name)}")
    return ":".join(parts[:1]) + ":" + "/".join(parts[1:])


def cache_identity(
    *,
    pipeline_id: str,
    node_name: str,
    port_name: str,
    security_domain: str,
    plan_fingerprint: str,
    ir_fingerprint: str | None = None,
    compiler_fingerprint: str | None = None,
    tenant: str = "default",
    environment: str = "default",
    run_id: str | None = None,
    authorization: str = "default",
    contract_version: str | None = None,
) -> str:
    """Deterministic cache key that cannot cross isolation domains (0.20)."""
    parts = [
        "cache",
        _seg(security_domain),
        _seg(tenant),
        _seg(environment),
        _seg(authorization),
    ]
    if run_id:
        parts.append(_seg(run_id))
    if contract_version:
        parts.append(f"cv-{_seg(contract_version)}")
    body = "/".join(parts[1:])
    key = (
        f"cache:{body}/{_seg(pipeline_id)}/"
        f"{_seg(node_name)}.{_seg(port_name)}@{plan_fingerprint}"
    )
    if ir_fingerprint:
        key += f"+ir:{ir_fingerprint}"
    if compiler_fingerprint:
        key += f"+cc:{compiler_fingerprint}"
    return key


def assert_identity_compatible(
    identity: str,
    *,
    security_domain: str,
    tenant: str = "default",
    environment: str = "default",
) -> None:
    """Reject selecting an artifact/cache identity from another isolation domain."""
    from etlantic.exceptions import ETLanticError

    expected_prefix_parts = [
        _seg(security_domain),
        _seg(tenant),
        _seg(environment),
    ]
    # identity forms: artifact:domain/tenant/env/... or cache:domain/tenant/env/...
    if ":" not in identity:
        raise ETLanticError(f"Malformed artifact/cache identity: {identity!r}")
    _, _, rest = identity.partition(":")
    segments = rest.split("/")
    for idx, expected in enumerate(expected_prefix_parts):
        if idx >= len(segments) or segments[idx] != expected:
            raise ETLanticError(
                "Artifact/cache identity isolation violation: "
                f"expected domain/tenant/env "
                f"{'/'.join(expected_prefix_parts)} in {identity!r}"
            )
