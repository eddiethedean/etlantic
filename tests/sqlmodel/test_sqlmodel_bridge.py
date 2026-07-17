"""SQLModel integration tests."""

from __future__ import annotations

import pytest
from contractmodel import ContractModel

pytest.importorskip("sqlmodel")

from etlantic_sqlmodel import (
    compare_metadata,
    contract_to_sqlmodel,
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
    assert table.__tablename__ == "customer"
    metadata = sqlmodel_to_contract(table)
    assert metadata["table_name"] == "customer"
    assert {f["name"] for f in metadata["fields"]} == {"customer_id", "name"}

    report = compare_metadata(Customer, table)
    assert report.valid


def test_run_conformance_checks() -> None:
    report = run_conformance_checks(
        Customer,
        table_name="customer",
        primary_key=("customer_id",),
    )
    assert report.valid
