"""Real PostgreSQL connector qualification; enabled with ETLANTIC_SQL_TEST_URL."""

from __future__ import annotations

import os
import uuid
from collections.abc import Mapping
from typing import Any

import anyio
import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("etlantic_sql.live_postgresql")

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from etlantic import Data, Extract, Load, Pipeline, PipelineRuntime, Profile
from etlantic.connectors.errors import ConnectorReadError, ConnectorWriteError
from etlantic.connectors.models import CommitReceipt
from etlantic.connectors.session import write_via_sink_connector
from etlantic.registry import BindingDescriptor, PlanningContext
from etlantic.runtime.state import RunStatus
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


class ManagedOrder(Data):
    id: str
    payload: str


class OverlappingManagedTransfer(Pipeline):
    source = Extract[ManagedOrder](asset="source")
    sink = Load[ManagedOrder](input=source, asset="sink")


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


@pytest.mark.parametrize("row_count", [9_000, 10_000])
def test_live_upsert_respects_bind_parameter_limit(
    secret_context: dict[str, Any], row_count: int
) -> None:
    assert URL is not None
    engine = create_engine(URL, hide_parameters=True)
    suffix = uuid.uuid4().hex
    target = f"etlantic_bulk_{suffix}"
    effects = f"etlantic_effects_{suffix}"
    binding = {
        "provider": "postgresql",
        "location": target,
        "config": {
            "mode": "upsert",
            "key_columns": ["id"],
            "effect_table": effects,
        },
    }
    context = {
        **secret_context,
        "run_id": f"bind-limit-{suffix}",
        "node": "bulk-upsert",
    }
    rows = [
        {"id": index, **{f"c{column}": column for column in range(1, 7)}}
        for index in range(row_count)
    ]
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    f"CREATE TABLE public.{target} ("
                    "id integer PRIMARY KEY, "
                    "c1 integer NOT NULL, c2 integer NOT NULL, "
                    "c3 integer NOT NULL, c4 integer NOT NULL, "
                    "c5 integer NOT NULL, c6 integer NOT NULL)"
                )
            )
            connection.execute(
                text(
                    f"CREATE TABLE public.{effects} ("
                    "effect_id text PRIMARY KEY, intent_fingerprint text NOT NULL, "
                    "publication_id text NOT NULL UNIQUE, row_count bigint NOT NULL)"
                )
            )

        receipt = _write(LivePostgresSinkConnector(), binding, context, rows)
        assert receipt.status == "committed"
        assert receipt.metadata["row_count"] == row_count
        with engine.connect() as connection:
            target_rows = connection.execute(
                text(f"SELECT count(*) FROM public.{target}")
            ).scalar_one()
            effect_rows = connection.execute(
                text(
                    f"SELECT row_count FROM public.{effects} "
                    "WHERE effect_id = :effect_id"
                ),
                {"effect_id": receipt.session_id},
            ).scalar_one()
        assert target_rows == row_count
        assert effect_rows == row_count
    finally:
        with engine.begin() as connection:
            connection.execute(text(f"DROP TABLE IF EXISTS public.{effects}"))
            connection.execute(text(f"DROP TABLE IF EXISTS public.{target}"))
        engine.dispose()


