"""Pipeline wiring for the sample project."""

from etlantic import Extract, Load, Pipeline

from .contracts import Customer, RawCustomer
from .transforms import NormalizeCustomers


class CustomerPipeline(Pipeline):
    raw: Extract[RawCustomer] = Extract(asset="customer_source")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Load[Customer] = Load(
        input=normalized.result,
        asset="customer_sink",
    )
