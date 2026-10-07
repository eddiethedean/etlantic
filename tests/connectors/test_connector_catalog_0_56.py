"""Managed connector catalog schema and secret redaction contracts."""

from __future__ import annotations

import json
from dataclasses import replace
from importlib.metadata import EntryPoint
from typing import Any

import pytest

from etlantic.connectors import catalog as connector_catalog
from etlantic.connectors.discovery import SOURCE_CONNECTORS_GROUP
from etlantic.connectors.models import ConnectorInfo
from etlantic.plugin_lifecycle import DiscoveredPlugin, PluginLifecycleResult
from etlantic.profile import Profile


class _SchemaProvider:
    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name="test-secret-source",
            protocol="etlantic.source/1",
            provider="test-secret-source",
            capabilities=("source.batch_snapshot",),
            configuration_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "endpoint": {"type": "string", "default": "https://example.test"},
                    "api_token": {
                        "type": "string",
                        "default": "never-publish-this",
                        "examples": ["never-publish-this-example"],
                    },
                    "accessToken": {
                        "type": "string",
                        "default": "camel-case-token",
                    },
                    "private_key": {
                        "type": "string",
                        "examples": ["private-key-example"],
                        "enum": ["private-key-enum"],
                    },
                    "connection": {
                        "type": "object",
                        "default": {
                            "region": "us-east-1",
                            "clientSecret": "nested-secret-value",
                        },
                    },
                    "opaque": {
                        "type": "string",
                        "writeOnly": True,
                        "default": "write-only-default",
                    },
                },
            },
        )


def _catalog_document(monkeypatch: Any, provider: _SchemaProvider) -> dict[str, Any]:
    plugin = DiscoveredPlugin(
        group=SOURCE_CONNECTORS_GROUP,
        name="test-secret-source",
        target="test_package:source",
        distribution_name="test-package",
        distribution_version="2.4.1",
        entry_point=EntryPoint(
            name="test-secret-source",
            value="test_package:source",
            group=SOURCE_CONNECTORS_GROUP,
        ),
    )

    def discover(_profile: Profile, *, run_id: str) -> dict[str, PluginLifecycleResult]:
        assert run_id == "connector-catalog"
        return {
            SOURCE_CONNECTORS_GROUP: PluginLifecycleResult(
                authorized=[plugin],
                loaded={"test-secret-source": provider},
            )
        }

    monkeypatch.setattr(connector_catalog, "discover_connectors_for_profile", discover)

    return connector_catalog.connector_catalog_for_profile(Profile(name="development"))


def test_connector_catalog_publishes_typed_schema_without_secret_defaults(
    monkeypatch: Any,
) -> None:
    document = _catalog_document(monkeypatch, _SchemaProvider())
    provider = next(
        item for item in document["connectors"] if item["name"] == "test-secret-source"
    )
    schema = provider["configuration_schema"]

    assert provider["schema_available"] is True
    assert provider["protocol"] == "etlantic.source/1"
    assert provider["package"] == "test-package"
    assert provider["package_version"] == "2.4.1"
    assert schema["properties"]["endpoint"]["default"] == "https://example.test"
    assert schema["properties"]["api_token"]["x-sensitive"] is True
    assert "default" not in schema["properties"]["api_token"]
    assert schema["properties"]["accessToken"]["x-sensitive"] is True
    assert "default" not in schema["properties"]["accessToken"]
    assert schema["properties"]["private_key"]["x-sensitive"] is True
    assert "examples" not in schema["properties"]["private_key"]
    assert "enum" not in schema["properties"]["private_key"]
    assert schema["properties"]["connection"]["default"] == {"region": "us-east-1"}
    assert "default" not in schema["properties"]["opaque"]
    assert "never-publish-this" not in json.dumps(document, sort_keys=True)
    assert "never-publish-this-example" not in json.dumps(document, sort_keys=True)
    assert "camel-case-token" not in json.dumps(document, sort_keys=True)
    assert "private-key-example" not in json.dumps(document, sort_keys=True)
    assert "private-key-enum" not in json.dumps(document, sort_keys=True)
    assert "nested-secret-value" not in json.dumps(document, sort_keys=True)
    assert "write-only-default" not in json.dumps(document, sort_keys=True)


