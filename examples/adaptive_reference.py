"""Executable public-only 0.54 Polars scan → Pandas development candidate."""

from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import ClassVar

import anyio
import polars as pl
from pydantic import ConfigDict

import etlantic as etl
from etlantic.io_policy import SafeIoPolicy
from etlantic.plan import plan_from_json, plan_pipeline, plan_to_json
from etlantic.profile import PlacementTarget
from etlantic.registry import BindingDescriptor, PlanningContext, PluginDescriptor
from etlantic.runtime import LocalScheduler, RunRequest
from etlantic.transform import functions as F
from etlantic.transform.fusion import PARQUET_CAPABILITY_EVIDENCE
from etlantic_pandas import create_plugin as pandas_plugin
from etlantic_polars import (
    create_parquet_storage,
    create_plugin,
    create_transform_compiler,
)


class Raw(etl.Data):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")
    key: int | None
    enabled: bool | None
    unused: int | None


class Selected(etl.Data):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")
    key: int | None
    enabled: bool | None


class Result(etl.Data):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")
    key: int | None


class Filter(etl.Transformation):
    source: etl.Input[Raw]
    key: etl.Parameter[int] = 1
    result: etl.Output[Raw]


@Filter.portable
def filter_rows(source, key):
    return source.filter(F.col("key") == key)


class Project(etl.Transformation):
    source: etl.Input[Raw]
    result: etl.Output[Selected]


@Project.portable
def project(source):
    return source.select("key", "enabled")


class Consumer(etl.Transformation):
    source: etl.Input[Selected]
    result: etl.Output[Result]


@Consumer.portable
def consume(source):
    return source.select("key")


class Reference(etl.Pipeline):
    raw: etl.Extract[Raw] = etl.Extract(asset="raw")
    filtered = Filter.step(source=raw)
    projected = Project.step(source=filtered.result)
    consumer = Consumer.step(source=projected.result)
    out: etl.Load[Result] = etl.Load(input=consumer.result, asset="out")

    @classmethod
    def build_graph(cls):
        graph = super().build_graph()
        return replace(
            graph,
            nodes=tuple(
                replace(
                    node,
                    metadata={
                        "etlantic.validation_required": {
                            "schema": "etlantic.physical_operation/1",
                            "kind": "validation",
                            "port": "result",
                            "outcome": "fail",
                        }
                    },
                )
                if node.name == "consumer"
                else node
                for node in graph.nodes
            ),
        )


def content_digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def candidate(root: Path):
    runtime = etl.PipelineRuntime()
    runtime.register_dataframe_plugin("polars", create_plugin())
    runtime.register_dataframe_plugin("pandas", pandas_plugin())
    source = create_parquet_storage()
    runtime.register_storage("polars-parquet", source)
    runtime.registry.register_binding(
        BindingDescriptor(
            "raw",
            "polars-parquet",
            location="raw.parquet",
            format="parquet",
            provider_version=etl.__version__,
            config=source.configuration(),
            config_fingerprint="sha256:" + content_digest(source.configuration()),
            metadata={
                "etlantic.parquet_capability_evidence": PARQUET_CAPABILITY_EVIDENCE
            },
            root_ref="workspace",
        )
    )
    targets = {
        "scan": PlacementTarget(engine="polars"),
        "consumer": PlacementTarget(engine="pandas"),
    }
    profile = etl.Profile(
        name="bounded-reference",
        execution_strategy="adaptive",
        portable_transform_policy="require",
        placement_targets=targets,
        eligible_targets=tuple(targets),
        implementation_overrides={
            node.name: "scan" if i < 3 else "consumer"
            for i, node in enumerate(Reference.build_graph().nodes)
        },
        safe_io={**SafeIoPolicy.for_root(root).to_dict(), "root_refs": ["workspace"]},
    )
    context = PlanningContext.create(profile, registry=runtime.registry)
    context.registry.transform_compilers["polars"] = create_transform_compiler()
    edge = next(
        e for e in Reference.build_graph().edges if e.consumer_node == "consumer"
    )
    # Static exact-direction descriptor, not a passing observation or approval.
    handoff = {
        "producer_target_identity": content_digest(targets["scan"].to_dict()),
        "consumer_target_identity": content_digest(targets["consumer"].to_dict()),
        "schema_fingerprint": content_digest(
            {
                "producer_contract_id": edge.producer_contract_id,
                "consumer_contract_id": edge.consumer_contract_id,
            }
        ),
        "format": "etlantic.contract/1",
        "mode": "batch",
        "durability": "ephemeral",
        "producer_capability_fingerprint": content_digest(
            context.registry.engines["polars"].to_dict()
        ),
        "consumer_capability_fingerprint": content_digest(
            context.registry.engines["pandas"].to_dict()
        ),
    }
    handoff["evidence_ref"] = "sha256:" + content_digest(handoff)
    context.registry.register_plugin(
        PluginDescriptor(
            "reference-arrow", "handoff", metadata={"handoff_evidence": [handoff]}
        )
    )
    plan = plan_pipeline(
        Reference, profile=profile, request=RunRequest(), context=context
    )
    return runtime, profile, plan


async def demonstrate(root: Path):
    root = root.resolve(strict=True)
    pl.DataFrame(
        {"key": [1, None, 2, 1], "enabled": [True] * 4, "unused": [99] * 4},
        schema={"key": pl.Int64, "enabled": pl.Boolean, "unused": pl.Int64},
    ).write_parquet(root / "raw.parquet")
    runtime, _, plan = candidate(root)
    report = await LocalScheduler().execute(
        plan_from_json(plan_to_json(plan)),
        request=RunRequest(),
        runtime=runtime,
        workspace=root,
    )
    assert report.status.value == "succeeded", report.diagnostics
    assert len(runtime.memory.get("out")) == 2
    proof = next(
        item["fusion"]
        for item in report.metadata["etlantic.physical_trace"]
        if "fusion" in item
    )
    assert proof["main_collections"] == 1
    print(
        "Experimental reference: one fused collection, one Arrow handoff, two published records"
    )


def main():
    with tempfile.TemporaryDirectory(prefix="etlantic-reference-") as directory:
        anyio.run(demonstrate, Path(directory))


if __name__ == "__main__":
    main()
