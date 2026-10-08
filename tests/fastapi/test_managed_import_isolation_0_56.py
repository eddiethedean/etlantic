"""Gateway imports and managed startup stay outside worker execution modules."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("sqlmodel")
pytest.importorskip("etlantic_fastapi")
pytest.importorskip("etlantic_sqlmodel")


def test_fastapi_gateway_import_and_construction_are_worker_isolated() -> None:
    script = r"""
import sys
import tempfile
from pathlib import Path

import etlantic_fastapi

def execution_modules():
    return sorted(
        name for name in sys.modules
        if name in {
            "etlantic.runtime.execute",
            "etlantic.runtime.action_execution_host",
        }
    )

assert not execution_modules(), execution_modules()

from etlantic.control_plane import MemoryAuthorizer
from etlantic_fastapi import (
    ManagedBackendConfig,
    create_managed_app,
    static_context_factory,
)
from etlantic_sqlmodel import create_sqlite_engine, upgrade

with tempfile.TemporaryDirectory() as temp:
    database = Path(temp) / "gateway.sqlite"
    operator_engine = create_sqlite_engine(f"sqlite:///{database}")
    upgrade(operator_engine)
    operator_engine.dispose()

    app = create_managed_app(
        ManagedBackendConfig(database_url=f"sqlite:///{database}"),
        authorizer=MemoryAuthorizer(),
        context_factory=static_context_factory(
            tenant_id="gateway-test",
            workspace_id="gateway-test",
            environment="test",
            security_domain="gateway-test",
        ),
    )
    assert app.state.managed_backend is not None
    assert not execution_modules(), execution_modules()
    app.state.managed_backend.close()
"""
    root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    plugin_source = str(root / "packages/etlantic-fastapi/src")
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = os.pathsep.join(
        path for path in (plugin_source, existing_pythonpath) if path
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_managed_backend_constructs_with_existing_schema_without_create_privilege() -> (
    None
):
    url = os.environ.get("ETLANTIC_SQLMODEL_TEST_URL")
    if not url:
        pytest.skip("set ETLANTIC_SQLMODEL_TEST_URL for live PostgreSQL startup")

    import sqlalchemy
    from sqlalchemy import inspect, text
    from sqlalchemy.engine import make_url

    from etlantic.control_plane import MemoryAuthorizer
    from etlantic_fastapi import (
        ManagedBackendConfig,
        create_managed_backend,
        static_context_factory,
    )
    from etlantic_sqlmodel.migrations import current_version, upgrade

    schema = f"etlantic_runtime_{uuid4().hex}"
    role = f"etlantic_runtime_{uuid4().hex}"
    password = uuid4().hex
    quoted_schema = f'"{schema}"'
    quoted_role = f'"{role}"'
    admin_engine = sqlalchemy.create_engine(url, pool_pre_ping=True)
    database_name = admin_engine.url.database
    assert database_name is not None
    quoted_database = admin_engine.dialect.identifier_preparer.quote(database_name)
    backend = None
    role_created = False
    try:
        with admin_engine.begin() as connection:
            connection.execute(text(f"CREATE SCHEMA {quoted_schema}"))
            connection.execute(
                text(f"CREATE ROLE {quoted_role} LOGIN PASSWORD '{password}'")
            )
            role_created = True
        operator_engine = sqlalchemy.create_engine(
            url,
            connect_args={"options": f"-csearch_path={schema}"},
        )
        try:
            assert (
                upgrade(operator_engine)
                == "014_cp1_complete_principal_idempotency_0_56"
            )
            assert (
                current_version(operator_engine)
                == "014_cp1_complete_principal_idempotency_0_56"
            )
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
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA "
                    f"{schema} TO {quoted_role}"
                )
            )
            connection.execute(
                text(
                    "GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA "
                    f"{schema} TO {quoted_role}"
                )
            )
            can_create = connection.execute(
                text("SELECT has_schema_privilege(:role, :schema, 'CREATE')"),
                {"role": role, "schema": schema},
            ).scalar_one()
        assert can_create is False

        tables_before = set(inspect(admin_engine).get_table_names(schema=schema))
        runtime_url = make_url(url).set(username=role, password=password)
        backend = create_managed_backend(
            ManagedBackendConfig(
                database_url=runtime_url.render_as_string(hide_password=False),
                engine_options={"connect_args": {"options": f"-csearch_path={schema}"}},
            ),
            authorizer=MemoryAuthorizer(),
            context_factory=static_context_factory(
                tenant_id="least-privilege-test",
                workspace_id="least-privilege-test",
                environment="test",
                security_domain="least-privilege-test",
            ),
        )
        assert backend is not None
        assert (
            set(inspect(admin_engine).get_table_names(schema=schema)) == tables_before
        )
    finally:
        if backend is not None:
            backend.close()
        with admin_engine.begin() as connection:
            connection.execute(text(f"DROP SCHEMA IF EXISTS {quoted_schema} CASCADE"))
            if role_created:
                connection.execute(text(f"DROP OWNED BY {quoted_role}"))
            connection.execute(text(f"DROP ROLE IF EXISTS {quoted_role}"))
        admin_engine.dispose()
