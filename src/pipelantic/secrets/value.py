"""Runtime-only secret values (never serialized into plans or reports)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class SecretSerializationError(TypeError):
    """Raised when a SecretValue is asked to serialize."""


@dataclass(slots=True)
class SecretValue:
    """Runtime-only secret payload with redacted display.

    Must never appear in plans, reports, events, or logs. Prefer passing this
    only to the declared resource consumer.
    """

    _value: Any
    provider: str
    name: str
    key: str
    version: str = "current"
    content_type: str = "text"

    @property
    def value(self) -> Any:
        """Return the underlying secret payload."""
        return self._value

    def get_secret_value(self) -> Any:
        """Alias for frameworks that expect pydantic-style accessors."""
        return self._value

    def __repr__(self) -> str:
        return (
            f"SecretValue(provider={self.provider!r}, name={self.name!r}, "
            f"key={self.key!r}, version={self.version!r}, value=***)"
        )

    def __str__(self) -> str:
        return "***"

    def __bool__(self) -> bool:
        return self._value is not None and self._value != ""

    def to_dict(self) -> dict[str, Any]:
        """Refuse serialization of secret values."""
        raise SecretSerializationError(
            "SecretValue cannot be serialized; use SecretRef identities only."
        )

    def __getstate__(self) -> dict[str, Any]:
        raise SecretSerializationError("SecretValue cannot be pickled.")
