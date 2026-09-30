# pyright: reportMissingImports=false, reportOptionalSubscript=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownVariableType=false
"""CP1 SQLModel tables are owned by the versioned migration chain."""

from __future__ import annotations

import hashlib
import os
import uuid
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from importlib import import_module
from pathlib import Path
from threading import Barrier
from typing import cast

import pytest

pytest.importorskip("sqlmodel")
pytest.importorskip("etlantic_sqlmodel")

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.schema import CreateSchema, DropSchema

from etlantic.control_plane import (
    ControlPlaneContext,
    ControlPlaneError,
    EnvironmentRef,
    Principal,
    RegistryDefinitionRepository,
    RegistryProvider,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic_sqlmodel.control_plane import (
    SQLModelDefinitionRepository,
    SqlModelEventStore,
    SqlModelRegistryProvider,
    SQLModelSubmissionStore,
    create_sqlite_engine,
)
from etlantic_sqlmodel.migrations import (
    VERSIONS,
    apply_migrations,
    current_version,
    downgrade,
    upgrade,
)

pytestmark = pytest.mark.sqlmodel


def test_006_migration_imports_legacy_definitions_as_immutable_revisions(
    tmp_path: Path,
) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'legacy-definitions.db'}")
    assert upgrade(engine, target="005_cp1_reference") == "005_cp1_reference"
    ctx = _ctx()
    legacy = SQLModelDefinitionRepository(engine)
    document = {
        "name": "orders",
        "authoring_id": "natural metadata remains intact",
    }
    legacy.put(ctx, "legacy-orders", document)

    assert upgrade(engine) == "009_event_retention_tombstones_0_56"
    registry = cast(RegistryProvider, SqlModelRegistryProvider(engine))
    definitions = RegistryDefinitionRepository(registry)
    current = definitions.resolve_revision(ctx, "legacy-orders", "current")
    exact = definitions.resolve_revision(ctx, "legacy-orders", current.revision_id)
    assert current.document == document
    assert exact == current
    assert legacy.get(ctx, "legacy-orders") == document

    # Re-applying its backfill is idempotent and keeps the immutable revision.
    migration = import_module(
        "etlantic_sqlmodel.migrations.versions.006_managed_definition_revisions_0_56"
    )
    migration.upgrade(engine)
    assert definitions.resolve_revision(ctx, "legacy-orders", "current") == current


@pytest.fixture
def postgres_engine_factory() -> Iterator[Callable[[], Engine]]:
    url = os.environ.get("ETLANTIC_SQLMODEL_TEST_URL")
    if not url:
        pytest.skip("ETLANTIC_SQLMODEL_TEST_URL is not configured")
    pytest.importorskip("psycopg")

    admin_engine = create_engine(url)
    schema = f"etlantic_cp1_{uuid.uuid4().hex}"
    with admin_engine.begin() as connection:
        connection.execute(CreateSchema(schema))

    engines: list[Engine] = []

    def factory() -> Engine:
        engine = create_engine(
            url,
            connect_args={"options": f"-csearch_path={schema}"},
        )
        engines.append(engine)
        return engine

    try:
        yield factory
    finally:
        for engine in engines:
            engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin_engine.dispose()


def _ctx(
    tenant: str = "tenant-a", workspace: str = "workspace-a"
) -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(subject="alice"),
        tenant=TenantRef(tenant_id=tenant),
        workspace=WorkspaceRef(tenant_id=tenant, workspace_id=workspace),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id="default"),
    )


