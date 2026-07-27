"""Deep immutability helpers for plan-owned nested values."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import is_dataclass
from types import MappingProxyType
from typing import Any


def deep_freeze(value: Any) -> Any:
    """Recursively freeze nested mappings and sequences.

    - ``dict`` / ``Mapping`` → ``MappingProxyType``
    - ``list`` → ``tuple``
    - ``set`` / ``frozenset`` → ``frozenset``
    - primitives and frozen dataclass instances are left alone
    """
    if value is None or isinstance(value, (bool, int, float, str, bytes, complex)):
        return value
    if isinstance(value, MappingProxyType):
        return MappingProxyType({k: deep_freeze(v) for k, v in value.items()})
    if isinstance(value, Mapping):
        return MappingProxyType({k: deep_freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(deep_freeze(v) for v in value)
    if isinstance(value, tuple):
        return tuple(deep_freeze(v) for v in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(deep_freeze(v) for v in value)
    if is_dataclass(value) and not isinstance(value, type):
        return value
    return value


def immutable_mapping(d: Mapping[str, Any] | None = None) -> MappingProxyType[str, Any]:
    """Return a deeply frozen mapping proxy for ``d`` (empty if ``None``)."""
    return deep_freeze(dict(d or {}))


def mutable_copy(value: Any) -> Any:
    """Deep-copy into mutable ``dict`` / ``list`` structure for ``to_dict``."""
    if isinstance(value, Mapping):
        return {k: mutable_copy(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [mutable_copy(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return [mutable_copy(v) for v in value]
    return value