@pytest.mark.parametrize("duplicate_index", [1, 9_999])
def test_live_upsert_duplicate_keys_are_stable_across_chunks(
    secret_context: dict[str, Any], duplicate_index: int
) -> None:
    assert URL is not None
    engine = create_engine(URL, hide_parameters=True)
    suffix = uuid.uuid4().hex
    target = f"etlantic_duplicate_{suffix}"
    effects = f"etlantic_effects_{suffix}"
    binding = {
        "provider": "postgresql",
        "location": target,
        "config": {
            "mode": "upsert",
            "key_columns": ["id"],
            "effect_table": effects,
        },
    }
    context = {
        **secret_context,
        "run_id": f"duplicate-key-{suffix}",
        "node": "duplicate-key-upsert",
    }
    rows = [
        {"id": index, **{f"c{column}": column for column in range(1, 7)}}
        for index in range(10_000)
    ]
    rows[duplicate_index]["id"] = 0
    rows[duplicate_index]["c1"] = 99
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    f"CREATE TABLE public.{target} ("
                    "id integer PRIMARY KEY, "
                    "c1 integer NOT NULL, c2 integer NOT NULL, "
                    "c3 integer NOT NULL, c4 integer NOT NULL, "
                    "c5 integer NOT NULL, c6 integer NOT NULL)"
                )
            )
            connection.execute(
                text(
                    f"CREATE TABLE public.{effects} ("
                    "effect_id text PRIMARY KEY, intent_fingerprint text NOT NULL, "
                    "publication_id text NOT NULL UNIQUE, row_count bigint NOT NULL)"
                )
            )

        receipt = _write(LivePostgresSinkConnector(), binding, context, rows)
        assert receipt.status == "committed"
        assert receipt.metadata["row_count"] == len(rows)
        with engine.connect() as connection:
            target_rows = connection.execute(
                text(f"SELECT count(*) FROM public.{target}")
            ).scalar_one()
            duplicate_value = connection.execute(
                text(f"SELECT c1 FROM public.{target} WHERE id = 0")
            ).scalar_one()
        assert target_rows == len(rows) - 1
        assert duplicate_value == 99
    finally:
        with engine.begin() as connection:
            connection.execute(text(f"DROP TABLE IF EXISTS public.{effects}"))
            connection.execute(text(f"DROP TABLE IF EXISTS public.{target}"))
        engine.dispose()


def test_live_upsert_does_not_retry_trigger_cardinality_errors(
    secret_context: dict[str, Any],
) -> None:
    assert URL is not None
    engine = create_engine(URL, hide_parameters=True)
    suffix = uuid.uuid4().hex
    target = f"etlantic_trigger_{suffix}"
    effects = f"etlantic_effects_{suffix}"
    trigger_function = f"etlantic_single_row_{suffix}"
    binding = {
        "provider": "postgresql",
        "location": target,
        "config": {
            "mode": "upsert",
            "key_columns": ["id"],
            "effect_table": effects,
        },
    }
    context = {
        **secret_context,
        "run_id": f"trigger-cardinality-{suffix}",
        "node": "trigger-cardinality-upsert",
    }
    sink = LivePostgresSinkConnector()
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    f"CREATE TABLE public.{target} ("
                    "id integer PRIMARY KEY, payload text NOT NULL)"
                )
            )
            connection.execute(
                text(
                    f"CREATE TABLE public.{effects} ("
                    "effect_id text PRIMARY KEY, intent_fingerprint text NOT NULL, "
                    "publication_id text NOT NULL UNIQUE, row_count bigint NOT NULL)"
                )
            )
            connection.execute(
                text(
                    f"CREATE FUNCTION public.{trigger_function}() RETURNS trigger "
                    "LANGUAGE plpgsql AS $$ BEGIN "
                    "PERFORM (SELECT id FROM inserted_rows); RETURN NULL; END $$"
                )
            )
            connection.execute(
                text(
                    f"CREATE TRIGGER reject_multirow_insert AFTER INSERT ON public.{target} "
                    "REFERENCING NEW TABLE AS inserted_rows "
                    f"FOR EACH STATEMENT EXECUTE FUNCTION public.{trigger_function}()"
                )
            )

        async def reject_trigger_cardinality_error() -> ConnectorWriteError:
            plan = await sink.plan_write(binding=binding, context=context)
            session = await sink.begin_write(
                plan=plan, binding=binding, context=context
            )
            await sink.write_batch(
                session,
                [{"id": 1, "payload": "first"}, {"id": 2, "payload": "second"}],
                context=context,
            )
            with pytest.raises(ConnectorWriteError) as failure:
                await sink.prepare(session, context=context)
            await sink.abort(session, context=context)
            return failure.value

        failure = anyio.run(reject_trigger_cardinality_error)
        assert failure.code == "PMCONN876"
        with engine.connect() as connection:
            target_rows = connection.execute(
                text(f"SELECT count(*) FROM public.{target}")
            ).scalar_one()
            effect_rows = connection.execute(
                text(f"SELECT count(*) FROM public.{effects}")
            ).scalar_one()
        assert target_rows == 0
        assert effect_rows == 0
    finally:
        with engine.begin() as connection:
            connection.execute(text(f"DROP TABLE IF EXISTS public.{effects}"))
            connection.execute(text(f"DROP TABLE IF EXISTS public.{target}"))
            connection.execute(
                text(f"DROP FUNCTION IF EXISTS public.{trigger_function}()")
            )
        engine.dispose()


