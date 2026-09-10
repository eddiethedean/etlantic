"""Transformations for the sample project."""

from etlantic import Input, Output, Transformation
from etlantic.transform import functions as F

from .contracts import Customer, RawCustomer


class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    result: Output[Customer]


@NormalizeCustomers.portable
def normalize_customers(customers):
    return customers.select(
        "customer_id",
        F.concat_ws(" ", F.col("first_name"), F.col("last_name")).alias("full_name"),
    )
