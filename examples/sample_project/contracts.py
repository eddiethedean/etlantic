"""Data contracts for the sample project."""

from etlantic import Data


class RawCustomer(Data):
    customer_id: int
    first_name: str
    last_name: str


class Customer(Data):
    customer_id: int
    full_name: str
