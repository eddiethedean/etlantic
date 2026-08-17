"""Fake-only schema-registry adapter tests (no Confluent HTTP)."""

from __future__ import annotations

import os

import pytest
from etlantic_schemaregistry import (
    FakeConfluentRegistry,
    create_registry,
    live_registry_url,
)

from etlantic.streaming.registry import SchemaFormat, schema_fingerprint

pytestmark = pytest.mark.schemaregistry


def test_factory_registers_identity_only() -> None:
    registry = create_registry()
    assert isinstance(registry, FakeConfluentRegistry)
    fp = schema_fingerprint('{"type":"string"}', format=SchemaFormat.JSON_SCHEMA)
    identity = registry.register("orders-value", fp, format=SchemaFormat.JSON_SCHEMA)
    assert identity.subject == "orders-value"
    assert identity.fingerprint == fp
    assert registry.subjects() == ["orders-value"]
    assert registry.get_versions("orders-value") == [1]
    assert registry.get_config("orders-value")["compatibility"] == "backward"
    assert registry.check_compatibility("orders-value", fp) is True


def test_outage_fails_closed() -> None:
    registry = FakeConfluentRegistry()
    registry.set_outage(True)
    with pytest.raises(LookupError):
        registry.lookup("missing")


def test_live_registry_skipped_unless_env() -> None:
    if live_registry_url():
        pytest.skip("live Confluent opt-in is Experimental and not part of default CI")
    assert os.environ.get("ETLANTIC_SCHEMA_REGISTRY_URL") in (None, "")
