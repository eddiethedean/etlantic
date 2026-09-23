"""SQLModel integration tests."""

from __future__ import annotations

import pytest
from contractmodel import ContractModel

pytest.importorskip("sqlmodel")

from etlantic_sqlmodel import (
    compare_metadata,
    contract_to_sqlmodel,
    contract_to_sqlmodel_source,
    run_conformance_checks,
    sqlmodel_to_contract,
)

pytestmark = pytest.mark.sqlmodel


class Customer(ContractModel):
    customer_id: int
    name: str


def test_contract_to_sqlmodel_round_trip() -> None:
    table = contract_to_sqlmodel(
        Customer,
        table_name="customer",
        primary_key=("customer_id",),
    )
    assert getattr(table, "__tablename__", None) == "customer"
    metadata = sqlmodel_to_contract(table)
    assert metadata["table_name"] == "customer"
    assert {f["name"] for f in metadata["fields"]} == {"customer_id", "name"}

    report = compare_metadata(Customer, table)
    assert report.valid


def test_contract_to_sqlmodel_source_emits_class() -> None:
    source = contract_to_sqlmodel_source(
        Customer,
        table_name="customer",
        primary_key=("customer_id",),
    )
    assert "class CustomerTable(SQLModel, table=True):" in source
    assert '__tablename__ = "customer"' in source
    assert "customer_id: int = Field(primary_key=True)" in source
    assert "name: str" in source
    assert "from sqlmodel import Field, SQLModel" in source


def test_run_conformance_checks() -> None:
    report = run_conformance_checks(
        Customer,
        table_name="customer",
        primary_key=("customer_id",),
    )
    assert report.valid
