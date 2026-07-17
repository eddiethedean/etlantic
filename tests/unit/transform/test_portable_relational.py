"""Relational portable authoring tests (0.11 W2)."""

from __future__ import annotations

from etlantic import Data, Input, Output, Transformation
from etlantic.transform import functions as F


class Orders(Data):
    order_id: int
    customer_id: int
    amount: float


class Customers(Data):
    customer_id: int
    region: str


class Joined(Data):
    order_id: int
    customer_id: int
    region: str


class AggOut(Data):
    region: str
    total: float


class JoinOrders(Transformation):
    orders: Input[Orders]
    customers: Input[Customers]
    result: Output[Joined]


@JoinOrders.portable
def _join(orders, customers):
    return orders.join(customers, on="customer_id", how="inner").select(
        "order_id", "customer_id", "region"
    )


class AggregateOrders(Transformation):
    orders: Input[Orders]
    customers: Input[Customers]
    result: Output[AggOut]


@AggregateOrders.portable
def _agg(orders, customers):
    joined = orders.join(customers, on="customer_id", how="left")
    return joined.groupBy("region").agg(total=F.sum(F.col("amount")).alias("total"))


def test_join_emits_relational_profile() -> None:
    defn = JoinOrders.portable_definition()
    assert defn is not None
    assert "dtcs:join" in defn.requirements["actions"]
    assert "dtcs:profile/portable-relational/1" in defn.requirements["profiles"]
    assert JoinOrders.to_transform_plan()["planIdentity"] == "dtcs.transform-plan/2"


def test_aggregate_and_union() -> None:
    defn = AggregateOrders.portable_definition()
    assert defn is not None
    assert "dtcs:aggregate" in defn.requirements["actions"]
    assert AggregateOrders.portable_fingerprint()

    class U(Transformation):
        a: Input[Orders]
        b: Input[Orders]
        result: Output[Orders]

    @U.portable
    def uni(a, b):
        return a.unionByName(b).dropDuplicates("order_id").limit(10)

    assert "dtcs:union" in U.portable_definition().requirements["actions"]
    assert "dtcs:deduplicate" in U.portable_definition().requirements["actions"]