@pytest.mark.parametrize("marker", ["writeOnly", "x-sensitive", "sensitive", "name"])
@pytest.mark.parametrize("wrapper", ["properties", "allOf", "anyOf", "oneOf", "items"])
def test_connector_catalog_redacts_inherited_sensitivity(
    monkeypatch: Any, marker: str, wrapper: str
) -> None:
    child = {
        "type": "object",
        "properties": {
            "value": {
                "type": "string",
                "default": "synthetic-private-default",
                "examples": ["synthetic-private-example"],
                "enum": ["synthetic-private-enum"],
                "const": "synthetic-private-const",
            }
        },
    }
    sensitive_object: dict[str, Any] = (
        child
        if wrapper == "properties"
        else {wrapper: child if wrapper == "items" else [child]}
    )
    if marker != "name":
        sensitive_object[marker] = True
    field_name = "credentials" if marker == "name" else "opaque"
    schema = {
        "type": "object",
        "properties": {
            field_name: sensitive_object,
            "region": {"type": "string", "default": "us-east-1"},
        },
    }

    class NestedSchemaProvider(_SchemaProvider):
        def info(self) -> ConnectorInfo:
            return replace(super().info(), configuration_schema=schema)

    document = _catalog_document(monkeypatch, NestedSchemaProvider())
    provider = next(
        item for item in document["connectors"] if item["name"] == "test-secret-source"
    )
    public_schema = provider["configuration_schema"]
    assert public_schema["properties"]["region"]["default"] == "us-east-1"
    assert "synthetic-private" not in json.dumps(document)
    # Sanitizing a catalog must not mutate the provider's schema.
    assert "synthetic-private-default" in json.dumps(schema)


@pytest.mark.parametrize(
    ("schema", "sample_key"),
    [
        (
            {
                "type": "object",
                "properties": {"opaque": {"type": "string", "writeOnly": True}},
                "default": {"opaque": "synthetic-private-value", "region": "us-east-1"},
            },
            "default",
        ),
        (
            {
                "type": "object",
                "properties": {"opaque": {"type": "string", "x-sensitive": True}},
                "examples": [{"opaque": "synthetic-private-value"}],
            },
            "examples",
        ),
        (
            {
                "type": "array",
                "items": {"type": "string", "writeOnly": True},
                "examples": [["synthetic-private-value"]],
            },
            "examples",
        ),
        (
            {
                "type": "array",
                "contains": {"type": "string", "writeOnly": True},
                "default": ["synthetic-private-value"],
            },
            "default",
        ),
        (
            {
                "type": "object",
                "properties": {"region": {"type": "string"}},
                "additionalProperties": {"type": "string", "writeOnly": True},
                "default": {
                    "opaque": "synthetic-private-value",
                    "region": "us-east-1",
                },
            },
            "default",
        ),
        (
            {
                "type": "array",
                "prefixItems": [{"type": "string", "writeOnly": True}],
                "examples": [["synthetic-private-value"]],
            },
            "examples",
        ),
        (
            {
                "$defs": {
                    "Private": {
                        "$dynamicAnchor": "private",
                        "type": "string",
                        "writeOnly": True,
                    }
                },
                "type": "object",
                "properties": {
                    "opaque": {
                        "$dynamicRef": "#private",
                        "default": "synthetic-private-value",
                    }
                },
            },
            "default",
        ),
        (
            {
                "type": "object",
                "properties": {"region": {"type": "string"}},
                "if": {"properties": {"mode": {"const": "private"}}},
                "then": {
                    "properties": {"opaque": {"type": "string", "writeOnly": True}}
                },
                "default": {
                    "mode": "private",
                    "opaque": "synthetic-private-value",
                    "region": "us-east-1",
                },
            },
            "default",
        ),
        (
            {
                "type": "object",
                "properties": {"region": {"type": "string"}},
                "unevaluatedProperties": {"type": "string", "writeOnly": True},
                "default": {
                    "opaque": "synthetic-private-value",
                    "region": "us-east-1",
                },
            },
            "default",
        ),
        (
            {
                "type": "array",
                "unevaluatedItems": {"type": "string", "writeOnly": True},
                "examples": [["synthetic-private-value"]],
            },
            "examples",
        ),
        (
            {
                "type": "object",
                "$defs": {"Private": {"type": "string", "writeOnly": True}},
                "properties": {
                    "opaque": {
                        "$ref": "#/$defs/Private",
                        "default": "synthetic-private-value",
                    }
                },
            },
            "default",
        ),
    ],
)
def test_connector_catalog_sanitizes_samples_with_schema_context(
    monkeypatch: Any, schema: dict[str, Any], sample_key: str
) -> None:
    source_schema = json.loads(json.dumps(schema))

    class ContextSchemaProvider(_SchemaProvider):
        def info(self) -> ConnectorInfo:
            return replace(super().info(), configuration_schema=source_schema)

    document = _catalog_document(monkeypatch, ContextSchemaProvider())
    public_schema = next(
        item["configuration_schema"]
        for item in document["connectors"]
        if item["name"] == "test-secret-source"
    )

    assert "synthetic-private-value" not in json.dumps(public_schema)
    if (
        sample_key == "default"
        and schema.get("type") == "object"
        and isinstance(schema.get("default"), dict)
    ):
        assert public_schema["default"]["region"] == "us-east-1"
    assert source_schema == schema


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "object", "default": {"region": "us-east-1"}},
        {
            "type": "object",
            "properties": {"opaque": {"type": "string", "default": "safe"}},
            "default": {"opaque": "safe"},
        },
    ],
)
def test_connector_catalog_preserves_safe_schema_samples(
    monkeypatch: Any, schema: dict[str, Any]
) -> None:
    class SafeSchemaProvider(_SchemaProvider):
        def info(self) -> ConnectorInfo:
            return replace(super().info(), configuration_schema=schema)

    document = _catalog_document(monkeypatch, SafeSchemaProvider())
    public_schema = next(
        item["configuration_schema"]
        for item in document["connectors"]
        if item["name"] == "test-secret-source"
    )
    assert public_schema["default"] == schema["default"]


