"""Regression tests for 0.2 P0/P1 correctness bugs."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from contractmodel import ContractModel
from tests.conftest import Customer, RawCustomer

from etlantic import (
    Extract,
    Input,
    Load,
    Output,
    Parameter,
    Pipeline,
    Transformation,
    diff_pipelines,
    graphs_equivalent,
    load_bundle,
    load_data_contract,
    write_contracts,
    write_odcs,
)
from etlantic.interchange.bundle import BundleError
from etlantic.interchange.diff import diff_transformations
from etlantic.interchange.dtcs import transformation_from_dtcs
from etlantic.interchange.odcs import dtcs_type_for_logical_type


class Event(ContractModel):
    when: datetime
    score: float


class CustomerA(ContractModel):
    id: int


class CustomerB(ContractModel):
    id: int
    extra: str


def test_dtcs_type_mapping_accepts_float_and_datetime() -> None:
    assert dtcs_type_for_logical_type("number") == "decimal"
    assert dtcs_type_for_logical_type("datetime") == "datetime"
    assert dtcs_type_for_logical_type("timestamp") == "datetime"
    with pytest.raises(ValueError, match="array"):
        dtcs_type_for_logical_type("array", field_name="tags")


def test_parameterized_transform_round_trips(tmp_path: Path) -> None:
    class Normalize(Transformation):
        customers: Input[RawCustomer]
        minimum_age: Parameter[int] = 18
        result: Output[Customer]

    class Pipe(Pipeline):
        raw: Extract[RawCustomer] = Extract(asset="src")
        normalized = Normalize.step(customers=raw, minimum_age=21)
        curated: Load[Customer] = Load(input=normalized.result, asset="sink")

    write_contracts(Pipe, tmp_path)
    loaded = load_bundle(tmp_path)
    assert loaded.pipeline is not None
    assert graphs_equivalent(Pipe.inspect(), loaded.pipeline.inspect())
    step = loaded.pipeline.__pipeline_members__["normalized"]
    assert step.parameters["minimum_age"] == 21


def test_float_datetime_contracts_export(tmp_path: Path) -> None:
    class PassThrough(Transformation):
        events: Input[Event]
        result: Output[Event]

    class Pipe(Pipeline):
        raw: Extract[Event] = Extract(asset="src")
        passed = PassThrough.step(events=raw)
        out: Load[Event] = Load(input=passed.result, asset="sink")

    write_contracts(Pipe, tmp_path)
    assert any((tmp_path / "data").glob("*.odcs.yaml"))


def test_published_id_compatibility_across_odcs_load(tmp_path: Path) -> None:
    write_odcs(RawCustomer, tmp_path / "raw.odcs.yaml")
    write_odcs(Customer, tmp_path / "customer.odcs.yaml")
    loaded_raw = load_data_contract(tmp_path / "raw.odcs.yaml")
    loaded_customer = load_data_contract(tmp_path / "customer.odcs.yaml")

    class Norm(Transformation):
        customers: Input[RawCustomer]
        result: Output[Customer]

    loaded_norm = transformation_from_dtcs(
        Norm.to_dtcs(),
        contracts={
            "rawcustomer": loaded_raw,
            "customer": loaded_customer,
        },
    )

    class Pipe(Pipeline):
        raw: Extract[RawCustomer] = Extract(asset="src")
        normalized = loaded_norm.step(customers=raw)
        curated: Load[Customer] = Load(input=normalized.result, asset="sink")

    report = Pipe.validate()
    assert report.valid, report.codes()


def test_nested_subpipeline_validation_runs() -> None:
    class BadChild(Pipeline):
        raw: Extract[RawCustomer] = Extract(asset="raw")
        curated: Load[Customer] = Load(input=raw, asset="curated")

    class Parent(Pipeline):
        src: Extract[RawCustomer] = Extract(asset="src")
        child = BadChild.subpipeline(raw=src)
        out: Load[Customer] = Load(input=child.curated, asset="out")

    report = Parent.validate()
    assert not report.valid
    assert "PMPIPE210" in report.codes()


def test_stale_graph_build_error_cleared() -> None:
    class Looper(Pipeline):
        raw: Extract[RawCustomer] = Extract(asset="raw")
        out: Load[RawCustomer] = Load(input=raw, asset="out")

    Looper._graph_build_error = "stale cyclic error"  # type: ignore[attr-defined]
    Looper._cached_graph = None  # type: ignore[attr-defined]
    graph = Looper.build_graph()
    assert Looper._graph_build_error is None  # type: ignore[attr-defined]
    assert graph.nodes
    assert Looper.validate().valid


def test_bundle_rejects_published_id_collision(tmp_path: Path) -> None:
    CustomerA.__published_id__ = "customer"  # type: ignore[attr-defined]
    CustomerB.__published_id__ = "customer"  # type: ignore[attr-defined]
    try:

        class Left(Transformation):
            customers: Input[CustomerA]
            result: Output[CustomerA]

        class Right(Transformation):
            customers: Input[CustomerB]
            result: Output[CustomerB]

        class Pipe(Pipeline):
            a: Extract[CustomerA] = Extract(asset="a")
            b: Extract[CustomerB] = Extract(asset="b")
            left = Left.step(customers=a)
            right = Right.step(customers=b)
            out_a: Load[CustomerA] = Load(input=left.result, asset="out_a")
            out_b: Load[CustomerB] = Load(input=right.result, asset="out_b")

        with pytest.raises(BundleError) as exc:
            write_contracts(Pipe, tmp_path / "bundle")
        assert "PMGEN232" in exc.value.report.codes()
    finally:
        for model in (CustomerA, CustomerB):
            if hasattr(model, "__published_id__"):
                delattr(model, "__published_id__")


def test_from_dtcs_accepts_odcs_prefixed_registry_keys() -> None:
    class Norm(Transformation):
        customers: Input[RawCustomer]
        result: Output[Customer]

    doc = Norm.to_dtcs()
    loaded = transformation_from_dtcs(
        doc,
        contracts={
            "odcs:rawcustomer": RawCustomer,
            "odcs:customer": Customer,
        },
    )
    assert loaded.inputs()[0].contract_type is RawCustomer


def test_diff_pipelines_fails_closed_on_incompatible_category(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import etlantic.interchange.diff as diff_mod

    monkeypatch.setattr(
        diff_mod.dpcs,
        "compare_contract_yaml",
        lambda *_a, **_k: {"category": "incompatible", "diagnostics": []},
    )
    report = diff_pipelines({"a": 1}, {"b": 2})
    assert not report.valid
    assert "PMGEN311" in report.codes()


def test_diff_transformations_rejects_invalid_dtcs(tmp_path: Path) -> None:
    bad = tmp_path / "bad.dtcs.yaml"
    bad.write_text("not: valid: dtcs\n", encoding="utf-8")
    report = diff_transformations(bad, bad)
    assert report.has_errors
    assert any(d.code == "PMGEN203" for d in report.errors)
