# pyright: reportAssignmentType=false, reportMissingParameterType=false, reportUnknownParameterType=false, reportUnknownVariableType=false
"""Unit tests for transformation ports and implementations."""

from etlantic import Input, Output, Parameter, Transformation
from tests.conftest import Customer, RawCustomer


class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    minimum_age: Parameter[int] = 18
    result: Output[Customer]


def test_collects_inputs_outputs_parameters() -> None:
    assert [p.name for p in NormalizeCustomers.inputs()] == ["customers"]
    assert [p.name for p in NormalizeCustomers.outputs()] == ["result"]
    params = NormalizeCustomers.parameters()
    assert len(params) == 1
    assert params[0].name == "minimum_age"
    assert params[0].has_default
    assert params[0].default == 18


def test_implementation_registration() -> None:
    @NormalizeCustomers.implementation("polars")
    def normalize(customers, minimum_age):
        return customers

    impls = NormalizeCustomers.implementations()
    assert "polars" in impls
    assert impls["polars"].identity.endswith("/polars")
    assert impls["polars"].callable is normalize
    assert impls["polars"].is_async is False


def test_step_creates_output_refs() -> None:
    step = NormalizeCustomers.step(customers="placeholder")
    assert step.result.port_name == "result"
    assert step.result.contract_type is Customer
    assert step.producer_key.startswith("step-")


def test_multiple_outputs() -> None:
    class Split(Transformation):
        customers: Input[RawCustomer]
        valid: Output[Customer]
        rejected: Output[Customer]

    step = Split.step(customers="x")
    assert set(step.output_refs) == {"valid", "rejected"}
