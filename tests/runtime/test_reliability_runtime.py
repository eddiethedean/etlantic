"""Reliability runtime helper tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from pipelantic.exceptions import PipelineExecutionError
from pipelantic.reliability import FreshnessExpectation, RetrySafetyDeclaration
from pipelantic.reliability_runtime import (
    assert_retry_safe,
    check_freshness,
    invalidation_targets,
    minimum_safe_repair,
)
from pipelantic.runtime.request import InvalidationMode


def test_freshness_check() -> None:
    exp = FreshnessExpectation(subject_id="s", max_age_seconds=60)
    now = datetime.now(UTC)
    ok = check_freshness(exp, observed_at=now - timedelta(seconds=10), now=now)
    assert ok.ok
    bad = check_freshness(exp, observed_at=now - timedelta(seconds=120), now=now)
    assert not bad.ok


def test_retry_safety() -> None:
    decl = RetrySafetyDeclaration(subject_id="step", safe=False)
    assert_retry_safe(decl, attempt=1, step_name="step", run_id="r")
    with pytest.raises(PipelineExecutionError):
        assert_retry_safe(decl, attempt=2, step_name="step", run_id="r")


def test_repair_and_invalidation() -> None:
    repair = minimum_safe_repair(
        failed_nodes={"b"},
        downstream={"a": {"b"}, "b": {"c"}, "c": set()},
    )
    assert set(repair.affected_nodes) == {"b", "c"}
    targets = invalidation_targets(
        graph_nodes=["a", "b", "c"],
        target="b",
        mode=InvalidationMode.DOWNSTREAM,
        downstream={"a": {"b"}, "b": {"c"}, "c": set()},
    )
    assert targets == {"b", "c"}