@pytest.mark.parametrize(
    "sample_key", ["default", "example", "examples", "const", "enum"]
)
@pytest.mark.parametrize(
    "sensitive_schema",
    [
        {"type": "string", "writeOnly": True},
        {"type": "string", "x-sensitive": True},
        {"type": "string", "sensitive": True},
        {"allOf": [{"$ref": "#/$defs/Private"}]},
    ],
)
def test_connector_catalog_redacts_each_parent_sample_keyword(
    monkeypatch: Any, sample_key: str, sensitive_schema: dict[str, Any]
) -> None:
    sample: Any = "synthetic-private-sample"
    if sample_key in {"examples", "enum"}:
        sample = [sample]
    schema: dict[str, Any] = {
        "$defs": {"Private": {"type": "string", "writeOnly": True}},
        "type": "object",
        "properties": {"opaque": sensitive_schema},
        sample_key: (
            {"opaque": sample}
            if sample_key not in {"examples", "enum"}
            else [{"opaque": sample[0]}]
        ),
    }

    class ParentSampleProvider(_SchemaProvider):
        def info(self) -> ConnectorInfo:
            return replace(super().info(), configuration_schema=schema)

    document = _catalog_document(monkeypatch, ParentSampleProvider())
    public_schema = next(
        item["configuration_schema"]
        for item in document["connectors"]
        if item["name"] == "test-secret-source"
    )
    assert "synthetic-private-sample" not in json.dumps(public_schema)


@pytest.mark.parametrize(
    "reference",
    ["#/$defs/Missing", "#/$defs/Loop", 7, None],
)
def test_connector_catalog_fails_closed_for_unresolved_or_cyclic_refs(
    monkeypatch: Any, reference: Any
) -> None:
    schema = {
        "$defs": {"Loop": {"$ref": "#/$defs/Loop"}},
        "type": "object",
        "properties": {
            "opaque": {
                "$ref": reference,
                "default": "synthetic-private-unverified-value",
            }
        },
    }

    class InvalidReferenceProvider(_SchemaProvider):
        def info(self) -> ConnectorInfo:
            return replace(super().info(), configuration_schema=schema)

    document = _catalog_document(monkeypatch, InvalidReferenceProvider())
    public_schema = next(
        item["configuration_schema"]
        for item in document["connectors"]
        if item["name"] == "test-secret-source"
    )
    assert "synthetic-private-unverified-value" not in json.dumps(public_schema)
