"""Real PostgreSQL connector qualification; enabled with ETLANTIC_SQL_TEST_URL."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

import anyio
import pytest
from sqlalchemy import create_engine, text

from etlantic.connectors.models import CommitReceipt
from etlantic.connectors.session import write_via_sink_connector
from etlantic.secrets import SecretValue
from etlantic_sql.live_postgresql import (
    LivePostgresSinkConnector,
    LivePostgresSourceConnector,
    LivePostgresStorageConnector,
)

URL = os.environ.get("ETLANTIC_SQL_TEST_URL")
pytestmark = pytest.mark.skipif(
    not URL, reason="requires an isolated live PostgreSQL URL"
)


@pytest.fixture(autouse=True)
def provision_test_tables() -> Any:
    assert URL
    engine = create_engine(URL, hide_parameters=True)
    with engine.begin() as connection:
        connection.execute(
            text("DROP TABLE IF EXISTS public.etlantic_connector_effects")
        )
        connection.execute(text("DROP TABLE IF EXISTS public.etlantic_phase056_orders"))
        connection.execute(
            text(
                "CREATE TABLE public.etlantic_phase056_orders "
                "(id text PRIMARY KEY, payload text NOT NULL)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE public.etlantic_connector_effects ("
                "effect_id text PRIMARY KEY, intent_fingerprint text NOT NULL, "
                "publication_id text NOT NULL UNIQUE, row_count bigint NOT NULL, "
                "committed_at timestamptz NOT NULL DEFAULT now())"
            )
        )
    yield
    with engine.begin() as connection:
        connection.execute(
            text("DROP TABLE IF EXISTS public.etlantic_connector_effects")
        )
        connection.execute(text("DROP TABLE IF EXISTS public.etlantic_phase056_orders"))
    engine.dispose()


@pytest.fixture
def secret_context() -> dict[str, Any]:
    assert URL
    return {
        "secret": SecretValue(
            _value=URL,
            provider="test",
            name="postgresql-url",
            key="url",
            version="fixture",
        ),
        "run_id": "phase056-live-test",
        "node": "sink-orders",
    }


def _binding(mode: str, **extra: Any) -> dict[str, Any]:
    return {
        "provider": "postgresql",
        "location": "etlantic_phase056_orders",
        "config": {
            "mode": mode,
            "effect_table": "public.etlantic_connector_effects",
            **extra,
        },
    }


def _write(
    connector: LivePostgresSinkConnector,
    binding: Mapping[str, Any],
    context: Mapping[str, Any],
    rows: list[dict[str, Any]],
) -> CommitReceipt:
    async def _run() -> CommitReceipt:
        return await write_via_sink_connector(
            connector,
            binding=binding,
            data=rows,
            context=context,
        )

    return anyio.run(_run)


def test_live_append_upsert_replace_and_idempotent_replay(
    secret_context: dict[str, Any],
) -> None:
    assert URL is not None
    engine = create_engine(URL, hide_parameters=True)
    sink = LivePostgresSinkConnector()
    context = {**secret_context, "node": "append"}

    first = _write(
        sink,
        _binding("append"),
        context,
        [{"id": "1", "payload": "old"}, {"id": "2", "payload": "keep"}],
    )
    assert first.status == "committed"

    # A process restart uses the stable effect ID and returns the durable receipt
    # without inserting the accepted rows twice.
    replay = _write(
        LivePostgresSinkConnector(),
        _binding("append"),
        context,
        [{"id": "1", "payload": "old"}, {"id": "2", "payload": "keep"}],
    )
    assert replay.publication_id == first.publication_id

    upsert = _write(
        sink,
        _binding("upsert", key_columns=["id"]),
        {**secret_context, "node": "upsert"},
        [{"id": "1", "payload": "new"}],
    )
    assert upsert.status == "committed"

    replace = _write(
        sink,
        _binding("replace"),
        {**secret_context, "node": "replace"},
        [{"id": "3", "payload": "replacement"}],
    )
    assert replace.status == "committed"
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT id, payload FROM public.etlantic_phase056_orders ORDER BY id")
        ).all()
    assert rows == [("3", "replacement")]
    engine.dispose()


def test_live_source_and_storage_inspection_are_bounded_and_read_only(
    secret_context: dict[str, Any],
) -> None:
    assert URL is not None
    engine = create_engine(URL, hide_parameters=True)
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO public.etlantic_phase056_orders VALUES ('1', 'row')")
        )
    source = LivePostgresSourceConnector()
    binding = {
        "provider": "postgresql",
        "location": "etlantic_phase056_orders",
        "config": {"row_limit": 10, "batch_size": 1, "max_bytes": 1024},
    }

    async def read_all() -> list[dict[str, Any]]:
        plan = await source.plan_read(binding=binding, context=secret_context)
        batches = [
            batch
            async for batch in source.read_batches(
                plan=plan, binding=binding, context=secret_context
            )
        ]
        return [dict(row) for batch in batches for row in batch.records]

    records = anyio.run(read_all)
    assert records == [{"id": "1", "payload": "row"}]

    storage = LivePostgresStorageConnector()

    async def inspect() -> Any:
        return await storage.inspect_schema(
            binding={"provider": "postgresql", "location": "etlantic_phase056_orders"},
            context=secret_context,
        )

    inspection = anyio.run(inspect)
    assert {field["name"] for field in inspection.fields} == {"id", "payload"}
    assert inspection.row_estimate is not None
    engine.dispose()


def test_live_failed_stage_rolls_back_and_effect_ack_reconciles(
    secret_context: dict[str, Any],
) -> None:
    sink = LivePostgresSinkConnector()
    failed = _write(
        sink,
        _binding("append"),
        {**secret_context, "node": "bad-write"},
        [{"id": "bad", "payload": "row", "unknown": "column"}],
    )
    assert failed.status == "rolled_back"

    class LostCommitAck(LivePostgresSinkConnector):
        async def commit(
            self, session: Any, *, context: Mapping[str, Any]
        ) -> CommitReceipt:
            await super().commit(session, context=context)
            raise RuntimeError("simulated lost commit acknowledgement")

    lost_connector = LostCommitAck()
    lost_context = {**secret_context, "node": "lost-ack"}
    lost = _write(
        lost_connector,
        _binding("append"),
        lost_context,
        [{"id": "ack", "payload": "durable"}],
    )
    assert lost.status == "unknown"
    recovered = anyio.run(
        lambda: LivePostgresSinkConnector().reconcile(lost, context=lost_context)
    )
    assert recovered.status == "committed"
