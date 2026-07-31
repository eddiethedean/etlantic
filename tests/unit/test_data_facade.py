"""0.3 authoring surface: Data facade and compatibility."""

from __future__ import annotations

import pytest
from contractmodel import ContractModel

import etlantic
from etlantic import Data, Extract, Input, Load, Output, Pipeline, Transformation


class Customer(Data):
    id: int
    name: str


class Normalize(Transformation):
    customers: Input[Customer]
    result: Output[Customer]


class CustomerPipeline(Pipeline):
    raw: Extract[Customer] = Extract(asset="customers")
    normalized = Normalize.step(customers=raw)
    out: Load[Customer] = Load(input=normalized.result, asset="curated")


def test_data_is_contract_model() -> None:
    assert Data is ContractModel


def test_datacontractmodel_removed() -> None:
    with pytest.raises(
        AttributeError, match=r"removed from the etlantic root in 0\.37\.0"
    ):
        getattr(etlantic, "DataContractModel")


def test_author_with_data() -> None:
    report = CustomerPipeline.validate()
    assert report.valid
    assert "structural" in report.phases
