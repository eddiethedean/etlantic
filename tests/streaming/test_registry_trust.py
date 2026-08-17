"""Schema-registry allowlist and in-memory protocol."""

from __future__ import annotations

import pytest

from etlantic.profile import Profile
from etlantic.streaming.registry import (
    InMemorySchemaRegistry,
    SchemaFormat,
    schema_fingerprint,
)
from etlantic.streaming.trust import registry_adapter_allowed


def test_production_empty_registry_allowlist_fails_closed() -> None:
    profile = Profile(name="production", security_mode="production")
    ok, diag = registry_adapter_allowed(profile, "etlantic-schemaregistry")
    assert ok is False
    assert diag is not None
    assert diag.code == "PMREG140"  # type: ignore[union-attr]


def test_in_memory_registry_identity() -> None:
    registry = InMemorySchemaRegistry()
    fp = schema_fingerprint('{"type":"record"}', format=SchemaFormat.JSON_SCHEMA)
    ident = registry.register("orders", fp, format=SchemaFormat.JSON_SCHEMA)
    assert ident.version == 1
    assert registry.lookup("orders").fingerprint == fp
    registry.set_outage(True)
    with pytest.raises(LookupError):
        registry.lookup("orders")
