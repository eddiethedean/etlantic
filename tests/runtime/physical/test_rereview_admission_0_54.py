# pyright: reportAssignmentType=false, reportAttributeAccessIssue=false, reportMissingParameterType=false, reportMissingTypeArgument=false, reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownVariableType=false
"""Focused admission regressions; no remote proof or approval records."""

from collections.abc import Mapping
from dataclasses import replace

import anyio
import pytest
from tests.plan.test_adaptive_planner_0_52 import adaptive_profile

from etlantic import (
    Data,
    Extract,
    Input,
    Load,
    Output,
    Parameter,
    Pipeline,
    PipelineRuntime,
    Transformation,
)
from etlantic.exceptions import PipelineExecutionError
from etlantic.plan import plan_from_json, plan_pipeline, plan_to_json
from etlantic.plan.freeze import mutable_copy
from etlantic.plan.serialize import plan_fingerprint
from etlantic.runtime.adaptive_admission import admit_adaptive_plan
from etlantic.runtime.adaptive_parameters import canonical_parameters
from etlantic.runtime.request import RunRequest
from etlantic.runtime.scheduler import LocalScheduler
from etlantic.transform import functions as F


class Row(Data):
    key: int


class DefaultFilter(Transformation):
    source: Input[Row]
    key: Parameter[int] = 1
    result: Output[Row]


@DefaultFilter.portable
def filter_rows(source, key):
    return source.filter(F.col("key") == key)


