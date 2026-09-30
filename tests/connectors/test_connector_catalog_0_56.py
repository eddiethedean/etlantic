"""Managed connector catalog schema and secret redaction contracts."""

from __future__ import annotations

import json
from importlib.metadata import EntryPoint
from typing import Any

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


def test_connector_catalog_publishes_typed_schema_without_secret_defaults(
    monkeypatch: Any,
) -> None:
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
                loaded={"test-secret-source": _SchemaProvider()},
            )
        }

    monkeypatch.setattr(connector_catalog, "discover_connectors_for_profile", discover)

    document = connector_catalog.connector_catalog_for_profile(
        Profile(name="development")
    )
    provider = next(
        item
        for item in document["connectors"]
        if item["name"] == "test-secret-source"
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
    assert schema["properties"]["connection"]["default"] == {
        "region": "us-east-1"
    }
    assert "default" not in schema["properties"]["opaque"]
    assert "never-publish-this" not in json.dumps(document, sort_keys=True)
    assert "never-publish-this-example" not in json.dumps(document, sort_keys=True)
    assert "camel-case-token" not in json.dumps(document, sort_keys=True)
    assert "private-key-example" not in json.dumps(document, sort_keys=True)
    assert "private-key-enum" not in json.dumps(document, sort_keys=True)
    assert "nested-secret-value" not in json.dumps(document, sort_keys=True)
    assert "write-only-default" not in json.dumps(document, sort_keys=True)
