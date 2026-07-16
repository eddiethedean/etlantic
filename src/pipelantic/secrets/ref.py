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
        return cls(
            provider=str(data["provider"]),
            name=str(data["name"]),
            key=str(data["key"]),
            version=str(data.get("version") or "current"),
            purpose=data.get("purpose"),
        )
