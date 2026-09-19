"""Runtime and CI regressions for the initial implementation review findings."""

import copy
import subprocess
from dataclasses import replace
from pathlib import Path

import anyio
import pytest
import yaml

pytest.importorskip("polars")
pytest.importorskip("pandas")
pytest.importorskip("pyarrow")

import polars as pl
from pydantic_core import core_schema
from tests.runtime.physical.fusion_fixture_0_54 import Raw, Reference
from tests.runtime.physical.test_fusion_0_54 import _seed, setup

from etlantic.io_policy import SafeIoPolicy
from etlantic.planning.adaptive import _transform_map
from etlantic.planning.fusion import recognize_fusion, schema_contract
from etlantic.runtime.request import RunRequest
from etlantic.runtime.scheduler import LocalScheduler
from etlantic.transform.fusion import FusionDescriptor
from etlantic_polars import create_parquet_storage
from etlantic_polars.fusion import inspect_fusion_query

pytestmark = [pytest.mark.polars, pytest.mark.pandas]


class PostInitRaw(Raw):
    def model_post_init(self, context):
        if self.key == 2:
            raise ValueError("Rejected source row")


class CustomInitRaw(Raw):
    def __init__(self, **values):
        super().__init__(**values)


class ValidateRaw(Raw):
    @classmethod
    def model_validate(cls, obj, **kwargs):
        raise ValueError("Rejected source row")


class CoreHookRaw(Raw):
    @classmethod
    def __get_pydantic_core_schema__(cls, source, handler):
        def reject(value):
            raise ValueError("Rejected source row")

        return core_schema.no_info_after_validator_function(reject, handler(source))


@pytest.mark.parametrize(
    "model", [PostInitRaw, CustomInitRaw, ValidateRaw, CoreHookRaw]
)
def test_custom_contract_hooks_are_not_schema_provable(model):
    with pytest.raises(ValueError, match="custom contract"):
        schema_contract(model, "review:raw")


def test_custom_source_hook_cannot_gain_fusion_authority(tmp_path):
    _, profile, context, plan = setup(tmp_path)
    graph = plan.logical_graph
    hooked = replace(
        graph,
        nodes=tuple(
            replace(n, contract_type=PostInitRaw) if n.name == "raw" else n
            for n in graph.nodes
        ),
    )
    assert (
        recognize_fusion(
            hooked,
            plan.decisions,
            tuple(
                (key, value, None) for key, value in profile.placement_targets.items()
            ),
            context,
            RunRequest(),
            _transform_map(Reference, None),
        )
        is None
    )
    with pytest.raises(ValueError, match="Rejected source row"):
        PostInitRaw.model_validate({"key": 2, "enabled": True, "unused": 99})
    assert not list(tmp_path.iterdir())


def test_live_hook_drift_rejects_before_source_read(tmp_path, monkeypatch):
    runtime, _, _, plan = setup(tmp_path)

    def validate(cls, obj, **kwargs):
        raise ValueError("Rejected source row")

    monkeypatch.setattr(Raw, "model_validate", classmethod(validate))

    async def run():
        from etlantic.exceptions import PipelineExecutionError

        with pytest.raises(PipelineExecutionError):
            await LocalScheduler().execute(
                plan, request=RunRequest(), runtime=runtime, workspace=tmp_path
            )

    anyio.run(run)
    assert not list(tmp_path.iterdir())
    assert runtime.memory.get("out") == []


def test_keyword_workspace_executes_actual_fused_query(tmp_path):
    root = tmp_path / "FILTER PROJECT 9" / "3 COLUMNS Parquet SCAN"
    root.mkdir(parents=True)
    _seed(root)
    runtime, _, _, plan = setup(root)

    async def run():
        report = await LocalScheduler().execute(
            plan, request=RunRequest(), runtime=runtime, workspace=root
        )
        assert report.status.value == "succeeded", report.diagnostics
        assert [row.key for row in runtime.memory.get("out")] == [1, 1]

    anyio.run(run)