def test_live_upsert_rolls_back_when_a_later_chunk_fails(
    secret_context: dict[str, Any],
) -> None:
    assert URL is not None
    engine = create_engine(URL, hide_parameters=True)
    suffix = uuid.uuid4().hex
    target = f"etlantic_bulk_{suffix}"
    effects = f"etlantic_effects_{suffix}"
    binding = {
        "provider": "postgresql",
        "location": target,
        "config": {
            "mode": "upsert",
            "key_columns": ["id"],
            "effect_table": effects,
        },
    }
    context = {
        **secret_context,
        "run_id": f"later-chunk-failure-{suffix}",
        "node": "bulk-upsert",
    }
    rows = [
        {"id": index, **{f"c{column}": column for column in range(1, 7)}}
        for index in range(10_000)
    ]
    rows[-1]["c1"] = -1
    sink = LivePostgresSinkConnector()
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    f"CREATE TABLE public.{target} ("
                    "id integer PRIMARY KEY, "
                    "c1 integer NOT NULL, c2 integer NOT NULL, "
                    "c3 integer NOT NULL, c4 integer NOT NULL, "
                    "c5 integer NOT NULL, c6 integer NOT NULL, "
                    "CONSTRAINT ck_reject_negative CHECK (c1 >= 0))"
                )
            )
            connection.execute(
                text(
                    f"CREATE TABLE public.{effects} ("
                    "effect_id text PRIMARY KEY, intent_fingerprint text NOT NULL, "
                    "publication_id text NOT NULL UNIQUE, row_count bigint NOT NULL)"
                )
            )

        async def fail_in_later_chunk() -> tuple[Any, ConnectorWriteError]:
            plan = await sink.plan_write(binding=binding, context=context)
            session = await sink.begin_write(
                plan=plan, binding=binding, context=context
            )
            await sink.write_batch(session, rows, context=context)
            with pytest.raises(ConnectorWriteError) as failure:
                await sink.prepare(session, context=context)
            await sink.abort(session, context=context)
            return session, failure.value

        _session, failure = anyio.run(fail_in_later_chunk)
        cause_text = str(failure)
        cause = failure.__cause__
        while cause is not None:
            cause_text += "\n" + str(cause)
            cause = cause.__cause__
        assert "ck_reject_negative" in cause_text
        with engine.connect() as connection:
            target_rows = connection.execute(
                text(f"SELECT count(*) FROM public.{target}")
            ).scalar_one()
            effect_rows = connection.execute(
                text(f"SELECT count(*) FROM public.{effects}")
            ).scalar_one()
        assert target_rows == 0
        assert effect_rows == 0
    finally:
        with engine.begin() as connection:
            connection.execute(text(f"DROP TABLE IF EXISTS public.{effects}"))
            connection.execute(text(f"DROP TABLE IF EXISTS public.{target}"))
        engine.dispose()


