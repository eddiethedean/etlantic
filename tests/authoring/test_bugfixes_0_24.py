"""Regression coverage for 0.24.0 top bugfixes."""

from __future__ import annotations

from pathlib import Path

import pytest
from examples.memory_customers import CustomerPipeline, normalize_customers

from etlantic.authoring import (
    EditCommand,
    apply_edit,
    connect,
    definition_from_pipeline,
    extract_node,
    load_node,
    pipeline_definition,
    pipeline_from_dict,
    pipeline_to_dict,
    read_pipeline_json,
    validate_pipeline_like,
    write_pipeline_json,
)
from etlantic.authoring.catalog import catalog_from_definition
from etlantic.cli.target import load_target
from etlantic.service import AuthoringService, PolicyContext


def test_read_pipeline_json_round_trip(tmp_path: Path) -> None:
    defn = definition_from_pipeline(CustomerPipeline)
    path = write_pipeline_json(defn, tmp_path / "pipe.json")
    loaded = read_pipeline_json(path)
    assert loaded.pipeline_id == defn.pipeline_id
    assert load_target(str(path)).pipeline_id == defn.pipeline_id


def test_missing_fingerprint_rejected_when_verify() -> None:
    defn = definition_from_pipeline(CustomerPipeline)
    data = pipeline_to_dict(defn)
    data.pop("fingerprint", None)
    with pytest.raises(ValueError, match="fingerprint required"):
        pipeline_from_dict(data, verify=True)


def test_secret_ref_with_value_rejected() -> None:
    defn = definition_from_pipeline(CustomerPipeline)
    data = pipeline_to_dict(defn)
    data["metadata"] = {
        "secret_ref": {"provider": "env", "name": "DB", "value": "hunter2"}
    }
    with pytest.raises(ValueError, match=r"secret_ref|secret"):
        pipeline_from_dict(data)


def test_api_token_key_rejected() -> None:
    defn = definition_from_pipeline(CustomerPipeline)
    data = pipeline_to_dict(defn)
    data["metadata"] = {"api_token": "x"}
    with pytest.raises(ValueError, match=r"forbidden|secret"):
        pipeline_from_dict(data)


def test_catalog_contract_ids_align_with_ports() -> None:
    defn = definition_from_pipeline(CustomerPipeline)
    catalog = catalog_from_definition(defn)
    contract_ids = {e.identity for e in catalog.entries if e.kind == "contract"}
    port_ids = {
        p.contract_id
        for n in defn.nodes
        for p in (*n.inputs, *n.outputs)
        if p.contract_id
    }
    assert port_ids
    assert port_ids <= contract_ids


def test_policy_allowlist_denies_unknown_asset() -> None:
    defn = definition_from_pipeline(CustomerPipeline)
    svc = AuthoringService(
        policy=PolicyContext(allowed_assets=("other",), allowed_actions=("edit",))
    )
    with pytest.raises(PermissionError, match="Asset"):
        svc.put_definition("x", pipeline_to_dict(defn))


def test_connect_rejects_unknown_port() -> None:
    defn = definition_from_pipeline(CustomerPipeline)
    with pytest.raises(ValueError, match="Unknown producer port"):
        connect(defn, "raw", "nope", "normalized", "customers")


def test_update_node_rename_rejected() -> None:
    defn = definition_from_pipeline(CustomerPipeline)
    node = defn.nodes[0]
    renamed = node.__class__.from_dict({**node.to_dict(), "name": "renamed"})
    with pytest.raises(ValueError, match="rename is not supported"):
        apply_edit(
            defn,
            EditCommand(
                op="update_node",
                payload={"name": node.name, "node": renamed.to_dict()},
            ),
        )


def test_catalog_lists_update_node() -> None:
    catalog = catalog_from_definition(definition_from_pipeline(CustomerPipeline))
    assert "update_node" in catalog.operations
    assert "update" not in catalog.operations


def test_definition_cycle_detected() -> None:
    from etlantic.authoring.definition import EdgeDefinition

    pid = "cycle.demo"
    cyclic = pipeline_definition(
        pipeline_id=pid,
        pipeline_name="Cycle",
        nodes=(
            extract_node("a", asset="a", contract_id="c", pipeline_id=pid),
            load_node("b", asset="b", contract_id="c", pipeline_id=pid),
        ),
        edges=(
            EdgeDefinition("a", "result", "b", "input"),
            EdgeDefinition("b", "input", "a", "result"),
        ),
    )
    report = validate_pipeline_like(cyclic, profile="development")
    assert report.has_errors
    assert any(d.code == "PMPIPE301" for d in report.diagnostics)


def test_submit_run_is_synchronous_reference() -> None:
    from etlantic.authoring.resolve import callable_registry

    defn = definition_from_pipeline(CustomerPipeline)
    callable_registry().register(
        defn.transformations[0].identity, "local", normalize_customers
    )
    svc = AuthoringService()
    put = svc.put_definition("demo", pipeline_to_dict(defn))
    assert put["fingerprint"]
    status = svc.submit_run("demo")
    assert status["run_model"] == "synchronous_reference"
    assert status["cancellable"] is False
    assert status["status"] in {"succeeded", "failed", "partial"}
    cancel = svc.cancel_run(status["job_id"])
    assert cancel["cancel_supported"] is False


def test_subpipeline_definition_from_pipeline() -> None:
    from etlantic import Extract, Load, Pipeline
    from tests.conftest import Customer, RawCustomer
    from tests.unit.test_subpipeline import CustomerCurationPipeline

    class Parent(Pipeline):
        inbound: Extract[RawCustomer] = Extract(asset="inbound")
        customers = CustomerCurationPipeline.subpipeline(raw=inbound)
        out: Load[Customer] = Load(input=customers.curated, asset="out")

    defn = definition_from_pipeline(Parent)
    nested = next(n for n in defn.nodes if n.kind == "subpipeline")
    assert nested.bindings["raw"] == {"node": "inbound", "port": "result"}
    round_trip = pipeline_from_dict(pipeline_to_dict(defn))
    assert any(n.kind == "subpipeline" for n in round_trip.nodes)
