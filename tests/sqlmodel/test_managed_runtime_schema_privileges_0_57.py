"""Live least-privilege PostgreSQL acceptance for the headless SQLModel backend."""

from __future__ import annotations

import asyncio
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
    pytest.importorskip("prefect")
    pytest.importorskip("etlantic_prefect")

    from prefect.client.orchestration import get_client
    from prefect.client.schemas.actions import WorkPoolCreate
    from prefect.testing.utilities import prefect_test_harness

    from etlantic import Data, Extract, Load, Pipeline
    from etlantic.authoring import definition_from_pipeline
    from etlantic.authoring.serialize import pipeline_to_dict

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
        spec_name = f"restricted-{uuid4().hex[:12]}"
        from etlantic_prefect import (
            ManagedDeploymentSpec,
            PrefectDeploymentRegistrar,
            PrefectDispatcher,
        )

        spec = ManagedDeploymentSpec.from_current_runtime(
            name=spec_name,
            work_pool_name=f"pool-{spec_name}",
            worker_backend_entry_point="phase058_test_backend",
            lockfile_sha256="a" * 64,
        )

        async def register_deployment():
            async with get_client() as client:
                await client.create_work_pool(
                    WorkPoolCreate(name=spec.work_pool_name, type="process")
                )
            registrar = PrefectDeploymentRegistrar()
            preview = await registrar.preview(spec)
            return await registrar.register(
                spec, expected_fingerprint=preview["spec"]["fingerprint"]
            )

        with prefect_test_harness():
            binding = asyncio.run(register_deployment())
            authz = MemoryAuthorizer()
            context = ControlPlaneContext(
                principal=Principal(subject="runtime", issuer="release-test"),
                tenant=TenantRef(tenant_id="release-tenant"),
                workspace=WorkspaceRef(
                    tenant_id="release-tenant", workspace_id="release-workspace"
                ),
                environment=EnvironmentRef(name="release-test"),
                security_domain=SecurityDomain(domain_id="release-test"),
            )
            for action in (
                "definition.write",
                "definition.read",
                "definition.validate",
                "definition.plan",
                "run.submit",
                "run.read",
                "run.cancel",
                "schedule.write",
            ):
                authz.grant(context, action)
            backend = create_managed_backend(
                SQLModelBackendConfig(
                    store_id=f"release-{uuid4().hex}",
                    execution_route=binding.execution_route,
                ),
                authorizer=authz,
                engine=runtime_engine,
            )
            event.remove(runtime_engine, "before_cursor_execute", capture_statement)
            event.remove(runtime_engine, "commit", capture_commit)
            assert not any(
                statement in {"CREATE", "ALTER", "INSERT", "UPDATE", "DELETE"}
                for statement in statements
            )
            assert not commits

            assert (
                backend.create_scheduler(owner_id=f"scheduler-{uuid4().hex}").tick(
                    context
                )
                == 0
            )

            class RestrictedRow(Data):
                value: int

            class RestrictedPipeline(Pipeline):
                source: Extract[RestrictedRow] = Extract(asset="source")
                output: Load[RestrictedRow] = Load(input=source, asset="output")

            backend.managed_service.register_definition(
                context,
                "restricted-phase058",
                pipeline_to_dict(definition_from_pipeline(RestrictedPipeline)),
            )
            accepted = backend.managed_service.submit_run(
                context,
                "restricted-phase058",
                idempotency_key=f"restricted-route-{uuid4().hex}",
            )
            stored = backend.durable_work.get_submission(
                context, accepted.submission_id
            )
            assert stored.execution_route == binding.execution_route
            dispatcher = PrefectDispatcher(
                backend=backend,
                context=context,
                binding=binding,
                owner_id=f"restricted-dispatcher-{uuid4().hex}",
            )
            dispatched = asyncio.run(dispatcher.tick(limit=10))
            assert len(dispatched) == 1
            assert dispatched[0]["status"] == "dispatched"
            assert dispatched[0]["submission_id"] == accepted.submission_id
            flow_run_id = dispatched[0]["prefect_flow_run_id"]
            assert flow_run_id
            stored_dispatch = backend.durable_work.get_dispatch(
                context, accepted.submission_id
            )
            assert stored_dispatch.status == "dispatched"
            assert stored_dispatch.prefect_flow_run_id == flow_run_id

            async def read_remote_flow_run():
                async with get_client() as client:
                    return await client.read_flow_run(flow_run_id)

            remote_flow_run = asyncio.run(read_remote_flow_run())
            assert str(remote_flow_run.deployment_id) == str(binding.deployment_id)
            with runtime_engine.connect() as connection:
                assert connection.execute(text("SELECT 1")).scalar_one() == 1
            with admin_engine.connect() as connection:
                assert (
                    connection.execute(
                        text("SELECT has_schema_privilege(:role, :schema, 'CREATE')"),
                        {"role": role, "schema": schema},
                    ).scalar_one()
                    is False
                )
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