def test_live_postgresql_partition_read_and_atomic_replace(
    secret_context: dict[str, Any],
) -> None:
    assert URL is not None
    engine = create_engine(URL, hide_parameters=True)
    with engine.begin() as connection:
        connection.execute(
            text("DROP TABLE IF EXISTS public.etlantic_phase056_partition_orders")
        )
        connection.execute(
            text(
                "CREATE TABLE public.etlantic_phase056_partition_orders "
                "(id text PRIMARY KEY, payload text NOT NULL, partition_key text)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO public.etlantic_phase056_partition_orders "
                "(id, payload, partition_key) VALUES "
                "('old-a', 'old', 'a'), ('keep-b', 'keep', 'b')"
            )
        )

    source = LivePostgresSourceConnector()
    source_binding = {
        "provider": "postgresql",
        "location": "etlantic_phase056_partition_orders",
        "config": {"partition_column": "partition_key"},
    }
    source_context = {**secret_context, "etlantic.partition_ids": ["a"]}

    async def read_selected() -> list[dict[str, Any]]:
        plan = await source.plan_read_partitions(
            binding=source_binding,
            context=source_context,
            partition_ids=("a",),
        )
        batches = [
            batch
            async for batch in source.read_batches(
                plan=plan, binding=source_binding, context=source_context
            )
        ]
        return [dict(row) for batch in batches for row in batch.records]

    assert anyio.run(read_selected) == [
        {"id": "old-a", "payload": "old", "partition_key": "a"}
    ]

    sink = LivePostgresSinkConnector()
    sink_binding = {
        "provider": "postgresql",
        "location": "etlantic_phase056_partition_orders",
        "config": {
            "mode": "append",
            "partition_column": "partition_key",
            "effect_table": "public.etlantic_connector_effects",
        },
    }
    sink_context = {
        **secret_context,
        "run_id": f"partition-{uuid.uuid4().hex}",
        "etlantic.partition_ids": ["a"],
    }
    receipt = _write(
        sink,
        sink_binding,
        sink_context,
        [{"id": "new-a", "payload": "new", "partition_key": "a"}],
    )
    assert receipt.status == "committed"
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT id, payload, partition_key "
                "FROM public.etlantic_phase056_partition_orders ORDER BY id"
            )
        ).all()
    assert rows == [("keep-b", "keep", "b"), ("new-a", "new", "a")]

    empty_context = {
        **secret_context,
        "run_id": f"partition-empty-{uuid.uuid4().hex}",
        "etlantic.partition_ids": ["a"],
    }
    empty_receipt = _write(sink, sink_binding, empty_context, [])
    assert empty_receipt.status == "committed"
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT id, payload, partition_key "
                "FROM public.etlantic_phase056_partition_orders ORDER BY id"
            )
        ).all()
    assert rows == [("keep-b", "keep", "b")]
    with engine.begin() as connection:
        connection.execute(
            text("DROP TABLE IF EXISTS public.etlantic_phase056_partition_orders")
        )
    engine.dispose()


def test_live_postgresql_partition_replace_rejects_rows_outside_selector(
    secret_context: dict[str, Any],
) -> None:
    assert URL is not None
    engine = create_engine(URL, hide_parameters=True)
    with engine.begin() as connection:
        connection.execute(
            text("DROP TABLE IF EXISTS public.etlantic_phase056_partition_orders")
        )
        connection.execute(
            text(
                "CREATE TABLE public.etlantic_phase056_partition_orders "
                "(id text PRIMARY KEY, payload text NOT NULL, partition_key text)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO public.etlantic_phase056_partition_orders "
                "(id, payload, partition_key) VALUES ('keep-b', 'keep', 'b')"
            )
        )
    context = {
        **secret_context,
        "run_id": f"partition-invalid-{uuid.uuid4().hex}",
        "etlantic.partition_ids": ["a"],
    }
    receipt = _write(
        LivePostgresSinkConnector(),
        {
            "provider": "postgresql",
            "location": "etlantic_phase056_partition_orders",
            "config": {
                "mode": "append",
                "partition_column": "partition_key",
                "effect_table": "public.etlantic_connector_effects",
            },
        },
        context,
        [{"id": "wrong", "payload": "wrong", "partition_key": "b"}],
    )
    assert receipt.status == "rolled_back"
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT id, payload, partition_key "
                "FROM public.etlantic_phase056_partition_orders"
            )
        ).all()
    assert rows == [("keep-b", "keep", "b")]
    with engine.begin() as connection:
        connection.execute(
            text("DROP TABLE IF EXISTS public.etlantic_phase056_partition_orders")
        )
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

    async def read_all(
        *, row_limit: int = 10, max_bytes: int = 1024
    ) -> list[dict[str, Any]]:
        binding = {
            "provider": "postgresql",
            "location": "etlantic_phase056_orders",
            "config": {
                "row_limit": row_limit,
                "batch_size": 1,
                "max_bytes": max_bytes,
            },
        }
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
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO public.etlantic_phase056_orders VALUES ('2', 'another row')"
            )
        )

    async def read_with_row_limit() -> list[dict[str, Any]]:
        return await read_all(row_limit=1)

    async def read_with_byte_limit() -> list[dict[str, Any]]:
        return await read_all(max_bytes=1)

    with pytest.raises(ConnectorReadError) as row_error:
        anyio.run(read_with_row_limit)
    assert row_error.value.code == "PMCONN855"
    with pytest.raises(ConnectorReadError) as byte_error:
        anyio.run(read_with_byte_limit)
    assert byte_error.value.code == "PMCONN856"

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