def test_latest_migration_provisions_cp1_and_report_tables(tmp_path: Path) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'cp1.db'}")

    assert apply_migrations(engine) == "009_event_retention_tombstones_0_56"
    assert current_version(engine) == "009_event_retention_tombstones_0_56"
    assert {
        "cp_definitions",
        "cp_submissions",
        "cp_events",
        "cp_run_reports",
    }.issubset(set(inspect(engine).get_table_names()))
    constraints = {
        constraint["name"]
        for table in ("cp_definitions", "cp_submissions", "cp_events")
        for constraint in inspect(engine).get_unique_constraints(table)
    }
    assert constraints >= {
        "uq_cp_definition_scope",
        "uq_cp_submission_idem",
        "uq_cp_event_scope_seq",
    }

    ctx = _ctx()
    definitions = SQLModelDefinitionRepository(engine)
    submissions = SQLModelSubmissionStore(engine)
    events = SqlModelEventStore(engine)
    definitions.put(ctx, "definition-1", {"name": "orders"})
    accepted = submissions.accept(
        ctx,
        idempotency_key="idem-1",
        payload={"definition_id": "definition-1"},
    )
    event = events.append(ctx, kind="run.accepted", payload={"run_id": "run-1"})

    restarted = create_sqlite_engine(f"sqlite:///{tmp_path / 'cp1.db'}")
    assert SQLModelDefinitionRepository(restarted).get(ctx, "definition-1") == {
        "name": "orders"
    }
    receipt = SQLModelSubmissionStore(restarted).lookup_idempotency(ctx, "idem-1")
    assert receipt is not None
    assert receipt.submission_id == accepted.receipt.submission_id
    replayed = SqlModelEventStore(restarted).list_after_cursor(ctx, None)
    assert len(replayed) == 1
    assert replayed[0].event_id == event.event_id


@pytest.mark.parametrize("previous_head", VERSIONS[:-1])
def test_upgrade_from_published_head_adds_managed_reports_without_replacing_schema(
    tmp_path: Path,
    previous_head: str,
) -> None:
    engine = create_sqlite_engine(
        f"sqlite:///{tmp_path / previous_head.replace('/', '_')}.db"
    )

    assert upgrade(engine, target=previous_head) == previous_head
    before = set(inspect(engine).get_table_names())
    if previous_head in {
        "007_managed_run_reports_0_56",
        "008_idempotent_run_events_0_56",
    }:
        assert "cp_run_reports" in before
    else:
        assert "cp_run_reports" not in before
    if previous_head == "008_idempotent_run_events_0_56":
        assert "cp_event_idempotency" in before
        assert {
            "tenant_id",
            "workspace_id",
            "event_key",
            "event_id",
        }.issubset(
            {column["name"] for column in inspect(engine).get_columns("cp_event_idempotency")}
        )
    else:
        assert "cp_event_idempotency" not in before

    assert upgrade(engine) == "009_event_retention_tombstones_0_56"
    tables = set(inspect(engine).get_table_names())
    assert before.issubset(tables)
    assert {
        "cp_definitions",
        "cp_submissions",
        "cp_events",
        "cp_run_reports",
        "cp_event_idempotency",
    }.issubset(tables)
    assert {
        "event_kind",
        "payload_sha256",
        "sequence",
        "cursor",
    }.issubset(
        {column["name"] for column in inspect(engine).get_columns("cp_event_idempotency")}
    )


def test_managed_report_migration_downgrade_preserves_prior_tables(
    tmp_path: Path,
) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'report-migration.db'}")
    assert upgrade(engine) == "009_event_retention_tombstones_0_56"

    assert downgrade(engine, target="006_managed_definition_revisions_0_56") == (
        "006_managed_definition_revisions_0_56"
    )
    tables = set(inspect(engine).get_table_names())
    assert "cp_run_reports" not in tables
    assert {
        "cp_definitions",
        "cp_events",
        "cp_registry_revisions",
    }.issubset(tables)

    assert upgrade(engine) == "009_event_retention_tombstones_0_56"
    assert "cp_run_reports" in set(inspect(engine).get_table_names())


