# pyright: reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownVariableType=false
"""Public-only provider fixtures and non-authoritative safe conformance results."""

from __future__ import annotations

import json
from dataclasses import replace

import anyio
import pytest

from etlantic import (
    Data,
    Extract,
    Input,
    Load,
    Output,
    Parameter,
    Pipeline,
    PipelineRuntime,
    Profile,
    Transformation,
)
from etlantic.profile import PlacementTarget
from etlantic.runtime import RunRequest
from etlantic.testing import (
    AdaptiveConformanceCase,
    arun_adaptive_provider_conformance_suite,
    run_adaptive_provider_conformance_suite,
)
from etlantic.transform import functions as F


class Row(Data):
    key: int | None


class Project(Transformation):
    source: Input[Row]
    result: Output[Row]


@Project.portable
def project(source):
    return source.select("key")


class Chain(Pipeline):
    raw: Extract[Row] = Extract(asset="raw")
    projected = Project.step(source=raw)
    out: Load[Row] = Load(input=projected.result, asset="out")


class MultiSource(Pipeline):
    raw: Extract[Row] = Extract(asset="raw")
    unused: Extract[Row] = Extract(asset="unused")
    projected = Project.step(source=raw)
    out: Load[Row] = Load(input=projected.result, asset="out")


class RequiredFilter(Transformation):
    source: Input[Row]
    key: Parameter[int]
    result: Output[Row]


@RequiredFilter.portable
def required_filter(source, key):
    return source.filter(F.col("key") == key)


class RequiredParameterChain(Pipeline):
    raw: Extract[Row] = Extract(asset="raw")
    filtered = RequiredFilter.step(source=raw)
    out: Load[Row] = Load(input=filtered.result, asset="out")


def case(case_id="local", **changes):
    def factory():
        runtime = PipelineRuntime()
        runtime.memory.seed("raw", [{"key": 1}, {"key": None}, {"key": 1}])
        return runtime

    def verify(runtime, plan, report):
        assert [row.key for row in runtime.memory.get("out")] == [1, None, 1]
        assert plan.schema == "etlantic.plan/2"
        assert report.status.value == "succeeded"

    result = AdaptiveConformanceCase(
        case_id,
        Chain,
        Profile(
            name="provider-suite",
            execution_strategy="adaptive",
            portable_transform_policy="require",
            placement_targets={"local": PlacementTarget(engine="local")},
            eligible_targets=("local",),
        ),
        RunRequest(),
        factory,
        verify,
    )
    return replace(result, **changes)


def test_actual_public_stored_execution_and_canonical_results():
    report = run_adaptive_provider_conformance_suite([case("z"), case("a")])
    assert report.passed
    payload = report.to_dict()
    assert payload["schema"] == "etlantic.adaptive_provider_conformance/1"
    assert [r["case_id"] for r in payload["results"]] == ["a", "z"]
    assert all(r["fingerprint"] for r in payload["results"])
    assert "raw" not in json.dumps(payload)


@pytest.mark.parametrize("mode", ["planning", "execution"])
@pytest.mark.parametrize("supplied", [True, False])
def test_required_parameter_from_request(mode, supplied):
    def verify(runtime, plan, report):
        if not supplied:
            assert plan is report is None
            assert runtime.memory.get("out") == []
        elif mode == "planning":
            assert plan is not None and report is None
        else:
            assert report.status.value == "succeeded"
            assert [row.key for row in runtime.memory.get("out")] == [1, 1]

    report = run_adaptive_provider_conformance_suite(
        [
            case(
                pipeline=RequiredParameterChain,
                mode=mode,
                request=RunRequest(
                    parameter_overrides={"filtered": {"key": 1}} if supplied else {}
                ),
                expected_acceptance=supplied,
                expected_code=None if supplied else "PMTRN102",
                verify=verify,
            )
        ]
    )
    assert report.passed
    assert report.results[0].observed_acceptance is supplied


@pytest.mark.parametrize(
    "changes",
    [
        {"case_id": "../unsafe"},
        {"case_id": ""},
        {"verify": None},
        {"mode": "unknown"},
        {"profile": "development"},
        {"request": None},
        {"expected_acceptance": 1},
        {"expected_acceptance": False},
        {"expected_code": "PMADP500"},
        {"expected_acceptance": False, "expected_code": "unknown"},
        {"pipeline": object()},
    ],
)
def test_malformed_catalogue_before_factories(changes):
    called = []
    invalid = case(runtime_factory=lambda: called.append(True))
    invalid = replace(invalid, **changes)
    with pytest.raises(ValueError):
        run_adaptive_provider_conformance_suite(
            [case("good", runtime_factory=lambda: called.append(True)), invalid]
        )
    assert called == []


