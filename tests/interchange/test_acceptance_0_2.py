"""Acceptance tests for 0.2 contract interoperability."""

from __future__ import annotations

from pathlib import Path

import pytest
from contractmodel import DataContract
from tests.conftest import Customer, RawCustomer

from pipelantic import (
    Input,
    Output,
    Pipeline,
    Sink,
    Source,
    Transformation,
    diff_data_contracts,
    graphs_equivalent,
    load_bundle,
    load_data_contract,
    write_contracts,
    write_odcs,
)
from pipelantic.interchange.dtcs import DtcsError, transformation_from_dtcs
from pipelantic.interchange.policy import check_dtcs_version, check_odcs_version
from pipelantic.interchange.security import UnsafeLoadError, read_text_bounded


class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    result: Output[Customer]


class CustomerPipeline(Pipeline):
    raw: Source[RawCustomer] = Source(binding="customer_source")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Sink[Customer] = Sink(input=normalized.result, binding="customer_sink")


def test_code_first_generate_is_byte_stable(tmp_path: Path) -> None:
    first = write_contracts(CustomerPipeline, tmp_path / "a")
    second = write_contracts(CustomerPipeline, tmp_path / "b")
    assert first.documents.keys() == second.documents.keys()
    for key in first.documents:
        assert first.documents[key] == second.documents[key]
    left_files = {
        p.relative_to(tmp_path / "a"): p.read_bytes()
        for p in (tmp_path / "a").rglob("*.yaml")
    }
    right_files = {
        p.relative_to(tmp_path / "b"): p.read_bytes()
        for p in (tmp_path / "b").rglob("*.yaml")
    }
    assert left_files == right_files


def test_round_trip_reconstructs_equivalent_graph(tmp_path: Path) -> None:
    write_contracts(CustomerPipeline, tmp_path)
    loaded = load_bundle(tmp_path)
    assert loaded.pipeline is not None
    assert graphs_equivalent(CustomerPipeline.inspect(), loaded.pipeline.inspect())
    assert loaded.pipeline.validate().valid


def test_contractmodel_odcs_workflow_unchanged(tmp_path: Path) -> None:
    path = tmp_path / "customer.odcs.yaml"
    DataContract.from_pydantic(Customer).save(path, format="odcs")
    restored = DataContract.from_odcs(path).to_pydantic()
    assert set(restored.model_fields) == set(Customer.model_fields)


def test_pipelantic_odcs_facades(tmp_path: Path) -> None:
    path = tmp_path / "raw.odcs.yaml"
    write_odcs(RawCustomer, path)
    loaded = load_data_contract(path)
    assert getattr(loaded, "__published_id__", None) == "rawcustomer"
    assert set(loaded.model_fields) == set(RawCustomer.model_fields)


def test_unknown_dtcs_version_fails_closed() -> None:
    report = check_dtcs_version("9.9.9")
    assert not report.valid
    assert "PMGEN202" in report.codes()


def test_unknown_odcs_version_fails_closed() -> None:
    report = check_odcs_version("v1.0.0")
    assert not report.valid
    assert "PMDATA202" in report.codes()


def test_unresolved_dtcs_contract_ref_fails() -> None:
    doc = NormalizeCustomers.to_dtcs()
    with pytest.raises(DtcsError) as exc:
        transformation_from_dtcs(doc, contracts={})
    assert "PMGEN205" in exc.value.report.codes()


def test_path_escape_rejected(tmp_path: Path) -> None:
    outside = tmp_path / "outside.yaml"
    outside.write_text("apiVersion: v3.0.0\n", encoding="utf-8")
    root = tmp_path / "bundle"
    root.mkdir()
    with pytest.raises(UnsafeLoadError) as exc:
        read_text_bounded(outside, root=root)
    assert "PMSRC101" in exc.value.report.codes()


def test_oversized_file_rejected(tmp_path: Path) -> None:
    path = tmp_path / "big.yaml"
    path.write_bytes(b"x" * 100)
    with pytest.raises(UnsafeLoadError) as exc:
        read_text_bounded(path, max_bytes=10)
    assert "PMSRC103" in exc.value.report.codes()


def test_load_paths_do_not_use_pickle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import pickle

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("pickle.load must not be called")

    monkeypatch.setattr(pickle, "load", _boom)
    monkeypatch.setattr(pickle, "loads", _boom)
    write_contracts(CustomerPipeline, tmp_path)
    load_bundle(tmp_path)


def test_diff_data_contracts_breaking() -> None:
    from contractmodel import ContractModel

    class Wide(ContractModel):
        customer_id: int
        email: str

    class Narrow(ContractModel):
        customer_id: int

    report = diff_data_contracts(Wide, Narrow)
    assert not report.valid
    assert any(code.startswith("PMDATA301") for code in report.codes())