def test_live_postgresql_resource_identity_resolves_table_aliases(
    secret_context: dict[str, Any],
) -> None:
    source = LivePostgresSourceConnector()
    sink = LivePostgresSinkConnector()

    async def resolve() -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
        source_identity = await source.resource_identities(
            binding={
                "provider": "postgresql",
                "location": "etlantic_phase056_orders",
            },
            context=secret_context,
        )
        aliased_sink_identity = await sink.resource_identities(
            binding={
                "provider": "postgresql",
                "config": {
                    "schema": "public",
                    "table": "etlantic_phase056_orders",
                    "mode": "append",
                },
            },
            context=secret_context,
        )
        other_sink_identity = await sink.resource_identities(
            binding={
                "provider": "postgresql",
                "config": {
                    "schema": "public",
                    "table": "other_table",
                    "mode": "append",
                },
            },
            context=secret_context,
        )
        return source_identity, aliased_sink_identity, other_sink_identity

    source_ids, alias_ids, other_ids = anyio.run(resolve)
    assert set(source_ids).intersection(alias_ids)
    assert not set(source_ids).intersection(other_ids)


def test_live_managed_postgresql_overlap_is_rejected_before_replace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert URL is not None
    monkeypatch.setenv("ETLANTIC_SQL_URL", URL)
    engine = create_engine(URL, hide_parameters=True)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO public.etlantic_phase056_orders VALUES "
                "('keep', 'source-row')"
            )
        )

    profile = Profile(name="dev", security_mode="development")
    planning = PlanningContext.create(profile=profile)
    planning.registry.register_binding(
        BindingDescriptor(
            binding="source",
            provider="postgresql",
            location="etlantic_phase056_orders",
            kind="source",
        )
    )
    planning.registry.register_binding(
        BindingDescriptor(
            binding="sink",
            provider="postgresql",
            location="etlantic_phase056_orders",
            kind="sink",
            config={"schema": "public", "mode": "replace"},
        )
    )
    runtime = PipelineRuntime()
    runtime.register_source_connector("postgresql", LivePostgresSourceConnector())
    runtime.register_sink_connector("postgresql", LivePostgresSinkConnector())

    report = OverlappingManagedTransfer.run(
        profile=profile, runtime=runtime, context=planning
    )

    assert report.status is RunStatus.PARTIAL
    assert any(item.code == "PMEXEC435" for item in report.diagnostics)
    assert "source-row" not in report.to_json()
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT id, payload FROM public.etlantic_phase056_orders")
        ).all()
    assert rows == [("keep", "source-row")]
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


@pytest.mark.parametrize("settlement", ["committed", "rolled_back"])
def test_live_reconciliation_does_not_settle_an_active_writer(
    secret_context: dict[str, Any], settlement: str
) -> None:
    async def run() -> None:
        writer = LivePostgresSinkConnector()
        binding = _binding("append")
        plan = await writer.plan_write(binding=binding, context=secret_context)
        session = await writer.begin_write(
            plan=plan, binding=binding, context=secret_context
        )
        settled = False
        try:
            await writer.write_batch(
                session,
                [{"id": "active", "payload": "pending"}],
                context=secret_context,
            )
            await writer.prepare(session, context=secret_context)
            uncertain = CommitReceipt(
                status="unknown",
                session_id=session.session_id,
                provider=session.provider,
                metadata=dict(session.metadata),
            )
            observer = LivePostgresSinkConnector()
            pending = await observer.reconcile(uncertain, context=secret_context)
            assert pending.status == "unknown"

            if settlement == "committed":
                await writer.commit(session, context=secret_context)
            else:
                await writer.abort(session, context=secret_context)
            settled = True
            resolved = await observer.reconcile(uncertain, context=secret_context)
            assert resolved.status == settlement
        finally:
            if not settled:
                await writer.abort(session, context=secret_context)

    anyio.run(run)


