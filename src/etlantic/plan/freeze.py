"""Helpers that freeze plan-owned nested mappings, lists, and sets.

Not full object-graph immutability: dataclass instances and unknown objects
pass through unchanged. Nested dataclass fields stay mutable so execution can
``deepcopy`` portable plans and other descriptor payloads.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import is_dataclass
from types import MappingProxyType
from typing import Any


def deep_freeze(value: Any) -> Any:
    """Freeze nested mappings, sequences, and sets for plan-owned values.

    Args:
        value: Arbitrary nested value owned by a plan graph.

    Returns:
        A structure where mappings become ``MappingProxyType``, lists/tuples
        become tuples, and sets become frozensets. Primitives, dataclass
        instances, and unknown objects are returned unchanged (fields are
        not recursively frozen — ``MappingProxyType`` is not picklable, and
        runtime portable compilation deep-copies descriptor payloads).

    Note:
        Callers may still observe mutation if they retain references to
        unfrozen dataclass fields or opaque objects. Top-level plan maps
        (implementations, metadata, …) are still frozen via this helper.
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
    """Return a deeply frozen mapping proxy for ``d`` (empty if ``None``).

    Args:
        d: Optional mapping to freeze.

    Returns:
        ``MappingProxyType`` with nested mappings/lists/sets frozen via
        :func:`deep_freeze`.
    """
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
