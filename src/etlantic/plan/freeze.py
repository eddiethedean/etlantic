"""Helpers that freeze plan-owned nested mappings, lists, and sets.

Dataclass instances owned by plans have known mapping fields frozen in place
(``metadata``, ``requirements``, ``support_summary``, ``portable_plan``).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from types import MappingProxyType
from typing import Any

_DATACLASS_MAPPING_FIELDS = frozenset(
    {
        "metadata",
        "requirements",
        "support_summary",
        "portable_plan",
    }
)


def deep_freeze(value: Any) -> Any:
    """Freeze nested mappings, sequences, sets, and plan dataclass fields.

    Args:
        value: Arbitrary nested value owned by a plan graph.

    Returns:
        A structure where mappings become ``MappingProxyType``, lists/tuples
        become tuples, and sets become frozensets. Dataclass instances have
        known mapping fields frozen via ``object.__setattr__``.
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
        names = {f.name for f in fields(value)}
        for field_name in _DATACLASS_MAPPING_FIELDS:
            if field_name not in names:
                continue
            field_val = getattr(value, field_name)
            if field_val is None:
                continue
            if isinstance(field_val, (dict, Mapping, list, tuple, set, frozenset)):
                object.__setattr__(value, field_name, deep_freeze(field_val))
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