def test_idempotent_event_migration_round_trip_preserves_event_history(
    tmp_path: Path,
) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'event-migration.db'}")
    assert upgrade(engine) == "009_event_retention_tombstones_0_56"
    ctx = _ctx()
    events = SqlModelEventStore(engine)
    original = events.append(
        ctx, kind="run.accepted", payload={"run_id": "run-migration"}
    )

    assert downgrade(engine, target="007_managed_run_reports_0_56") == (
        "007_managed_run_reports_0_56"
    )
    assert "cp_event_idempotency" not in set(inspect(engine).get_table_names())
    assert upgrade(engine) == "009_event_retention_tombstones_0_56"
    assert "cp_event_idempotency" in set(inspect(engine).get_table_names())
    events = SqlModelEventStore(engine)
    repeated = events.append_once(
        ctx,
        event_key="run-migration:attempt-1:started",
        kind="run.started",
        payload={"run_id": "run-migration", "attempt_id": "attempt-1"},
    )
    same = events.append_once(
        ctx,
        event_key="run-migration:attempt-1:started",
        kind="run.started",
        payload={"run_id": "run-migration", "attempt_id": "attempt-1"},
    )
    assert same.event_id == repeated.event_id
    retained = events.list_after_cursor(ctx, None, limit=10)
    assert retained[0].event_id == original.event_id
    assert [event.kind for event in retained] == [
        "run.accepted",
        "run.started",
    ]


def test_event_retention_migration_backfills_previously_published_keys(
    tmp_path: Path,
) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'event-tombstone-backfill.db'}")
    assert upgrade(engine, target="008_idempotent_run_events_0_56") == (
        "008_idempotent_run_events_0_56"
    )
    ctx = _ctx()
    events = SqlModelEventStore(engine)
    prior = events.append(
        ctx, kind="run.started", payload={"run_id": "legacy-key-run"}
    )
    key = "legacy-key-started"
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO cp_event_idempotency "
                "(tenant_id, workspace_id, event_key, event_id) "
                "VALUES (:tenant_id, :workspace_id, :event_key, :event_id)"
            ),
            {
                "tenant_id": ctx.tenant.tenant_id,
                "workspace_id": ctx.workspace.workspace_id,
                "event_key": hashlib.sha256(key.encode()).hexdigest(),
                "event_id": prior.event_id,
            },
        )

    assert upgrade(engine) == "009_event_retention_tombstones_0_56"
    repeated = SqlModelEventStore(engine).append_once(
        ctx,
        event_key=key,
        kind="run.started",
        payload={"run_id": "legacy-key-run"},
    )
    assert repeated.event_id == prior.event_id
    with engine.connect() as connection:
        metadata = connection.execute(
            text(
                "SELECT event_kind, payload_sha256, sequence, cursor "
                "FROM cp_event_idempotency WHERE event_key = :event_key"
            ),
            {"event_key": hashlib.sha256(key.encode()).hexdigest()},
        ).one()
    assert metadata[0] == "run.started"
    assert metadata[1] == hashlib.sha256(
        b'{"run_id": "legacy-key-run"}'
    ).hexdigest()
    assert metadata[2:] == (prior.sequence, prior.cursor)


@pytest.mark.parametrize(
    "starting_head",
    (None, "004_schedules_0_47"),
    ids=("fresh", "upgrade-from-004"),
)
def test_postgresql_migration_provisions_and_persists_cp1_stores(
    postgres_engine_factory: Callable[[], Engine],
    starting_head: str | None,
) -> None:
    engine = postgres_engine_factory()
    if starting_head is None:
        assert current_version(engine) is None
    else:
        assert upgrade(engine, target=starting_head) == starting_head
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO cp_schedule_snapshot "
                    "(store_id, payload_json, payload_version) "
                    "VALUES (:store_id, :payload_json, :payload_version)"
                ),
                {
                    "store_id": "before-cp1",
                    "payload_json": '{"preserved": true}',
                    "payload_version": 7,
                },
            )

    assert upgrade(engine) == "009_event_retention_tombstones_0_56"
    assert current_version(engine) == "009_event_retention_tombstones_0_56"
    tables = set(inspect(engine).get_table_names())
    assert {
        "cp_definitions",
        "cp_submissions",
        "cp_events",
        "cp_run_reports",
    }.issubset(tables)
    if starting_head is not None:
        with engine.connect() as connection:
            preserved = connection.execute(
                text(
                    "SELECT payload_json, payload_version "
                    "FROM cp_schedule_snapshot WHERE store_id = :store_id"
                ),
                {"store_id": "before-cp1"},
            ).one()
        assert preserved == ('{"preserved": true}', 7)

    ctx = _ctx()
    accepted = SQLModelSubmissionStore(engine).accept(
        ctx,
        idempotency_key=f"postgres-{starting_head or 'fresh'}",
        payload={"definition_id": "definition-1"},
    )
    event = SqlModelEventStore(engine).append(
        ctx,
        kind="run.accepted",
        payload={"submission_id": accepted.receipt.submission_id},
    )

    engine.dispose()
    restarted = postgres_engine_factory()
    receipt = SQLModelSubmissionStore(restarted).lookup_idempotency(
        ctx, f"postgres-{starting_head or 'fresh'}"
    )
    assert receipt is not None
    assert receipt.submission_id == accepted.receipt.submission_id
    replayed = SqlModelEventStore(restarted).list_after_cursor(ctx, None)
    assert [item.event_id for item in replayed] == [event.event_id]


