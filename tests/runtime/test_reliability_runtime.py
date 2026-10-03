# pyright: reportOptionalOperand=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnusedFunction=false
"""Reliability runtime helper and Pipeline.run e2e tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from etlantic import (
    Data,
    Extract,
    Input,
    Load,
    Output,
    Pipeline,
    PipelineRuntime,
    Transformation,
)
from etlantic.exceptions import PipelineExecutionError
from etlantic.reliability import (
    FreshnessExpectation,
    PartitionCompletenessExpectation,
    RetrySafetyDeclaration,
)
from etlantic.reliability_runtime import (
    assert_retry_safe,
    check_freshness,
    coerce_observed_at,
    invalidation_targets,
    minimum_safe_repair,
    resolve_freshness_observed_at,
)
from etlantic.runtime.request import InvalidationMode, RetryPolicy, RunRequest
from etlantic.runtime.state import RunStatus


class Row(Data):
    id: int
    name: str
    region: str = "us"


class Normalize(Transformation):
    rows: Input[Row]
    result: Output[Row]


@Normalize.implementation("local")
def normalize_local(rows: list[Row]) -> list[Row]:
    return [Row(id=r.id, name=r.name.strip().title(), region=r.region) for r in rows]


class SimplePipeline(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    normalized = Normalize.step(rows=raw)
    out: Load[Row] = Load(input=normalized.result, asset="out")


def test_freshness_check() -> None:
    exp = FreshnessExpectation(subject_id="s", max_age_seconds=60)
    now = datetime.now(UTC)
    ok = check_freshness(exp, observed_at=now - timedelta(seconds=10), now=now)
    assert ok.ok
    bad = check_freshness(exp, observed_at=now - timedelta(seconds=120), now=now)
    assert not bad.ok


def test_check_freshness_none_observed_fails_closed() -> None:
    exp = FreshnessExpectation(subject_id="s", max_age_seconds=60)
    result = check_freshness(exp, observed_at=None)
    assert result.ok is False
    assert "No observed timestamp" in (result.message or "")


def test_resolve_freshness_observed_at_from_metadata() -> None:
    exp = FreshnessExpectation(subject_id="raw", max_age_seconds=60)
    now = datetime.now(UTC)
    resolved = resolve_freshness_observed_at(
        exp,
        node_name="raw",
        binding="rows",
        metadata={"freshness_observed_at": {"raw": now.isoformat()}},
    )
    assert coerce_observed_at(resolved) is not None
    assert abs((resolved - now).total_seconds()) < 1


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


def test_freshness_missing_observed_at_fails_run() -> None:
    runtime = PipelineRuntime()
    runtime.memory.seed("rows", [Row(id=1, name="a")])
    report = SimplePipeline.run(
        profile="development",
        runtime=runtime,
        request=RunRequest(
            metadata={
                "freshness": {
                    "raw": FreshnessExpectation(subject_id="raw", max_age_seconds=3600)
                }
            }
        ),
    )
    assert report.status in {RunStatus.FAILED, RunStatus.PARTIAL}
    assert any(d.code == "PMEXEC350" for d in report.diagnostics)


def test_freshness_with_observed_at_succeeds() -> None:
    runtime = PipelineRuntime()
    runtime.memory.seed("rows", [Row(id=1, name="a")])
    now = datetime.now(UTC)
    report = SimplePipeline.run(
        profile="development",
        runtime=runtime,
        request=RunRequest(
            metadata={
                "freshness": {
                    "raw": FreshnessExpectation(subject_id="raw", max_age_seconds=3600)
                },
                "freshness_observed_at": {"raw": now},
            }
        ),
    )
    assert report.status is RunStatus.SUCCEEDED
    assert not any(d.code == "PMEXEC350" for d in report.diagnostics)


def test_freshness_stale_data_fails_run() -> None:
    runtime = PipelineRuntime()
    runtime.memory.seed("rows", [Row(id=1, name="a")])
    stale = datetime.now(UTC) - timedelta(hours=2)
    report = SimplePipeline.run(
        profile="development",
        runtime=runtime,
        request=RunRequest(
            metadata={
                "freshness": {
                    "raw": FreshnessExpectation(subject_id="raw", max_age_seconds=60)
                },
                "freshness_observed_at": {"raw": stale},
            }
        ),
    )
    assert report.status in {RunStatus.FAILED, RunStatus.PARTIAL}
    assert any(d.code == "PMEXEC350" for d in report.diagnostics)


def test_partition_completeness_minimum_count() -> None:
    runtime = PipelineRuntime()
    runtime.memory.seed(
        "rows",
        [Row(id=1, name="a", region="us"), Row(id=2, name="b", region="eu")],
    )
    ok_report = SimplePipeline.run(
        profile="development",
        runtime=runtime,
        request=RunRequest(
            metadata={
                "partitions": {
                    "raw": PartitionCompletenessExpectation(
                        subject_id="raw",
                        partition_keys=("region",),
                        minimum_count=2,
                    )
                }
            }
        ),
    )
    assert ok_report.status is RunStatus.SUCCEEDED

    runtime2 = PipelineRuntime()
    runtime2.memory.seed("rows", [Row(id=1, name="a", region="us")])
    bad_report = SimplePipeline.run(
        profile="development",
        runtime=runtime2,
        request=RunRequest(
            metadata={
                "partitions": {
                    "raw": PartitionCompletenessExpectation(
                        subject_id="raw",
                        partition_keys=("region",),
                        minimum_count=2,
                    )
                }
            }
        ),
    )
    assert bad_report.status in {RunStatus.FAILED, RunStatus.PARTIAL}
    assert any(d.code == "PMEXEC351" for d in bad_report.diagnostics)


def test_partition_lineage_links_committed_output_without_row_values() -> None:
    runtime = PipelineRuntime()
    private_regions = ("private-region-alpha", "private-region-beta")
    runtime.memory.seed(
        "rows",
        [
            Row(id=1, name="a", region=private_regions[0]),
            Row(id=2, name="b", region=private_regions[1]),
        ],
    )
    report = SimplePipeline.run(
        profile="development",
        runtime=runtime,
        request=RunRequest(
            metadata={
                "partitions": {
                    "raw": PartitionCompletenessExpectation(
                        subject_id="raw",
                        partition_keys=("region",),
                        minimum_count=2,
                    )
                }
            }
        ),
    )

    assert report.status is RunStatus.SUCCEEDED
    partition_lineage = report.metadata["etlantic.partition_lineage"]
    assert partition_lineage["source_nodes"] == 1
    assert partition_lineage["output_nodes"] == 1
    assert partition_lineage["outputs"][0]["partition_keys"] == ["region"]
    assert partition_lineage["outputs"][0]["produced_partitions"] == 2
    produced_edges = [
        edge for edge in report.lineage if edge.get("kind") == "produced_partition"
    ]
    assert len(produced_edges) == 2
    assert all(edge["from"].startswith("node:") for edge in produced_edges)
    serialized_report = report.to_json()
    assert all(value not in serialized_report for value in private_regions)


def test_retry_safety_blocks_unsafe_retry() -> None:
    class Boom(Transformation):
        rows: Input[Row]
        result: Output[Row]

    calls = {"n": 0}

    @Boom.implementation("local")
    def boom_local(rows: list[Row]) -> list[Row]:
        calls["n"] += 1
        raise RuntimeError("boom")

    class BoomPipeline(Pipeline):
        raw: Extract[Row] = Extract(asset="rows")
        step = Boom.step(rows=raw)
        out: Load[Row] = Load(input=step.result, asset="out")

    runtime = PipelineRuntime()
    runtime.memory.seed("rows", [Row(id=1, name="a")])
    report = BoomPipeline.run(
        profile="development",
        runtime=runtime,
        request=RunRequest(
            retry=RetryPolicy(max_attempts=3, backoff_seconds=0),
            metadata={
                "retry_safety": {
                    "step": RetrySafetyDeclaration(subject_id="step", safe=False)
                }
            },
        ),
    )
    assert report.status in {RunStatus.FAILED, RunStatus.PARTIAL}
    # First attempt fails; retry is rejected as unsafe before a second invoke.
    assert calls["n"] == 1
    assert any(d.code == "PMEXEC501" for d in report.diagnostics)
    step = next(s for s in report.steps if s.step_name == "step")
    assert step.attempts == 1
