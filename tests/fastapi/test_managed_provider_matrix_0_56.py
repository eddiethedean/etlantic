"""Managed-worker source/destination qualification for phase 0.56.

Foundry endpoints in this matrix are independent Semblance-backed loopback
simulators. PostgreSQL cases require a disposable database supplied through
``ETLANTIC_SQL_TEST_URL``.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("sqlmodel")
pytest.importorskip("etlantic_sqlmodel")
pytest.importorskip("fastapi")
pytest.importorskip("httpx2")
pytest.importorskip("semblance")

import sqlalchemy
from etlantic_foundry.connectors import FoundrySinkConnector, FoundrySourceConnector
from sqlalchemy import text
from tests.foundry.simulator import FoundrySimulator

from etlantic import Data, Extract, Load, Pipeline, Profile
from etlantic.authoring import definition_from_pipeline
from etlantic.authoring.serialize import pipeline_to_dict
from etlantic.connectors.local_files import LocalFilesSourceConnector
from etlantic.control_plane import (
    ControlPlaneContext,
    EnvironmentRef,
    MemoryAuthorizer,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.registry import BindingDescriptor, PlanningContext
from etlantic.runtime.managed_execution import ManagedExecutionAdapter
from etlantic.runtime.state import RunStatus
from etlantic.secrets import SecretRef
from etlantic.secrets.provider import SecretResolutionContext
from etlantic_fastapi import (
    ManagedBackendConfig,
    create_managed_backend,
    static_context_factory,
)
from etlantic_sql.live_postgresql import (
    LivePostgresSinkConnector,
    LivePostgresSourceConnector,
)
from etlantic_sqlmodel.migrations import upgrade

POSTGRES_URL = os.environ.get("ETLANTIC_SQL_TEST_URL")
EVIDENCE_PATH = os.environ.get("ETLANTIC_PHASE056_MATRIX_EVIDENCE")
pytestmark = pytest.mark.skipif(
    not POSTGRES_URL, reason="requires an isolated PostgreSQL 16 test database"
)


class _TransferRow(Data):
    id: str
    payload: str


class _TransferPipeline(Pipeline):
    source: Extract[_TransferRow] = Extract(asset="source")
    sink: Load[_TransferRow] = Load(input=source, asset="sink")


class _AllowMatrixSecrets:
    """Explicit worker authorization for the matrix's isolated credentials."""

    async def authorize_late_binding(
        self, reference: SecretRef, context: SecretResolutionContext
    ) -> bool:
        return context.trusted_scope is not None and reference.name.startswith(
            "ETLANTIC_PHASE056_"
        )


def _package_version(distribution: str) -> str:
    return importlib.metadata.version(distribution)