def test_postgresql_concurrent_event_appends_allocate_ordered_sequences(
    postgres_engine_factory: Callable[[], Engine],
) -> None:
    engine = postgres_engine_factory()
    assert upgrade(engine) == "009_event_retention_tombstones_0_56"
    engine.dispose()

    ctx = _ctx()
    workers = 16
    barrier = Barrier(workers)

    def append(index: int):
        store = SqlModelEventStore(postgres_engine_factory())
        barrier.wait(timeout=30)
        return store.append(
            ctx,
            kind="run.accepted",
            payload={"index": index},
        )

    with ThreadPoolExecutor(max_workers=workers) as pool:
        events = list(pool.map(append, range(workers)))

    assert sorted(event.sequence for event in events) == list(range(1, workers + 1))
    assert len({event.event_id for event in events}) == workers
    assert len({event.cursor for event in events}) == workers

    replayed = SqlModelEventStore(postgres_engine_factory()).list_after_cursor(
        ctx, None, limit=workers
    )
    assert [event.sequence for event in replayed] == list(range(1, workers + 1))
    assert {event.payload["index"] for event in replayed} == set(range(workers))
    assert [(event.event_id, event.cursor) for event in replayed] == [
        (event.event_id, event.cursor)
        for event in sorted(events, key=lambda item: item.sequence)
    ]

    isolated = SqlModelEventStore(postgres_engine_factory()).append(
        _ctx("tenant-b", "workspace-b"),
        kind="run.accepted",
        payload={"index": 0},
    )
    assert isolated.sequence == 1
    assert isolated.cursor not in {event.cursor for event in events}


def test_postgresql_event_retention_expires_cursors_without_duplicate_delivery(
    postgres_engine_factory: Callable[[], Engine],
) -> None:
    engine = postgres_engine_factory()
    assert upgrade(engine) == "009_event_retention_tombstones_0_56"
    ctx = _ctx()
    events = SqlModelEventStore(engine)
    expired = events.append_once(
        ctx,
        event_key="attempt-start-retention",
        kind="run.started",
        payload={"run_id": "retention-run"},
    )
    events.append(ctx, kind="run.progress", payload={"run_id": "retention-run"})
    anchor = events.append(
        ctx, kind="run.completed", payload={"run_id": "retention-run"}
    )

    assert events.prune_before_sequence(ctx, before_sequence=3) == 2
    with pytest.raises(ControlPlaneError) as cursor_error:
        events.list_after_cursor(ctx, expired.cursor)
    assert cursor_error.value.status == 410
    with pytest.raises(ControlPlaneError) as duplicate_error:
        events.append_once(
            ctx,
            event_key="attempt-start-retention",
            kind="run.started",
            payload={"run_id": "retention-run"},
        )
    assert duplicate_error.value.status == 410

    appended = events.append(ctx, kind="run.recovered")
    assert appended.sequence == anchor.sequence + 1 == 4
    assert [item.event_id for item in events.list_after_cursor(ctx, None)] == [
        anchor.event_id,
        appended.event_id,
    ]
