"""Prefect ExecutionScheduler plugin tests."""

from __future__ import annotations

import os

import pytest

pytest.importorskip("prefect")
try:
    from prefect import flow as _prefect_flow  # noqa: F401
except ImportError:  # pragma: no cover - empty leftover namespace package
    pytest.skip("prefect package not installed", allow_module_level=True)

from etlantic import (
    Data,
    Extract,
    Input,
    Load,
    Output,
    Pipeline,
    PipelineRuntime,
    Profile,
    Transformation,
)
from etlantic.exceptions import ETLanticError
from etlantic.runtime.scheduler import SCHEDULER_PROTOCOL
from etlantic.runtime.scheduler_discovery import (
    discover_scheduler_plugins,
    resolve_scheduler,
)
from etlantic.runtime.state import RunStatus

pytestmark = pytest.mark.prefect

# Prefer in-process Prefect without requiring a durable API server.
os.environ.setdefault("PREFECT_LOGGING_TO_API_ENABLED", "false")


class _Raw(Data):
    customer_id: int
    first_name: str
    last_name: str


class _Out(Data):
    customer_id: int
    full_name: str


class _Normalize(Transformation):
    customers: Input[_Raw]
    result: Output[_Out]


@_Normalize.implementation("local")
def _normalize(customers: list[_Raw]) -> list[_Out]:
    return [
        _Out(
            customer_id=row.customer_id,
            full_name=f"{row.first_name} {row.last_name}",
        )
        for row in customers
    ]


class _Tiny(Pipeline):
    raw: Extract[_Raw] = Extract(asset="raw")
    normalized = _Normalize.step(customers=raw)
    out: Load[_Out] = Load(input=normalized.result, asset="out")


def test_prefect_discovered() -> None:
    found = discover_scheduler_plugins()
    assert "prefect" in found
    assert found["prefect"].info.name == "prefect"
    assert found["prefect"].info.direct_execution is True
    assert found["prefect"].info.external_compilation is False


def test_resolve_prefect_scheduler() -> None:
    scheduler = resolve_scheduler("prefect")
    assert scheduler.info.name == "prefect"


def test_airflow_not_a_scheduler() -> None:
    with pytest.raises(ETLanticError, match="compile target"):
        resolve_scheduler("airflow")


def test_prefect_conformance_suite() -> None:
    from etlantic.testing import run_scheduler_conformance_suite
    from etlantic_prefect import PrefectScheduler

    result = run_scheduler_conformance_suite(PrefectScheduler())
    assert result["scheduler"] == "prefect"
    assert result["status"] == "succeeded"


def test_pipeline_run_with_prefect_profile() -> None:
    runtime = PipelineRuntime()
    runtime.memory.seed(
        "raw",
        [_Raw(customer_id=1, first_name="Ada", last_name="Lovelace")],
    )
    report = _Tiny.run(
        profile=Profile(name="prefect-test", orchestrator="prefect"),
        runtime=runtime,
    )
    assert report.status is RunStatus.SUCCEEDED
    assert report.metadata.get("etlantic.scheduler") == "prefect"
    assert report.metadata.get("etlantic.scheduler_protocol") == SCHEDULER_PROTOCOL
    assert report.metadata.get("etlantic.prefect.run_id")
    assert report.run_id == report.metadata["etlantic.prefect.run_id"]
    correlation = report.metadata.get("etlantic.prefect.task_correlation") or {}
    assert set(correlation) >= {"raw", "normalized", "out"}
    assert runtime.memory.get("out")