def _write_matrix_evidence() -> Iterator[list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    yield records
    if EVIDENCE_PATH is None:
        return
    assert len(records) == len(_matrix_cases()), (
        f"evidence has {len(records)} cases; expected {len(_matrix_cases())}"
    )
    assert all(
        row["success_status"] == RunStatus.SUCCEEDED.value
        and row["failure_status"] == RunStatus.FAILED.value
        and row["target_unchanged_after_failure"] is True
        for row in records
    )
    evidence_path = Path(EVIDENCE_PATH)
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(
        json.dumps(
            {
                "schema": "etlantic.phase_0_56.managed_provider_matrix/1",
                "criterion": "AC056-036",
                "created_at_utc": datetime.now(UTC).isoformat(),
                "provider_versions": {
                    "etlantic": _package_version("etlantic"),
                    "etlantic_sql": _package_version("etlantic-sql"),
                    "etlantic_foundry": _package_version("etlantic-foundry"),
                    "semblance": _package_version("semblance"),
                },
                "cases": sorted(
                    records,
                    key=lambda row: (
                        row["source_kind"],
                        row["destination_kind"],
                        row["destination_mode"],
                    ),
                ),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


_matrix_evidence_records = pytest.fixture(scope="session")(_write_matrix_evidence)


def _context() -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal("phase056-provider-matrix"),
        tenant=TenantRef("phase056-provider-matrix"),
        workspace=WorkspaceRef("phase056-provider-matrix", "qualification"),
        environment=EnvironmentRef("test"),
        security_domain=SecurityDomain("phase056-provider-matrix"),
    )


def _matrix_cases() -> list[tuple[str, str, str]]:
    cases: list[tuple[str, str, str]] = []
    for source in ("foundry_a", "foundry_b", "postgresql", "csv"):
        for destination in ("foundry_a", "foundry_b"):
            cases.append((source, destination, "replace"))
        for mode in ("append", "upsert", "replace"):
            cases.append((source, "postgresql", mode))
    return cases


@pytest.mark.parametrize(
    ("source_kind", "destination_kind", "destination_mode"),
    _matrix_cases(),
    ids=lambda value: str(value),
)
def test_managed_worker_executes_required_provider_pairing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    source_kind: str,
    destination_kind: str,
    destination_mode: str,
    _matrix_evidence_records: list[dict[str, Any]],
) -> None:
    assert POSTGRES_URL is not None
    case_id = (
        f"{source_kind}-{destination_kind}-{destination_mode}-{uuid.uuid4().hex[:8]}"
    )
    source_id = f"source-{uuid.uuid4().hex[:10]}"
    expected_payload = f"payload-{case_id}"
    source_table = f"etlantic_p056_{uuid.uuid4().hex[:12]}"
    target_table = f"etlantic_p056_{uuid.uuid4().hex[:12]}"
    effects_table = f"etlantic_p056_fx_{uuid.uuid4().hex[:10]}"
    pg_engine = sqlalchemy.create_engine(POSTGRES_URL, hide_parameters=True)
    postgres_url = sqlalchemy.engine.make_url(POSTGRES_URL)
    postgres_identity = {
        "host": postgres_url.host,
        "port": postgres_url.port,
        "database": postgres_url.database,
    }
    with pg_engine.connect() as connection:
        postgres_version = str(
            connection.execute(text("SHOW server_version")).scalar_one()
        )
    with pg_engine.begin() as connection:
        connection.execute(
            text(
                f'CREATE TABLE public."{source_table}" '
                "(id text PRIMARY KEY, payload text NOT NULL)"
            )
        )
        connection.execute(
            text(
                f'CREATE TABLE public."{target_table}" '
                "(id text PRIMARY KEY, payload text NOT NULL)"
            )
        )
        connection.execute(
            text(
                f'CREATE TABLE public."{effects_table}" ('
                "effect_id text PRIMARY KEY, intent_fingerprint text NOT NULL, "
                "publication_id text NOT NULL UNIQUE, row_count bigint NOT NULL, "
                "committed_at timestamptz NOT NULL DEFAULT now())"
            )
        )
        if source_kind == "postgresql":
            connection.execute(
                text(f'INSERT INTO public."{source_table}" VALUES (:id, :payload)'),
                {"id": source_id, "payload": expected_payload},
            )
        if destination_kind == "postgresql" and destination_mode == "upsert":
            connection.execute(
                text(f'INSERT INTO public."{target_table}" VALUES (:id, :payload)'),
                {"id": source_id, "payload": "stale-value"},
            )

    def cleanup_postgresql_case() -> None:
        try:
            with pg_engine.begin() as connection:
                connection.execute(
                    text(f'DROP TABLE IF EXISTS public."{source_table}"')
                )
                connection.execute(
                    text(f'DROP TABLE IF EXISTS public."{target_table}"')
                )
                connection.execute(
                    text(f'DROP TABLE IF EXISTS public."{effects_table}"')
                )
        finally:
            pg_engine.dispose()

    request.addfinalizer(cleanup_postgresql_case)

    token_a = f"phase056-foundry-a-{uuid.uuid4().hex}"
    token_b = f"phase056-foundry-b-{uuid.uuid4().hex}"
    dataset_a = f"ri.foundry.main.dataset.phase056.{uuid.uuid4().hex[:12]}"
    dataset_b = f"ri.foundry.main.dataset.phase056.{uuid.uuid4().hex[:12]}"
    tx_a = f"ri.foundry.main.transaction.phase056-a-{uuid.uuid4().hex[:8]}"
    tx_b = f"ri.foundry.main.transaction.phase056-b-{uuid.uuid4().hex[:8]}"
    seeded = {
        "seed/input.csv": f"id,payload\n{source_id},{expected_payload}\n".encode()
    }
    simulator_a = FoundrySimulator(
        token=token_a,
        dataset_rid=dataset_a,
        pinned_transaction=tx_a,
        namespace="phase056-a",
        seed_files=seeded,
    )
    simulator_b = FoundrySimulator(
        token=token_b,
        dataset_rid=dataset_b,
        pinned_transaction=tx_b,
        namespace="phase056-b",
        seed_files=seeded,
    )
    monkeypatch.setenv("ETLANTIC_PHASE056_FOUNDRY_A", token_a)
    monkeypatch.setenv("ETLANTIC_PHASE056_FOUNDRY_B", token_b)
    monkeypatch.setenv("ETLANTIC_PHASE056_POSTGRES_URL", POSTGRES_URL)

    with simulator_a.serve() as url_a, simulator_b.serve() as url_b:
        endpoints = {
            "foundry_a": (url_a, dataset_a, tx_a, "ETLANTIC_PHASE056_FOUNDRY_A"),
            "foundry_b": (url_b, dataset_b, tx_b, "ETLANTIC_PHASE056_FOUNDRY_B"),
        }
        ctx = _context()
        profile = Profile(
            name="phase056-provider-matrix",
            security_mode="development",
            plugin_allowlist={"etlantic": None},
        )
        csv_reference: dict[str, Any] | None = None

        def planning_context_factory(
            _ctx: ControlPlaneContext, effective_profile: Profile
        ) -> PlanningContext:
            planning = PlanningContext.create(profile=effective_profile)
            if source_kind in endpoints:
                source_url, dataset, transaction, token_name = endpoints[source_kind]
                source_descriptor = BindingDescriptor(
                    binding="source",
                    provider="foundry",
                    kind="source",
                    format="csv",
                    secret_ref=SecretRef(provider="env", name=token_name, key="value"),
                    config={
                        "base_url": source_url,
                        "dataset_rid": dataset,
                        "branch_name": "main",
                        "transaction_rid": transaction,
                        "path_prefix": "seed/",
                        "format": "csv",
                    },
                )
            elif source_kind == "postgresql":
                source_descriptor = BindingDescriptor(
                    binding="source",
                    provider="postgresql",
                    kind="source",
                    location=source_table,
                    secret_ref=SecretRef(
                        provider="env",
                        name="ETLANTIC_PHASE056_POSTGRES_URL",
                        key="value",
                    ),
                    config={"schema": "public", "mode": "snapshot"},
                )
            else:
                assert csv_reference is not None
                source_descriptor = BindingDescriptor(
                    binding="source",
                    provider="local-files",
                    kind="source",
                    format="csv",
                    config={"input_resource": csv_reference},
                )
            planning.registry.register_binding(source_descriptor)

            if destination_kind in endpoints:
                target_url, dataset, _transaction, token_name = endpoints[
                    destination_kind
                ]
                destination_descriptor = BindingDescriptor(
                    binding="sink",
                    provider="foundry",
                    kind="sink",
                    format="csv",
                    mode="replace",
                    secret_ref=SecretRef(provider="env", name=token_name, key="value"),
                    config={
                        "base_url": target_url,
                        "dataset_rid": dataset,
                        "branch_name": "main",
                        "mode": "replace",
                        "file_path": f"managed-output/{case_id}.csv",
                        "format": "csv",
                    },
                )
            else:
                config: dict[str, Any] = {
                    "schema": "public",
                    "mode": destination_mode,
                    "effect_table": f"public.{effects_table}",
                }
                if destination_mode == "upsert":
                    config["key_columns"] = ["id"]
                destination_descriptor = BindingDescriptor(
                    binding="sink",
                    provider="postgresql",
                    kind="sink",
                    location=target_table,
                    secret_ref=SecretRef(
                        provider="env",
                        name="ETLANTIC_PHASE056_POSTGRES_URL",
                        key="value",
                    ),
                    config=config,
                )
            planning.registry.register_binding(destination_descriptor)
            return planning

        sqlite_url = f"sqlite:///{tmp_path / 'managed.sqlite'}"
        sqlite_engine = sqlalchemy.create_engine(sqlite_url)
        try:
            upgrade(sqlite_engine)
        finally:
            sqlite_engine.dispose()
        authorizer = MemoryAuthorizer()
        for action in (
            "definition.write",
            "run.submit",
            "run.read",
            "run.report",
            "input.read",
        ):
            authorizer.grant(ctx, action)
        backend = create_managed_backend(
            ManagedBackendConfig(
                database_url=sqlite_url,
                store_id=f"phase056-provider-{case_id}",
                profile=profile,
                artifact_root=str(tmp_path / "artifacts"),
            ),
            authorizer=authorizer,
            context_factory=static_context_factory(
                tenant_id=ctx.tenant.tenant_id,
                workspace_id=ctx.workspace.workspace_id,
                environment=ctx.environment.name,
                security_domain=ctx.security_domain.domain_id,
            ),
            planning_context_factory=planning_context_factory,
        )
        try:
            if source_kind == "csv":
                content = f"id,payload\n{source_id},{expected_payload}\n".encode()
                staged = backend.input_resources.stage(
                    ctx,
                    content,
                    media_type="text/csv",
                    format="csv",
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
                reference = backend.input_resources.finalize(
                    ctx,
                    staged.upload_id,
                    expected_sha256=hashlib.sha256(content).hexdigest(),
                    expected_byte_length=len(content),
                )
                csv_reference = reference.to_dict()

            service = backend.api.managed_service
            assert service is not None
            service.register_definition(
                ctx,
                "provider-matrix-transfer",
                pipeline_to_dict(definition_from_pipeline(_TransferPipeline)),
            )
            receipt = service.submit_run(
                ctx,
                "provider-matrix-transfer",
                idempotency_key=case_id,
            )
            host = backend.create_execution_host(owner_id=f"worker-{case_id}")
            adapter = cast(ManagedExecutionAdapter, host.runner)
            adapter.secret_alias_authorizer = _AllowMatrixSecrets()
            destination_simulator: FoundrySimulator | None = None
            output_path = f"managed-output/{case_id}.csv"
            if destination_kind in {"foundry_a", "foundry_b"}:
                destination_simulator = (
                    simulator_a if destination_kind == "foundry_a" else simulator_b
                )

            def runtime_factory() -> PipelineRuntime:
                runtime = PipelineRuntime()
                runtime.register_source_connector("foundry", FoundrySourceConnector())
                runtime.register_sink_connector("foundry", FoundrySinkConnector())
                runtime.register_source_connector(
                    "postgresql", LivePostgresSourceConnector()
                )
                runtime.register_sink_connector(
                    "postgresql", LivePostgresSinkConnector()
                )
                runtime.register_source_connector(
                    "local-files", LocalFilesSourceConnector()
                )
                return runtime

            adapter.runtime_factory = runtime_factory
            assert host.tick(ctx) == 1
            report = service.get_run_report(ctx, str(receipt.resource_id))
            assert report["status"] == RunStatus.SUCCEEDED.value, report

            if destination_kind == "postgresql":
                with pg_engine.connect() as connection:
                    rows = connection.execute(
                        text(f'SELECT id, payload FROM public."{target_table}"')
                    ).all()
                    effect_receipt = connection.execute(
                        text(
                            f"SELECT effect_id, publication_id, row_count "
                            f'FROM public."{effects_table}"'
                        )
                    ).one()
                assert rows == [(source_id, expected_payload)]
                successful_target_snapshot: object = rows
                success_effect: dict[str, Any] = {
                    "provider": "postgresql",
                    "effect_id": str(effect_receipt.effect_id),
                    "publication_id": str(effect_receipt.publication_id),
                    "row_count": int(effect_receipt.row_count),
                }
            else:
                assert destination_simulator is not None
                published = destination_simulator.files[("main", output_path)].content
                assert published == (
                    f"id,payload\n{source_id},{expected_payload}\n".encode()
                )
                successful_target_snapshot = published
                published_file = destination_simulator.files[("main", output_path)]
                success_effect = {
                    "provider": "foundry",
                    "dataset_rid": destination_simulator.dataset_rid,
                    "branch": published_file.branch_name,
                    "transaction_rid": published_file.transaction_rid,
                    "path": output_path,
                    "sha256": hashlib.sha256(published).hexdigest(),
                    "byte_length": len(published),
                }

            # Each pairing/mode also records an actual source-provider failure
            # through the same managed worker and verifies that the target is
            # untouched. The immutable CSV case tampers only after acceptance.
            failed_receipt = service.submit_run(
                ctx,
                "provider-matrix-transfer",
                idempotency_key=f"{case_id}-source-failure",
            )
            if source_kind in endpoints:
                source_simulator = (
                    simulator_a if source_kind == "foundry_a" else simulator_b
                )
                source_simulator.files.pop(("main", "seed/input.csv"))
            elif source_kind == "postgresql":
                with pg_engine.begin() as connection:
                    connection.execute(text(f'DROP TABLE public."{source_table}"'))
            else:
                assert csv_reference is not None
                resource_id = str(csv_reference["resource_id"])
                tampered = f"id,payload\n{source_id},tampered-value\n".encode()
                with backend.engine.begin() as connection:
                    connection.execute(
                        text(
                            "UPDATE cp_input_uploads SET content = :content "
                            "WHERE upload_id = :upload_id"
                        ),
                        {"content": tampered, "upload_id": resource_id},
                    )

            assert host.tick(ctx) == 1
            failed_report = service.get_run_report(ctx, str(failed_receipt.resource_id))
            assert failed_report["status"] == RunStatus.FAILED.value, failed_report
            diagnostics = cast(list[Any], failed_report.get("diagnostics") or [])
            assert diagnostics
            expected_prefix = (
                "PMFND" if source_kind.startswith("foundry_") else "PMCONN"
            )
            assert any(
                str(cast(dict[str, Any], item).get("code", "")).startswith(
                    expected_prefix
                )
                for item in diagnostics
                if isinstance(item, dict)
            )
            assert token_a not in str(failed_report)
            assert token_b not in str(failed_report)
            failure_codes = sorted(
                {
                    str(cast(dict[str, Any], item).get("code", ""))
                    for item in diagnostics
                    if isinstance(item, dict) and cast(dict[str, Any], item).get("code")
                }
            )

            if destination_kind == "postgresql":
                with pg_engine.connect() as connection:
                    unchanged = connection.execute(
                        text(f'SELECT id, payload FROM public."{target_table}"')
                    ).all()
                assert unchanged == successful_target_snapshot
            else:
                assert destination_simulator is not None
                assert destination_simulator.files[("main", output_path)].content == (
                    successful_target_snapshot
                )

            if source_kind in endpoints:
                source_url, source_dataset, source_transaction, _token_name = endpoints[
                    source_kind
                ]
                source_identity: dict[str, Any] = {
                    "provider": "foundry",
                    "base_url": source_url,
                    "dataset_rid": source_dataset,
                    "branch": "main",
                    "transaction_rid": source_transaction,
                    "path": "seed/input.csv",
                }
            elif source_kind == "postgresql":
                source_identity = {
                    "provider": "postgresql",
                    "schema": "public",
                    "table": source_table,
                }
            else:
                assert csv_reference is not None
                source_identity = {
                    "provider": "immutable_csv_upload",
                    "resource_id": csv_reference["resource_id"],
                    "version": csv_reference["version"],
                    "sha256": csv_reference["sha256"],
                    "byte_length": csv_reference["byte_length"],
                    "media_type": csv_reference["media_type"],
                    "format": csv_reference["format"],
                }

            if destination_kind in endpoints:
                destination_url, destination_dataset, _tx, _token_name = endpoints[
                    destination_kind
                ]
                destination_identity: dict[str, Any] = {
                    "provider": "foundry",
                    "base_url": destination_url,
                    "dataset_rid": destination_dataset,
                    "branch": "main",
                    "path": output_path,
                    "mode": destination_mode,
                }
            else:
                destination_identity = {
                    "provider": "postgresql",
                    "host": postgres_identity["host"],
                    "port": postgres_identity["port"],
                    "database": postgres_identity["database"],
                    "schema": "public",
                    "table": target_table,
                    "effect_table": effects_table,
                    "mode": destination_mode,
                }

            _matrix_evidence_records.append(
                {
                    "source_kind": source_kind,
                    "destination_kind": destination_kind,
                    "destination_mode": destination_mode,
                    "postgresql": {
                        **postgres_identity,
                        "server_version": postgres_version,
                    },
                    "foundry_simulator_scopes": [
                        {
                            "namespace": simulator.namespace,
                            "dataset_rid": simulator.dataset_rid,
                            "pinned_transaction_rid": simulator.pinned_transaction,
                        }
                        for simulator in (simulator_a, simulator_b)
                    ],
                    "accepted_success_run_id": str(receipt.resource_id),
                    "success_status": RunStatus.SUCCEEDED.value,
                    "source_identity": source_identity,
                    "destination_identity": destination_identity,
                    "success_effect": success_effect,
                    "accepted_failure_run_id": str(failed_receipt.resource_id),
                    "failure_status": RunStatus.FAILED.value,
                    "failure_diagnostic_codes": failure_codes,
                    "target_unchanged_after_failure": True,
                    "report_contains_no_foundry_credentials": True,
                }
            )
        finally:
            backend.close()
