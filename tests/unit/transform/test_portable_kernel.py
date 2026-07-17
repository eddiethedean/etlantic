"""Kernel portable authoring tests (0.11 W1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from etlantic import Data, Input, Output, Parameter, Transformation
from etlantic.exceptions import ModelDefinitionError
from etlantic.transform import PLAN_PROTOCOL
from etlantic.transform import functions as F
from etlantic.transform.protocol import MISSING

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "portable"


class RawCustomer(Data):
    customer_id: int
    email: str
    age: int


class Customer(Data):
    customer_id: int
    email: str
    age: int


class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    minimum_age: Parameter[int]
    result: Output[Customer]


@NormalizeCustomers.portable
def _normalize(customers, minimum_age):
    return (
        customers.filter(F.col("age") >= minimum_age)
        .withColumn("email", F.lower(F.col("email")))
        .select("customer_id", "email", "age")
    )


def test_portable_emits_plan_v2_and_stable_fingerprint() -> None:
    plan = NormalizeCustomers.to_transform_plan()
    assert plan["planIdentity"] == PLAN_PROTOCOL
    fp1 = NormalizeCustomers.portable_fingerprint()
    fp2 = NormalizeCustomers.portable_fingerprint()
    assert fp1 == fp2
    assert len(fp1) == 64


def test_kernel_requirements_and_actions() -> None:
    defn = NormalizeCustomers.portable_definition()
    assert defn is not None
    assert "dtcs:filter" in defn.requirements["actions"]
    assert "dtcs:lower" in defn.requirements["functions"]
    assert "dtcs:profile/portable-relational-kernel/2" in defn.requirements["profiles"]


def test_golden_kernel_fingerprint_file(tmp_path: Path) -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    plan = NormalizeCustomers.to_transform_plan()
    # Drop non-semantic volatile keys for fixture comparison of action ids shape
    payload = {
        "planIdentity": plan["planIdentity"],
        "profile": plan["profile"],
        "actions": [a["kind"]["action"] for a in plan["actions"]],
        "fingerprint": NormalizeCustomers.portable_fingerprint(),
    }
    path = FIXTURES / "kernel_normalize.json"
    if not path.exists():
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    expected = json.loads(path.read_text(encoding="utf-8"))
    assert payload["planIdentity"] == expected["planIdentity"]
    assert payload["actions"] == expected["actions"]
    assert payload["fingerprint"] == expected["fingerprint"]


def test_boolean_python_rejected() -> None:
    class T(Transformation):
        customers: Input[RawCustomer]
        result: Output[Customer]

    with pytest.raises(ModelDefinitionError):

        @T.portable
        def bad(customers):
            if F.col("age") > 18:
                return customers
            return customers


def test_expr_sql_rejected() -> None:
    with pytest.raises(ModelDefinitionError):
        F.expr("age + 1")


def test_missing_output_rejected() -> None:
    class T(Transformation):
        customers: Input[RawCustomer]
        result: Output[Customer]
        other: Output[Customer]

    with pytest.raises(ModelDefinitionError):

        @T.portable
        def bad(customers):
            return {"result": customers.select("customer_id")}


def test_missing_literal_round_trips() -> None:
    class T(Transformation):
        customers: Input[RawCustomer]
        result: Output[Customer]

    @T.portable
    def define(customers):
        return customers.withColumn("flag", F.lit(MISSING)).select(
            "customer_id", "flag"
        )

    plan = T.to_transform_plan()
    assert plan["planIdentity"] == PLAN_PROTOCOL
