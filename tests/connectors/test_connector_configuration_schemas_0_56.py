"""Installed connector option schemas are a plan-time contract."""

from __future__ import annotations

import json

import pytest
from etlantic_foundry.connectors import FoundrySourceConnector

from etlantic.connectors.models import ConnectorInfo
from etlantic.connectors.negotiate import (
    PMCONN880,
    assert_binding_connector_capabilities,
)
from etlantic.exceptions import PipelineValidationError
from etlantic.registry import BindingDescriptor
from etlantic_sql.live_postgresql import (
    LivePostgresSinkConnector,
    LivePostgresSourceConnector,
)


def test_connector_info_configuration_schema_round_trips() -> None:
    info = FoundrySourceConnector().info()

    restored = ConnectorInfo.from_dict(info.to_dict())

    assert restored.configuration_schema == info.configuration_schema
    assert restored.configuration_schema["additionalProperties"] is False
    assert (
        restored.configuration_schema["properties"]["transaction_rid"]["minLength"] == 1
    )
    serialized = info.to_dict()
    serialized["configuration_schema"]["properties"].clear()
    assert "transaction_rid" in info.configuration_schema["properties"]


def test_postgresql_partition_options_are_in_the_installed_schema() -> None:
    source = LivePostgresSourceConnector().info()
    sink = LivePostgresSinkConnector().info()

    assert "source.partitioned" in source.capabilities
    assert "partition_column" in source.configuration_schema["properties"]
    assert "write.partition_replace" in sink.capabilities
    assert "partition_column" in sink.configuration_schema["properties"]


def test_installed_schema_rejects_unknown_option_without_echoing_values() -> None:
    binding = BindingDescriptor(
        binding="foundry-input",
        provider="foundry",
        kind="source",
        config={
            "base_url": "https://example.palantirfoundry.com",
            "dataset_rid": "ri.foundry.main.dataset.abc",
            "branch_name": "master",
            "transaction_rid": "ri.foundry.main.transaction.xyz",
            "access_token": "never-echo-this-secret",
        },
    )

    with pytest.raises(PipelineValidationError) as exc_info:
        assert_binding_connector_capabilities(
            {"input": binding},
            runtime_source_connectors={"foundry": FoundrySourceConnector()},
        )

    diagnostics = exc_info.value.report.diagnostics
    assert any(item.code == PMCONN880 for item in diagnostics)
    rendered = json.dumps([item.to_dict() for item in diagnostics], sort_keys=True)
    assert "never-echo-this-secret" not in rendered


def test_installed_schema_accepts_declared_binding_mode() -> None:
    binding = BindingDescriptor(
        binding="foundry-input",
        provider="foundry",
        kind="source",
        mode="snapshot",
        config={
            "base_url": "https://example.palantirfoundry.com",
            "dataset_rid": "ri.foundry.main.dataset.abc",
            "branch_name": "master",
            "transaction_rid": "ri.foundry.main.transaction.xyz",
        },
    )

    assert_binding_connector_capabilities(
        {"input": binding},
        runtime_source_connectors={"foundry": FoundrySourceConnector()},
    )
