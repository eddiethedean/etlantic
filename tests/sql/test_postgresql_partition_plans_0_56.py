"""Provider contract checks for bounded PostgreSQL partition operations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import anyio
import pytest

from etlantic.connectors.capabilities import (
    IDEMPOTENCY,
    SOURCE_PARTITIONED,
    WRITE_PARTITION_REPLACE,
)
from etlantic.connectors.errors import ConnectorConfigError
from etlantic_sql.live_postgresql import (
    LivePostgresSinkConnector,
    LivePostgresSourceConnector,
)


def test_partition_plans_bind_the_selected_values_and_capabilities() -> None:
    source = LivePostgresSourceConnector()
    source_binding = {
        "provider": "postgresql",
        "location": "orders",
        "config": {"partition_column": "region"},
    }
    source_plan = anyio.run(
        lambda: source.plan_read_partitions(
            binding=source_binding,
            context={},
            partition_ids=("north", "south"),
        )
    )
    assert source_plan.required_capabilities == (SOURCE_PARTITIONED,)
    assert source_plan.listing_intent["partition_column"] == "region"
    assert source_plan.listing_intent["partition_ids"] == ["north", "south"]

    sink = LivePostgresSinkConnector()
    sink_binding = {
        "provider": "postgresql",
        "location": "orders",
        "config": {"partition_column": "region"},
    }
    sink_plan = anyio.run(
        lambda: sink.plan_write_partitions(
            binding=sink_binding,
            context={},
            partition_ids=("north",),
        )
    )
    assert set(sink_plan.required_capabilities) == {
        WRITE_PARTITION_REPLACE,
        IDEMPOTENCY,
    }
    assert sink_plan.write_mode == "partition_replace"
    assert sink_plan.metadata["partition_ids"] == ["north"]


@pytest.mark.parametrize(
    "connector,binding",
    [
        (
            LivePostgresSourceConnector(),
            {"provider": "postgresql", "location": "orders", "config": {}},
        ),
        (
            LivePostgresSinkConnector(),
            {"provider": "postgresql", "location": "orders", "config": {}},
        ),
    ],
)
def test_partition_plans_require_a_configured_partition_column(
    connector: LivePostgresSourceConnector | LivePostgresSinkConnector,
    binding: Mapping[str, Any],
) -> None:
    with pytest.raises(ConnectorConfigError, match="partition_column"):
        if isinstance(connector, LivePostgresSourceConnector):
            anyio.run(
                lambda: connector.plan_read_partitions(
                    binding=binding,
                    context={},
                    partition_ids=("north",),
                )
            )
        else:
            anyio.run(
                lambda: connector.plan_write_partitions(
                    binding=binding,
                    context={},
                    partition_ids=("north",),
                )
            )


@pytest.mark.parametrize("partition_ids", [(), ("",), ("dup", "dup")])
def test_partition_plans_reject_empty_or_duplicate_selectors(
    partition_ids: tuple[str, ...],
) -> None:
    connector = LivePostgresSourceConnector()
    with pytest.raises(ConnectorConfigError, match="partition ids"):
        anyio.run(
            lambda: connector.plan_read_partitions(
                binding={
                    "provider": "postgresql",
                    "location": "orders",
                    "config": {"partition_column": "region"},
                },
                context={},
                partition_ids=partition_ids,
            )
        )