class DefaultPipeline(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    filtered = DefaultFilter.step(source=raw)
    out: Load[Row] = Load(input=filtered.result, asset="out")


def refingerprint(plan):
    fingerprint = plan_fingerprint(plan)
    return replace(plan, fingerprint=fingerprint, plan_id="plan:" + fingerprint[:16])


def local_plan(request=None):
    return plan_pipeline(
        DefaultPipeline, profile=adaptive_profile(), request=request or RunRequest()
    )


def test_unfused_default_one_json_roundtrip():
    plan = local_plan()
    assert plan.metadata["etlantic.runtime"]["parameters"]["filtered"]["key"] == 1
    decoded = plan_from_json(plan_to_json(plan))
    assert decoded.logical_graph.node_map()["filtered"].parameters[0].value is ...
    assert plan_to_json(decoded) == plan_to_json(plan)

    async def run():
        runtime = PipelineRuntime()
        runtime.memory.seed("rows", [{"key": 1}, {"key": 2}])
        report = await LocalScheduler().execute(
            decoded, request=RunRequest(), runtime=runtime
        )
        assert report.status.value == "succeeded", report.diagnostics
        assert [row.key for row in runtime.memory.get("out")] == [1]

    anyio.run(run)


@pytest.mark.parametrize(
    "mutation", ["missing", "name", "value", "typed", "unknown-node"]
)
def test_capture_closed_and_live_drift(mutation):
    plan = local_plan()
    metadata = mutable_copy(plan.metadata)
    parameters = metadata["etlantic.runtime"]["parameters"]
    if mutation == "missing":
        metadata["etlantic.runtime"].pop("parameters")
    elif mutation == "name":
        parameters["filtered"] = {"unknown": 1}
    elif mutation == "unknown-node":
        parameters["unknown"] = {}
    else:
        parameters["filtered"]["key"] = True if mutation == "typed" else 2
    altered = refingerprint(replace(plan, metadata=metadata))
    with pytest.raises(PipelineExecutionError, match="parameter"):
        admit_adaptive_plan(altered, request=RunRequest())
    if mutation == "missing":
        assert plan_from_json(plan_to_json(altered)).schema == "etlantic.plan/2"
        with pytest.raises(PipelineExecutionError):
            admit_adaptive_plan(
                plan_from_json(plan_to_json(altered)), request=RunRequest()
            )


def test_request_override_cannot_hide_live_graph_drift():
    request = RunRequest(parameter_overrides={"filtered": {"key": 2}})
    plan = local_plan(request)
    graph = replace(
        plan.logical_graph,
        nodes=tuple(
            replace(
                node,
                parameters=tuple(
                    replace(p, value=1, has_value=True) for p in node.parameters
                ),
            )
            if node.name == "filtered"
            else node
            for node in plan.logical_graph.nodes
        ),
    )
    with pytest.raises(PipelineExecutionError, match="parameter"):
        admit_adaptive_plan(
            refingerprint(replace(plan, logical_graph=graph)), request=request
        )


@pytest.mark.parametrize("kind", ["cycle", "depth", "wide", "custom", "nan"])
def test_parameter_traversal_is_bounded(kind):
    class Untrusted(Mapping):
        def __iter__(self):
            raise AssertionError("Custom mapping callback entered")

        def __len__(self):
            raise AssertionError("Custom mapping callback entered")

        def __getitem__(self, key):
            raise AssertionError("Custom mapping callback entered")

    if kind == "cycle":
        value = []
        value.append(value)
    elif kind == "depth":
        value = 1
        for _ in range(100):
            value = [value]
    else:
        value = (
            [0] * 10001
            if kind == "wide"
            else Untrusted()
            if kind == "custom"
            else float("nan")
        )
    with pytest.raises(ValueError):
        canonical_parameters(value)


def staged_plan():
    from etlantic.runtime.physical_operations import OPERATION_SCHEMA

    graph = DefaultPipeline.build_graph()
    graph = replace(
        graph,
        nodes=tuple(
            replace(
                node,
                metadata={
                    "etlantic.validation_required": {
                        "schema": OPERATION_SCHEMA,
                        "kind": "validation",
                    },
                    "etlantic.materialization_required": {
                        "schema": OPERATION_SCHEMA,
                        "kind": "materialization",
                        "checkpoint": "memory",
                    },
                    "etlantic.reuse_artifact": {
                        "schema": OPERATION_SCHEMA,
                        "kind": "reuse",
                        "checkpoint": "memory",
                    },
                },
            )
            if node.name == "out"
            else node
            for node in graph.nodes
        ),
    )
    scoped = type(
        "ScopedStages",
        (DefaultPipeline,),
        {"build_graph": classmethod(lambda cls: graph)},
    )
    return plan_pipeline(scoped, profile=adaptive_profile(), request=RunRequest())


def test_valid_multiple_sink_barriers_follow_lowering_order(monkeypatch):
    plan = staged_plan()
    before = plan_to_json(plan)
    admit_adaptive_plan(
        plan_from_json(before), request=RunRequest(), runtime=PipelineRuntime()
    )
    assert plan_to_json(plan) == before
    import etlantic.runtime.adaptive_admission as admission

    # Preserve frozen case identities while checking all sanitized failures.
    for failure in (
        ValueError("private-value"),
        TypeError("private-value"),
        KeyError("private-value"),
    ):

        def malformed(_plan, failure=failure):
            raise failure

        monkeypatch.setattr(admission, "_validate_required_boundaries", malformed)
        with pytest.raises(PipelineExecutionError) as error:
            admit_adaptive_plan(plan, request=RunRequest())
        assert error.value.code == "PMADP403"
        assert str(error.value) == "Adaptive logical barrier descriptor is invalid"
    own_error = PipelineExecutionError(
        "Existing admission rejection", code="PMADP403", stage="admission"
    )

    def rejected(_plan):
        raise own_error

    monkeypatch.setattr(admission, "_validate_required_boundaries", rejected)
    with pytest.raises(PipelineExecutionError) as error:
        admit_adaptive_plan(plan, request=RunRequest())
    assert error.value is own_error


@pytest.mark.parametrize("mutation", ["branch", "order"])
def test_sink_barrier_cannot_branch_or_reorder(mutation):
    plan = staged_plan()
    dag = plan.physical_dag
    stages = {
        u.kind.value: u
        for u in dag.units
        if u.kind.value in {"validation", "materialization", "reuse"}
    }
    compute = dag.logical_to_physical["out"]
    if mutation == "branch":
        units = tuple(
            replace(
                unit,
                dependencies=tuple(
                    replace(dep, unit_id=compute) for dep in unit.dependencies
                ),
            )
            if unit.kind.value == "publication"
            else unit
            for unit in dag.units
        )
        order = dag.topological_order
    else:
        previous = {
            "materialization": compute,
            "validation": stages["materialization"].identity,
            "reuse": stages["validation"].identity,
        }
        units = tuple(
            replace(
                unit,
                dependencies=tuple(
                    replace(dep, unit_id=previous[unit.kind.value])
                    for dep in unit.dependencies
                ),
            )
            if unit.kind.value in previous
            else unit
            for unit in dag.units
        )
        from etlantic.planning.adaptive import _topological_units

        order = _topological_units(list(units))
    plan = refingerprint(
        replace(plan, physical_dag=replace(dag, units=units, topological_order=order))
    )
    with pytest.raises(PipelineExecutionError) as error:
        admit_adaptive_plan(plan, request=RunRequest(), runtime=PipelineRuntime())
    assert error.value.code == "PMADP403"


def test_collection_keeps_producer_validation_on_data_path():
    from etlantic.runtime.physical_operations import (
        OPERATION_SCHEMA,
        validate_operation,
    )

    descriptor = {
        "schema": OPERATION_SCHEMA,
        "kind": "collection",
        "max_rows": 10,
        "max_bytes": 1000,
    }
    for field in ("max_rows", "max_bytes"):
        for invalid in (True, 1.0, 0, -1, None):
            with pytest.raises(ValueError):
                validate_operation("collection", {**descriptor, field: invalid})
    with pytest.raises(ValueError):
        validate_operation("collection", {**descriptor, "kind": "validation"})

    graph = DefaultPipeline.build_graph()
    graph = replace(
        graph,
        nodes=tuple(
            replace(
                node,
                metadata={
                    "etlantic.validation_required": {
                        "schema": OPERATION_SCHEMA,
                        "kind": "validation",
                    },
                },
            )
            if node.name == "raw"
            else replace(
                node,
                metadata={
                    "etlantic.collection_required": {
                        "schema": OPERATION_SCHEMA,
                        "kind": "collection",
                        "max_rows": 10,
                        "max_bytes": 1000,
                    },
                },
            )
            if node.name == "filtered"
            else node
            for node in graph.nodes
        ),
    )
    scoped = type(
        "ScopedCollection",
        (DefaultPipeline,),
        {"build_graph": classmethod(lambda cls: graph)},
    )
    plan = plan_pipeline(scoped, profile=adaptive_profile(), request=RunRequest())
    admit_adaptive_plan(
        plan_from_json(plan_to_json(plan)),
        request=RunRequest(),
        runtime=PipelineRuntime(),
    )


@pytest.mark.polars
@pytest.mark.pandas
@pytest.mark.parametrize(
    "mutation",
    [
        "request-two",
        "source-contract",
        "hooked-source-linked",
        "member-contract",
        "edge",
        "removed-validation",
        "branch-validation",
    ],
)
def test_fusion_and_barrier_bind_logical_authority(tmp_path, mutation):
    pytest.importorskip("polars")
    pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")
    from tests.runtime.physical.test_fusion_0_54 import setup
    from tests.runtime.physical.test_review_remediation_0_54 import PostInitRaw

    request = (
        RunRequest(parameter_overrides={"filtered": {"key": 2}})
        if mutation == "request-two"
        else RunRequest()
    )
    runtime, _, _, plan = setup(tmp_path, request)
    if mutation == "request-two":
        request = RunRequest(parameter_overrides={"filtered": {"key": 2}})
        metadata = mutable_copy(plan.metadata)
        metadata["etlantic.runtime"]["request"] = request.to_dict()
        metadata["etlantic.runtime"]["parameters"]["filtered"]["key"] = 2
        graph = replace(
            plan.logical_graph,
            nodes=tuple(
                replace(
                    node,
                    parameters=tuple(
                        replace(p, value=2, has_value=True) for p in node.parameters
                    ),
                )
                if node.name == "filtered"
                else node
                for node in plan.logical_graph.nodes
            ),
        )
        # Tamper a real request-2 descriptor, retaining generated guards.
        from etlantic.planning.adaptive import _digest
        from etlantic.transform.fusion import FusionDescriptor

        original = next(
            u for u in plan.physical_dag.units if u.metadata.get("etlantic.fusion")
        )
        descriptor = replace(
            FusionDescriptor.from_dict(original.metadata["etlantic.fusion"]),
            parameters={"key": 1},
        )
        region_ids = {}
        regions = []
        for region in plan.regions:
            if region.fused:
                target = next(
                    t for t in plan.inventory.targets if t.target_id == region.target_id
                )
                identity = (
                    "region:"
                    + _digest(
                        {
                            "target": target.identity,
                            "nodes": list(region.logical_nodes),
                            "security": region.security_domain,
                            "execution": "local-static-batch/1",
                            "policy": "conservative",
                            "fused": True,
                            "fusion_evidence": descriptor.fingerprint,
                            "planner": "0.53",
                        }
                    )[:24]
                )
                region_ids[region.identity] = identity
                region = replace(
                    region,
                    identity=identity,
                    metadata={
                        **mutable_copy(region.metadata),
                        "etlantic.fusion_evidence": descriptor.fingerprint,
                    },
                )
            regions.append(region)
        regions = tuple(
            replace(
                region,
                dependencies=tuple(
                    region_ids.get(uid, uid) for uid in region.dependencies
                ),
            )
            for region in regions
        )

        units = []
        replacements = {}
        for unit in plan.physical_dag.units:
            if unit.metadata.get("etlantic.fusion"):
                unit = replace(
                    unit,
                    metadata={
                        **mutable_copy(unit.metadata),
                        "etlantic.fusion": descriptor.to_dict(),
                        "etlantic.fusion_fingerprint": descriptor.fingerprint,
                        "etlantic.region": region_ids.get(
                            unit.metadata.get("etlantic.region"),
                            unit.metadata.get("etlantic.region"),
                        ),
                    },
                )
                from etlantic.plan.physical import generated_unit_identity

                identity = generated_unit_identity(
                    **{
                        name: getattr(unit, name)
                        for name in (
                            "kind",
                            "target_identity",
                            "logical_nodes",
                            "input_contracts",
                            "output_contracts",
                            "policy",
                            "retry_policy",
                            "ownership",
                            "protocol_versions",
                            "metadata",
                        )
                    }
                )
                replacements[unit.identity] = identity
                unit = replace(unit, identity=identity)
            units.append(unit)
        units = tuple(
            replace(
                unit,
                dependencies=tuple(
                    replace(dep, unit_id=replacements.get(dep.unit_id, dep.unit_id))
                    for dep in unit.dependencies
                ),
            )
            for unit in units
        )
        dag = replace(
            plan.physical_dag,
            units=units,
            logical_to_physical={
                name: replacements.get(uid, uid)
                for name, uid in plan.physical_dag.logical_to_physical.items()
            },
            topological_order=tuple(
                replacements.get(uid, uid)
                for uid in plan.physical_dag.topological_order
            ),
        )
        plan = replace(
            plan,
            metadata=metadata,
            logical_graph=graph,
            physical_dag=dag,
            regions=regions,
        )
    elif mutation == "hooked-source-linked":
        hooked_id = PostInitRaw.__module__ + ":PostInitRaw"
        graph = replace(
            plan.logical_graph,
            nodes=tuple(
                replace(
                    node,
                    contract_id=hooked_id,
                    contract_type=PostInitRaw,
                    outputs=tuple(
                        replace(port, contract_id=hooked_id, contract_type=PostInitRaw)
                        for port in node.outputs
                    ),
                )
                if node.name == "raw"
                else replace(
                    node,
                    inputs=tuple(
                        replace(port, contract_id=hooked_id, contract_type=PostInitRaw)
                        for port in node.inputs
                    ),
                )
                if node.name == "filtered"
                else node
                for node in plan.logical_graph.nodes
            ),
            edges=tuple(
                replace(
                    edge, producer_contract_id=hooked_id, consumer_contract_id=hooked_id
                )
                if edge.consumer_node == "filtered"
                else edge
                for edge in plan.logical_graph.edges
            ),
        )
        from etlantic.transform.fusion import fusion_digest

        metadata = mutable_copy(plan.metadata)
        metadata["etlantic.runtime"]["contracts"][hooked_id] = fusion_digest(
            PostInitRaw.model_json_schema()
        ).removeprefix("sha256:")
        plan = replace(plan, logical_graph=graph, metadata=metadata)
    elif mutation in {"source-contract", "member-contract"}:
        graph = replace(
            plan.logical_graph,
            nodes=tuple(
                replace(
                    node,
                    contract_id=PostInitRaw.__module__ + ":PostInitRaw",
                    contract_type=PostInitRaw,
                )
                if mutation == "source-contract" and node.name == "raw"
                else replace(
                    node,
                    inputs=tuple(
                        replace(port, contract_id="wrong:Contract")
                        for port in node.inputs
                    ),
                )
                if mutation == "member-contract" and node.name == "filtered"
                else node
                for node in plan.logical_graph.nodes
            ),
        )
        plan = replace(plan, logical_graph=graph)
    elif mutation == "edge":
        graph = replace(
            plan.logical_graph,
            edges=tuple(
                replace(edge, producer_contract_id="wrong:Contract")
                if edge.consumer_node == "filtered"
                else edge
                for edge in plan.logical_graph.edges
            ),
        )
        plan = replace(plan, logical_graph=graph)
    else:
        dag = plan.physical_dag
        barrier = next(u for u in dag.units if u.kind.value == "validation")
        upstream = barrier.dependencies[0].unit_id
        units = tuple(
            replace(
                unit,
                dependencies=tuple(
                    replace(dep, unit_id=upstream)
                    if dep.unit_id == barrier.identity
                    else dep
                    for dep in unit.dependencies
                ),
            )
            for unit in dag.units
            if mutation != "removed-validation" or unit.identity != barrier.identity
        )
        order = tuple(
            uid
            for uid in dag.topological_order
            if mutation != "removed-validation" or uid != barrier.identity
        )
        plan = replace(
            plan, physical_dag=replace(dag, units=units, topological_order=order)
        )
    with pytest.raises(PipelineExecutionError) as error:
        admit_adaptive_plan(
            plan_from_json(plan_to_json(refingerprint(plan))),
            request=request,
            runtime=runtime,
            workspace=tmp_path,
        )
    assert error.value.code == "PMADP403"
    assert runtime.memory.get("out") == []
    assert not list(tmp_path.iterdir())
