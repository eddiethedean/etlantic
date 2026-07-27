"""deep_freeze set/frozenset regression."""

from __future__ import annotations

from types import MappingProxyType

import pytest

from etlantic.plan.freeze import deep_freeze


def test_deep_freeze_sets() -> None:
    frozen = deep_freeze({"tags": {"a", "b"}, "nested": [{"x": {1, 2}}]})
    assert isinstance(frozen, MappingProxyType)
    assert isinstance(frozen["tags"], frozenset)
    assert frozen["tags"] == frozenset({"a", "b"})
    assert isinstance(frozen["nested"][0]["x"], frozenset)
    with pytest.raises(AttributeError):
        frozen["tags"].add("c")  # type: ignore[attr-defined]
