"""CP1 SQLModel tables are owned by the versioned migration chain."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import inspect

pytest.importorskip("sqlmodel")
pytest.importorskip("etlantic_sqlmodel")

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