def test_live_reconciliation_remains_unknown_during_commit(
    secret_context: dict[str, Any],
) -> None:
    assert URL
    engine = create_engine(URL, hide_parameters=True)
    gate = uuid.uuid4().hex
    function_name = f"etlantic_commit_gate_{gate}"
    with engine.begin() as connection:
        connection.execute(
            text(
                f"CREATE FUNCTION public.{function_name}() RETURNS trigger "
                "LANGUAGE plpgsql AS $$ BEGIN "
                f"PERFORM pg_advisory_xact_lock(hashtextextended('{gate}', 0)); "
                "RETURN NEW; END $$"
            )
        )
        connection.execute(
            text(
                "CREATE CONSTRAINT TRIGGER etlantic_commit_gate "
                "AFTER INSERT ON public.etlantic_phase056_orders "
                "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
                f"EXECUTE FUNCTION public.{function_name}()"
            )
        )

    async def run() -> None:
        writer = LivePostgresSinkConnector()
        binding = _binding("append")
        plan = await writer.plan_write(binding=binding, context=secret_context)
        session = await writer.begin_write(
            plan=plan, binding=binding, context=secret_context
        )
        await writer.write_batch(
            session, [{"id": "commit", "payload": "in-flight"}], context=secret_context
        )
        await writer.prepare(session, context=secret_context)
        uncertain = CommitReceipt(
            status="unknown",
            session_id=session.session_id,
            provider=session.provider,
            metadata=dict(session.metadata),
        )
        observer = LivePostgresSinkConnector()

        async def commit() -> None:
            result = await writer.commit(session, context=secret_context)
            assert result.status == "committed"

        try:
            with engine.connect() as gate_connection:
                gate_connection.execute(
                    text("SELECT pg_advisory_lock(hashtextextended(:gate, 0))"),
                    {"gate": gate},
                )
                gate_connection.commit()
                async with anyio.create_task_group() as group:
                    group.start_soon(commit)
                    try:
                        with anyio.fail_after(5):
                            while True:
                                blocked = gate_connection.execute(
                                    text(
                                        "SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
                                        "WHERE datname = current_database() "
                                        "AND query = 'COMMIT' AND wait_event_type = 'Lock')"
                                    )
                                ).scalar_one()
                                gate_connection.commit()
                                if blocked:
                                    break
                                await anyio.sleep(0.01)
                        pending = await observer.reconcile(
                            uncertain, context=secret_context
                        )
                        assert pending.status == "unknown"
                    finally:
                        gate_connection.execute(
                            text(
                                "SELECT pg_advisory_unlock(hashtextextended(:gate, 0))"
                            ),
                            {"gate": gate},
                        )
                        gate_connection.commit()
            resolved = await observer.reconcile(uncertain, context=secret_context)
            assert resolved.status == "committed"
        finally:
            await writer.abort(session, context=secret_context)

    try:
        anyio.run(run)
    finally:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "DROP TRIGGER etlantic_commit_gate "
                    "ON public.etlantic_phase056_orders"
                )
            )
            connection.execute(text(f"DROP FUNCTION public.{function_name}()"))
        engine.dispose()


def test_live_sink_denies_ungranted_write_and_leaves_target_unchanged(
    secret_context: dict[str, Any],
) -> None:
    assert URL is not None
    admin_engine = create_engine(URL, hide_parameters=True)
    role = f"etlantic_p056_{uuid.uuid4().hex[:16]}"
    quoted_role = admin_engine.dialect.identifier_preparer.quote(role)
    try:
        with admin_engine.begin() as connection:
            connection.execute(text(f"CREATE ROLE {quoted_role} LOGIN"))
            connection.execute(
                text(
                    f"GRANT SELECT ON public.etlantic_phase056_orders TO {quoted_role}"
                )
            )
            connection.execute(
                text(
                    "GRANT SELECT ON public.etlantic_connector_effects "
                    f"TO {quoted_role}"
                )
            )

        restricted_url = (
            make_url(URL).set(username=role).render_as_string(hide_password=False)
        )
        restricted_context = {
            **secret_context,
            "node": "denied-write",
            "secret": SecretValue(
                _value=restricted_url,
                provider="test",
                name="postgresql-read-only-url",
                key="url",
                version="fixture",
            ),
        }
        result = _write(
            LivePostgresSinkConnector(),
            _binding("append"),
            restricted_context,
            [{"id": "denied", "payload": "must-not-publish"}],
        )
        assert result.status == "rolled_back"
        with admin_engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT count(*) FROM public.etlantic_phase056_orders")
                ).scalar_one()
                == 0
            )
    finally:
        with admin_engine.begin() as connection:
            connection.execute(text(f"DROP OWNED BY {quoted_role}"))
            connection.execute(text(f"DROP ROLE IF EXISTS {quoted_role}"))
        admin_engine.dispose()
