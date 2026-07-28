"""Execution regions and materialization boundaries."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ExecutionRegion:
    """A group of logical nodes realized by one backend together."""

    identity: str
    engine: str
    node_names: tuple[str, ...]
    security_domain: str = "default"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize region."""
        return {
            "identity": self.identity,
            "engine": self.engine,
            "node_names": list(self.node_names),
            "security_domain": self.security_domain,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(
        cls, data: dict[str, Any], *, strict: bool = False
    ) -> ExecutionRegion:
        """Deserialize region."""
        from etlantic.extensions import validate_extension_metadata
        from etlantic.plan.freeze import deep_freeze

        metadata = dict(data.get("metadata") or {})
        validate_extension_metadata(metadata, path="region.metadata", strict=strict)
        region = cls(
            identity=str(data["identity"]),
            engine=str(data["engine"]),
            node_names=tuple(data.get("node_names") or ()),
            security_domain=str(data.get("security_domain") or "default"),
            metadata=metadata,
        )
        object.__setattr__(region, "metadata", deep_freeze(region.metadata))
        return region


@dataclass(frozen=True, slots=True)
class MaterializationBoundary:
    """A required durable/handoff boundary between regions or for reuse."""

    identity: str
    producer_node: str
    producer_port: str
    reason: str
    security_domain: str = "default"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize boundary."""
        return {
            "identity": self.identity,
            "producer_node": self.producer_node,
            "producer_port": self.producer_port,
            "reason": self.reason,
            "security_domain": self.security_domain,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(
        cls, data: dict[str, Any], *, strict: bool = False
    ) -> MaterializationBoundary:
        """Deserialize boundary."""
        from etlantic.extensions import validate_extension_metadata
        from etlantic.plan.freeze import deep_freeze

        metadata = dict(data.get("metadata") or {})
        validate_extension_metadata(metadata, path="boundary.metadata", strict=strict)
        boundary = cls(
            identity=str(data["identity"]),
            producer_node=str(data["producer_node"]),
            producer_port=str(data["producer_port"]),
            reason=str(data["reason"]),
            security_domain=str(data.get("security_domain") or "default"),
            metadata=metadata,
        )
        object.__setattr__(boundary, "metadata", deep_freeze(boundary.metadata))
        return boundary
