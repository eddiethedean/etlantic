"""Typed outbound event declarations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class OutboundEvent(Generic[T]):
    """Declared outbound event that a pipeline may emit."""

    name: str
    payload_type: type[T] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Emit(Generic[T]):
    """Runtime emission of an outbound event (payload must be secret-free)."""

    event: str
    payload: T
    metadata: dict[str, Any] = field(default_factory=dict)
