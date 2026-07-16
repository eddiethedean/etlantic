"""Unit tests for portable SQL IR and discovery (no database required)."""

from __future__ import annotations

from pipelantic.profile import Profile
from pipelantic.registry import PlanningContext
from pipelantic.sql import (
    SQL_PROTOCOL_VERSION,
    RelationRef,
    col,
    concat,
    select,
)
from pipelantic.sql.helpers import is_safe_identifier, require_safe_identifier


def test_relation_ref_parse() -> None:
    assert RelationRef.parse("customers").name == "customers"
    assert RelationRef.parse("public.customers").namespace == "public"
    assert RelationRef.parse("db.public.customers").catalog == "db"


def test_identifier_policy() -> None:
    assert is_safe_identifier("customer_id")
    assert not is_safe_identifier("customer;drop")
    try:
        require_safe_identifier("bad-name")
        raise AssertionError
    except ValueError:
        pass


def test_select_builder() -> None:
    q = select(
        col("customer_id"),
        concat(col("first_name"), col("last_name"), as_="full_name"),
        source="public.customers",
    )
    assert q.source.namespace == "public"
    assert q.to_dict()["kind"] == "select"
    assert SQL_PROTOCOL_VERSION.startswith("pipelantic.sql/")


def test_planning_context_requests_sql_capabilities() -> None:
    ctx = PlanningContext.create(Profile(name="sql-dev", sql_engine="sql"))
    assert "sql" in ctx.required_capabilities
    assert ctx.profile.sql_engine == "sql"
