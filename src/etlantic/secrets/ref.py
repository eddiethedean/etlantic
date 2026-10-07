"""Serializable secret references (values resolve only at runtime)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SecretRef:
    """Logical reference to a secret; never contains the secret value."""

    provider: str
    name: str
    key: str
    version: str = "current"
    purpose: str | None = None

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("SecretRef.provider must be a non-empty string")
        if not self.name.strip():
            raise ValueError("SecretRef.name must be a non-empty string")
        if not self.version.strip():
            raise ValueError("SecretRef.version must be a non-empty string")
        if self.purpose is not None and not self.purpose.strip():
            raise ValueError("SecretRef.purpose must be non-empty when provided")

    def identity(self) -> str:
        """Deterministic identity for this reference."""
        base = f"secret:{self.provider}/{self.name}#{self.key}@{self.version}"
        if self.purpose:
            return f"{base}?purpose={self.purpose}"
        return base

    def to_dict(self) -> dict[str, Any]:
        """Serialize for plans and profiles (secret-free)."""
        data = asdict(self)
        return {k: v for k, v in data.items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SecretRef:
        """Deserialize a SecretRef from a mapping."""
        version_raw = data.get("version")
        purpose_raw = data.get("purpose")
        if version_raw is not None and not isinstance(version_raw, str):
            raise ValueError("SecretRef.version must be a string")
        if purpose_raw is not None and not isinstance(purpose_raw, str):
            raise ValueError("SecretRef.purpose must be a string or null")
        return cls(
            provider=str(data["provider"]),
            name=str(data["name"]),
            key=str(data["key"]),
            version="current" if version_raw is None else str(version_raw),
            purpose=purpose_raw,
        )
