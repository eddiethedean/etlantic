"""Live least-privilege PostgreSQL acceptance for the headless SQLModel backend."""

from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("sqlmodel")
pytest.importorskip("psycopg")
pytest.importorskip("etlantic_sqlmodel")

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Connection, Engine, ExecutionContext, make_url

from etlantic.control_plane import (
    ControlPlaneContext,
    EnvironmentRef,
    MemoryAuthorizer,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic_sqlmodel import (
    SQLModelBackendConfig,
    create_managed_backend,
    inspect_schema,
)
from etlantic_sqlmodel.migrations import VERSIONS, upgrade

pytestmark = pytest.mark.sqlmodel


def test_restricted_postgresql_role_inspects_schema_and_runs_headless_scheduler() -> (
    None
):
    url = os.environ.get("ETLANTIC_SQLMODEL_TEST_URL")
    if not url:
        pytest.skip("ETLANTIC_SQLMODEL_TEST_URL is not configured")

    schema = f"etlantic_057_{uuid4().hex}"
    role = f"etlantic_057_{uuid4().hex}"
    password = uuid4().hex
    admin_engine = create_engine(url, pool_pre_ping=True)
    database_name = admin_engine.url.database
    assert database_name is not None
    dialect = admin_engine.dialect.identifier_preparer
    quoted_schema = dialect.quote(schema)
    quoted_role = dialect.quote(role)
    quoted_database = dialect.quote(database_name)
    role_created = False
    backend = None
    runtime_engine: Engine | None = None
    try:
        with admin_engine.begin() as connection:
            connection.execute(text(f"CREATE SCHEMA {quoted_schema}"))
            connection.execute(
                text(f"CREATE ROLE {quoted_role} LOGIN PASSWORD '{password}'")
            )
            role_created = True

        operator_engine = create_engine(
            url,
            connect_args={"options": f"-csearch_path={schema}"},
        )
        try:
            assert upgrade(operator_engine) == VERSIONS[-1]
        finally:
            operator_engine.dispose()

        with admin_engine.begin() as connection:
            connection.execute(
                text(f"GRANT CONNECT ON DATABASE {quoted_database} TO {quoted_role}")
            )
            connection.execute(
                text(f"GRANT USAGE ON SCHEMA {quoted_schema} TO {quoted_role}")
            )
            connection.execute(
                text(
                    f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {quoted_schema} "
                    f"TO {quoted_role}"
                )
            )
            connection.execute(
                text(
                    f"GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA {quoted_schema} "
                    f"TO {quoted_role}"
                )
            )
            can_create = connection.execute(
                text("SELECT has_schema_privilege(:role, :schema, 'CREATE')"),
                {"role": role, "schema": schema},
            ).scalar_one()
        assert can_create is False

        runtime_url = make_url(url).set(username=role, password=password)
        runtime_engine = create_engine(
            runtime_url,
            connect_args={"options": f"-csearch_path={schema}"},
        )
        statements: list[str] = []
        commits: list[bool] = []

        def capture_statement(
            _conn: Connection,
            _cursor: Any,
            statement: str,
            _parameters: Any,
            _context: ExecutionContext,
            _many: bool,
        ) -> None:
            statements.append(statement.lstrip().split(None, 1)[0].upper())

        def capture_commit(_conn: Connection) -> None:
            commits.append(True)

        event.listen(runtime_engine, "before_cursor_execute", capture_statement)
        event.listen(runtime_engine, "commit", capture_commit)
        inspected = inspect_schema(runtime_engine)
        assert inspected.compatible
        backend = create_managed_backend(
            SQLModelBackendConfig(store_id=f"release-{uuid4().hex}"),
            authorizer=MemoryAuthorizer(),
            engine=runtime_engine,
        )
        event.remove(runtime_engine, "before_cursor_execute", capture_statement)
        event.remove(runtime_engine, "commit", capture_commit)
        assert not any(
            statement in {"CREATE", "ALTER", "INSERT", "UPDATE", "DELETE"}
            for statement in statements
        )
        assert not commits

        context = ControlPlaneContext(
            principal=Principal(subject="runtime", issuer="release-test"),
            tenant=TenantRef(tenant_id="release-tenant"),
            workspace=WorkspaceRef(
                tenant_id="release-tenant", workspace_id="release-workspace"
            ),
            environment=EnvironmentRef(name="release-test"),
            security_domain=SecurityDomain(domain_id="release-test"),
        )
        assert (
            backend.create_scheduler(owner_id=f"scheduler-{uuid4().hex}").tick(context)
            == 0
        )
        with runtime_engine.connect() as connection:
            assert connection.execute(text("SELECT 1")).scalar_one() == 1
        assert set(inspect(admin_engine).get_table_names(schema=schema))
    finally:
        if runtime_engine is not None:
            if backend is not None:
                backend.close()
            runtime_engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f"DROP SCHEMA IF EXISTS {quoted_schema} CASCADE"))
            if role_created:
                connection.execute(text(f"DROP OWNED BY {quoted_role}"))
            connection.execute(text(f"DROP ROLE IF EXISTS {quoted_role}"))
        admin_engine.dispose()
