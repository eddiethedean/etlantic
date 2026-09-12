"""CP1 SQLModel tables are owned by the versioned migration chain."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

pytest.importorskip("sqlmodel")
pytest.importorskip("etlantic_sqlmodel")

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.schema import CreateSchema, DropSchema

from etlantic.control_plane import (
    ControlPlaneContext,
    EnvironmentRef,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic_sqlmodel.control_plane import (
    SQLModelDefinitionRepository,
    SqlModelEventStore,
    SQLModelSubmissionStore,
    create_sqlite_engine,
)
from etlantic_sqlmodel.migrations import (
    VERSIONS,
    apply_migrations,
    current_version,
    upgrade,
)

pytestmark = pytest.mark.sqlmodel


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


def _ctx() -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(subject="alice"),
        tenant=TenantRef(tenant_id="tenant-a"),
        workspace=WorkspaceRef(tenant_id="tenant-a", workspace_id="workspace-a"),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id="default"),
    )


def test_latest_migration_provisions_all_cp1_store_tables(tmp_path: Path) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'cp1.db'}")

    assert apply_migrations(engine) == "005_cp1_reference"
    assert current_version(engine) == "005_cp1_reference"
    assert {
        "cp_definitions",
        "cp_submissions",
        "cp_events",
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
def test_upgrade_from_published_head_adds_cp1_tables_without_replacing_existing_schema(
    tmp_path: Path,
    previous_head: str,
) -> None:
    engine = create_sqlite_engine(
        f"sqlite:///{tmp_path / previous_head.replace('/', '_')}.db"
    )

    assert upgrade(engine, target=previous_head) == previous_head
    before = set(inspect(engine).get_table_names())
    assert "cp_events" not in before

    assert upgrade(engine) == "005_cp1_reference"
    tables = set(inspect(engine).get_table_names())
    assert before.issubset(tables)
    assert {
        "cp_definitions",
        "cp_submissions",
        "cp_events",
    }.issubset(tables)


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

    assert upgrade(engine) == "005_cp1_reference"
    assert current_version(engine) == "005_cp1_reference"
    tables = set(inspect(engine).get_table_names())
    assert {
        "cp_definitions",
        "cp_submissions",
        "cp_events",
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
    assert upgrade(engine) == "005_cp1_reference"
    engine.dispose()

    ctx = _ctx()
    workers = 16
    barrier = Barrier(workers)

    def append(index: int):
        barrier.wait(timeout=30)
        return SqlModelEventStore(postgres_engine_factory()).append(
            ctx,
            kind="run.accepted",
            payload={"index": index},
        )

    with ThreadPoolExecutor(max_workers=workers) as pool:
        events = list(pool.map(append, range(workers)))

    assert sorted(event.sequence for event in events) == list(range(1, workers + 1))
    assert len({event.event_id for event in events}) == workers

    replayed = SqlModelEventStore(postgres_engine_factory()).list_after_cursor(
        ctx, None, limit=workers
    )
    assert [event.sequence for event in replayed] == list(range(1, workers + 1))
    assert {event.payload["index"] for event in replayed} == set(range(workers))
