"""Deterministic expansion identity and bounds (046-D)."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from etlantic.exceptions import PipelineValidationError
from etlantic.model import NodeKind
from etlantic.streaming import (
    ExpansionBounds,
    ExpansionSpec,
    child_identity,
    expand_children,
    is_control_kind,
    reject_python_branch,
)


def test_child_identity_is_deterministic() -> None:
    a = child_identity(
        plan_id="plan-a",
        parent_id="map-1",
        map_key="p0",
        input_snapshot_id="snap-1",
    )
    b = child_identity(
        plan_id="plan-a",
        parent_id="map-1",
        map_key="p0",
        input_snapshot_id="snap-1",
    )
    c = child_identity(
        plan_id="plan-a",
        parent_id="map-1",
        map_key="p1",
        input_snapshot_id="snap-1",
    )
    assert a == b
    assert a != c
    assert len(a) == 64


def test_expand_children_stable_order() -> None:
    spec = ExpansionSpec(parent_id="map-1", collection_identity="parts")
    first = expand_children(spec, ["a", "b"], plan_id="p", input_snapshot_id="s")
    second = expand_children(spec, ["a", "b"], plan_id="p", input_snapshot_id="s")
    assert [c.identity for c in first] == [c.identity for c in second]
    assert first[0].map_key == "a"


def test_duplicate_keys_fail_closed_before_identity_collision() -> None:
    spec = ExpansionSpec(parent_id="map-1", collection_identity="parts")
    with pytest.raises(PipelineValidationError) as exc:
        expand_children(spec, ["a", "a"], plan_id="p", input_snapshot_id="s")
    diagnostics = exc.value.report.diagnostics
    assert any(d.code == "PMDYN101" for d in diagnostics)
    assert any("duplicate map keys" in d.message for d in diagnostics)


class _OversizedKeys(Sequence[str]):
    def __len__(self) -> int:
        return 2

    def __getitem__(self, index: int) -> str:
        raise AssertionError(f"oversized keys should not be consumed: {index}")


def test_oversized_keys_fail_before_consumption() -> None:
    spec = ExpansionSpec(
        parent_id="map-1",
        collection_identity="parts",
        bounds=ExpansionBounds(max_children=1),
    )
    with pytest.raises(PipelineValidationError) as exc:
        expand_children(spec, _OversizedKeys(), plan_id="p", input_snapshot_id="s")
    assert any(d.code == "PMDYN101" for d in exc.value.report.diagnostics)


class _GrowingKeys(list[str]):
    def __iter__(self):
        self.append("a")
        return super().__iter__()


def test_keys_changed_during_consumption_fail_closed() -> None:
    spec = ExpansionSpec(parent_id="map-1", collection_identity="parts")
    with pytest.raises(PipelineValidationError) as exc:
        expand_children(
            spec, _GrowingKeys(["a", "b"]), plan_id="p", input_snapshot_id="s"
        )
    diagnostics = exc.value.report.diagnostics
    assert any(d.code == "PMDYN101" for d in diagnostics)
    assert any("changed" in d.message for d in diagnostics)


def test_bound_exhaustion_max_children() -> None:
    spec = ExpansionSpec(
        parent_id="map-1",
        collection_identity="parts",
        bounds=ExpansionBounds(max_children=2),
    )
    with pytest.raises(PipelineValidationError) as exc:
        expand_children(spec, ["a", "b", "c"], plan_id="p", input_snapshot_id="s")
    assert any(d.code == "PMDYN101" for d in exc.value.report.diagnostics)


def test_empty_keys_fail_closed() -> None:
    spec = ExpansionSpec(parent_id="map-1", collection_identity="parts")
    with pytest.raises(PipelineValidationError) as exc:
        expand_children(spec, [], plan_id="p", input_snapshot_id="s")
    assert any(d.code == "PMDYN100" for d in exc.value.report.diagnostics)


def test_from_dict_honors_zero_bounds() -> None:
    bounds = ExpansionBounds.from_dict(
        {"max_children": 0, "max_concurrency": 0, "max_depth": 0}
    )
    assert bounds.max_children == 0
    assert bounds.max_concurrency == 0
    assert bounds.max_depth == 0


def test_bound_exhaustion_max_concurrency() -> None:
    spec = ExpansionSpec(
        parent_id="map-1",
        collection_identity="parts",
        bounds=ExpansionBounds(max_concurrency=1),
    )
    with pytest.raises(PipelineValidationError) as exc:
        expand_children(spec, ["a", "b"], plan_id="p", input_snapshot_id="s")
    assert any(d.code == "PMDYN101" for d in exc.value.report.diagnostics)


def test_non_positive_duration_fails_closed() -> None:
    spec = ExpansionSpec(
        parent_id="map-1",
        collection_identity="parts",
        bounds=ExpansionBounds(max_duration_seconds=0),
    )
    with pytest.raises(PipelineValidationError) as exc:
        expand_children(spec, ["a"], plan_id="p", input_snapshot_id="s")
    assert any(d.code == "PMDYN101" for d in exc.value.report.diagnostics)
    diag = reject_python_branch()
    assert diag.code == "PMDYN120"


def test_control_kinds() -> None:
    assert is_control_kind(NodeKind.MAP)
    assert is_control_kind("compensation")
    assert not is_control_kind(NodeKind.STEP)
