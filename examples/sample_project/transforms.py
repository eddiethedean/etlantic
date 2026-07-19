"""Transformations for the sample project."""

from etlantic import Input, Output, Transformation

from .contracts import Customer, RawCustomer


class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    result: Output[Customer]


@NormalizeCustomers.implementation("local")
def normalize_customers(customers: list[RawCustomer]) -> list[Customer]:
    return [
        Customer(
            customer_id=customer.customer_id,
            full_name=f"{customer.first_name} {customer.last_name}",
        )
        for customer in customers
    ]