@pytest.mark.parametrize("column", ["FILTER", "FILTER FIELD"])
def test_actual_keyword_columns_preserve_native_scan_proof(tmp_path, column):
    _, _, _, plan = setup(tmp_path)
    unit = next(u for u in plan.physical_dag.units if u.metadata.get("etlantic.fusion"))
    descriptor = FusionDescriptor.from_dict(unit.metadata["etlantic.fusion"])
    # The descriptor's syntax/type proof is identical after alpha-renaming the
    # column. Exercise native explain without fabricating positive query text.
    from etlantic.plan.freeze import mutable_copy

    first = copy.deepcopy(mutable_copy(descriptor.members[0].definition))
    second = copy.deepcopy(mutable_copy(descriptor.members[1].definition))
    first["actions"][0]["kind"]["parameters"]["predicate"]["left"]["target"] = column
    second["actions"][0]["kind"]["parameters"]["fields"] = [column, "enabled"]
    from types import SimpleNamespace

    view = SimpleNamespace(
        members=(SimpleNamespace(definition=first), SimpleNamespace(definition=second)),
        parameters={"key": 1},
    )
    path = tmp_path / "raw.parquet"
    pl.DataFrame(
        {column: [1, 2], "enabled": [True, True], "unused": [9, 9]}
    ).write_parquet(path)
    storage = create_parquet_storage()
    with storage.open_scan(
        location="raw.parquet", context={"safe_io": SafeIoPolicy.for_root(tmp_path)}
    ) as scan:
        assert "in-mem bytes" in scan.explain()
        query = scan.filter(pl.col(column) == 1).select(column, "enabled")
        proof = inspect_fusion_query(query, view)
        assert proof["scan_predicate"] and proof["scan_projection"]
        assert query.collect()[column].to_list() == [1]
    assert not storage.pending_snapshot_cleanups()


def test_standalone_filter_is_not_mistaken_for_scan_pushdown(tmp_path):
    _, _, _, plan = setup(tmp_path)
    unit = next(u for u in plan.physical_dag.units if u.metadata.get("etlantic.fusion"))
    descriptor = FusionDescriptor.from_dict(unit.metadata["etlantic.fusion"])

    class Query:
        def explain(self, **kwargs):
            return 'FILTER [(col("key")) == (1)]\nFROM\n  Parquet SCAN [FILTER workspace/source.parquet]\n  PROJECT 2/3 COLUMNS\n  SELECTION: [(col("key")) == (1)]'

    assert not inspect_fusion_query(Query(), descriptor)["scan_predicate"]


def workflow():
    return yaml.safe_load(
        (
            Path(__file__).resolve().parents[3] / ".github/workflows/checks.yml"
        ).read_text()
    )


def test_ci_proofs_are_outside_checkout_and_do_not_dirty_git(tmp_path):
    jobs = workflow()["jobs"]
    steps = jobs["checks"]["steps"] + jobs["adaptive-evidence"]["steps"]
    for step in steps:
        command = step.get("run", "")
        if "--output" in command or "--aggregate" in command:
            assert "${{ runner.temp }}/adaptive-" in command
        with_args = step.get("with", {})
        if "adaptive-0." in str(with_args.get("path", "")):
            assert str(with_args["path"]).startswith("${{ runner.temp }}/")
    checkout = tmp_path / "checkout"
    checkout.mkdir()

    def git(*args):
        return subprocess.check_output(
            ["git", "-C", str(checkout), *args], text=True
        ).strip()

    git("init", "-q")
    git(
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "fixture",
    )
    (tmp_path / "adaptive-0.53-proof").mkdir()
    (tmp_path / "adaptive-0.53-proof/qualification.json").write_text("{}")
    assert git("status", "--porcelain") == ""


def test_fastapi_ci_requires_both_provider_backends():
    steps = workflow()["jobs"]["fastapi"]["steps"]
    assert any(
        "--extra fastapi --group sqlmodel" in step.get("run", "") for step in steps
    )
    step = next(step for step in steps if "tests/fastapi" in step.get("run", ""))
    assert step["env"]["ETLANTIC_REQUIRE_SQLMODEL"] == "1"
