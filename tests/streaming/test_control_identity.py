"""Deterministic expansion identity and bounds (046-D)."""

from __future__ import annotations

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


def test_python_branch_diagnostic() -> None:
    diag = reject_python_branch()
    assert diag.code == "PMDYN120"


def test_control_kinds() -> None:
    assert is_control_kind(NodeKind.MAP)
    assert is_control_kind("compensation")
    assert not is_control_kind(NodeKind.STEP)
