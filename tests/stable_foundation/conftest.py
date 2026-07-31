"""Shared fixtures for the stable-foundation acceptance suite."""

from __future__ import annotations

import pytest
from examples.memory_customers import Customer, CustomerPipeline, RawCustomer


@pytest.fixture
def customer_pipeline():
    """Canonical in-memory customer pipeline used across several SF items."""
    return CustomerPipeline


@pytest.fixture
def customer_seed() -> dict:
    return {
        "customer_source": (
            RawCustomer(customer_id=1, first_name="Ada", last_name="Lovelace"),
            RawCustomer(customer_id=2, first_name="Grace", last_name="Hopper"),
        )
    }


@pytest.fixture
def customer_types() -> tuple[type, type]:
    return RawCustomer, Customer