def test_empty_duplicate_and_catalogue_bound_before_factories():
    called = []
    item = case(runtime_factory=lambda: called.append(True))
    for catalogue in (
        [],
        [item, item],
        [replace(item, case_id=f"c{i}") for i in range(257)],
    ):
        with pytest.raises(ValueError):
            run_adaptive_provider_conformance_suite(catalogue)
    assert called == []


def test_expected_unqualified_execution_rejects_without_reads():
    called = []

    def factory():
        runtime = PipelineRuntime()
        original = runtime.memory.read

        async def read(**kwargs):
            called.append(True)
            return await original(**kwargs)

        runtime.memory.read = read
        return runtime

    report = run_adaptive_provider_conformance_suite(
        [
            case(
                pipeline=MultiSource,
                runtime_factory=factory,
                expected_acceptance=False,
                expected_code="PMADP500",
                verify=lambda runtime, plan, report: not called,
            )
        ]
    )
    assert report.passed
    assert report.to_dict()["results"][0]["code"] == "PMADP500"
    assert called == []


def test_oracle_failure_is_safe_behavioral_failure():
    def verify(*args):
        raise AssertionError("source-row-and-secret-canary")

    report = run_adaptive_provider_conformance_suite([case(verify=verify)])
    assert not report.passed
    assert "canary" not in json.dumps(report.to_dict())


def test_hostile_oracle_serializer_never_runs():
    calls = []

    class Hostile:
        def to_dict(self):
            calls.append("serialized")
            raise AssertionError("secret-canary")

    with pytest.raises(ValueError, match="oracle"):
        run_adaptive_provider_conformance_suite([case(verify=lambda *args: Hostile())])
    assert not calls


def test_reused_runtime_is_harness_error():
    runtime = PipelineRuntime()
    with pytest.raises(ValueError, match="factory"):
        run_adaptive_provider_conformance_suite(
            [
                case(
                    "a",
                    mode="planning",
                    runtime_factory=lambda: runtime,
                    verify=lambda *args: True,
                ),
                case(
                    "b",
                    mode="planning",
                    runtime_factory=lambda: runtime,
                    verify=lambda *args: True,
                ),
            ]
        )


def test_sync_loop_guard_and_async_entry_point():
    async def exercise():
        called = []
        with pytest.raises(RuntimeError, match="async"):
            run_adaptive_provider_conformance_suite(
                [case(runtime_factory=lambda: called.append(True))]
            )
        assert not called
        assert (await arun_adaptive_provider_conformance_suite([case()])).passed

    anyio.run(exercise)


def test_async_cancellation_propagates_after_active_read_cleanup():
    async def exercise():
        entered, drained = anyio.Event(), anyio.Event()

        def factory():
            runtime = PipelineRuntime()

            async def read(**kwargs):
                entered.set()
                try:
                    await anyio.sleep_forever()
                finally:
                    drained.set()

            runtime.memory.read = read
            return runtime

        finished = []
        callbacks = []

        async def run():
            await arun_adaptive_provider_conformance_suite(
                [
                    case(
                        "a",
                        runtime_factory=factory,
                        expected_acceptance=False,
                        expected_code="PMEXEC409",
                        verify=lambda *args: callbacks.append("oracle"),
                    ),
                    case("b", runtime_factory=lambda: callbacks.append("next_factory")),
                ]
            )
            finished.append(True)

        with anyio.fail_after(10):
            async with anyio.create_task_group() as tasks:
                tasks.start_soon(run)
                await entered.wait()
                tasks.cancel_scope.cancel()
        assert drained.is_set()
        assert not finished
        assert callbacks == []

    anyio.run(exercise)


@pytest.mark.parametrize("expected_acceptance", [True, False])
def test_direct_task_cancel_drains_without_oracle_or_next_factory(expected_acceptance):
    import asyncio

    async def exercise():
        entered, drained = anyio.Event(), anyio.Event()
        calls = []

        def factory():
            runtime = PipelineRuntime()

            async def read(**kwargs):
                entered.set()
                try:
                    await anyio.sleep_forever()
                finally:
                    with anyio.CancelScope(shield=True):
                        await anyio.sleep(0)
                        drained.set()

            runtime.memory.read = read
            return runtime

        task = asyncio.create_task(
            arun_adaptive_provider_conformance_suite(
                [
                    case(
                        "a",
                        runtime_factory=factory,
                        expected_acceptance=expected_acceptance,
                        expected_code=None if expected_acceptance else "PMEXEC409",
                        verify=lambda *args: calls.append("oracle"),
                    ),
                    case("b", runtime_factory=lambda: calls.append("next_factory")),
                ]
            )
        )
        with anyio.fail_after(10):
            await entered.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert drained.is_set()
        assert calls == []

    anyio.run(exercise)
