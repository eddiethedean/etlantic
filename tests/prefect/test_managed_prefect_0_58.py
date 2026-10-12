# pyright: reportArgumentType=false, reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnusedFunction=false
"""Managed Prefect contracts for phase 0.58."""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from collections.abc import Callable, Generator
from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from multiprocessing import get_context
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace
from typing import Any, Protocol, cast
from uuid import UUID, uuid4

import pytest

os.environ.setdefault("PREFECT_SERVER_ANALYTICS_ENABLED", "false")
os.environ.setdefault("PREFECT_LOGGING_TO_API_ENABLED", "false")
os.environ.setdefault("PREFECT_LOGGING_LEVEL", "ERROR")

pytest.importorskip("prefect")

from etlantic import Data, Extract, Input, Load, Output, Pipeline, Transformation
from etlantic.authoring import definition_from_pipeline
from etlantic.authoring.serialize import pipeline_to_dict
from etlantic.control_plane import (
    ControlPlaneContext,
    DispatchRecord,
    EnvironmentRef,
    ExecutionEnvelope,
    ExecutionRouteLifecycle,
    ManagedBackend,
    MemoryAuthorizer,
    MemoryDefinitionRepository,
    MemoryDurableWorkStore,
    MemoryEventStore,
    MemorySubmissionStore,
    Principal,
    ScheduleSpec,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.schedule_memory import MemoryScheduleStore
from etlantic.service import ManagedApplicationService, ScheduleApplicationService
from etlantic_prefect import (
    ManagedDeploymentBinding,
    ManagedDeploymentSpec,
    ManagedExecutionReference,
    PrefectDeploymentRegistrar,
    PrefectDispatcher,
)

pytestmark = pytest.mark.prefect


class _InstalledWorkerBackendFixture(Protocol):
    def build_backend(self) -> tuple[ManagedBackend, ControlPlaneContext]: ...

    def restore_test_execution_host_factory(self) -> None: ...


class _Row(Data):
    value: int


class _Copy(Transformation):
    rows: Input[_Row]
    result: Output[_Row]


@_Copy.implementation("local")
def _copy_rows(rows: list[_Row]) -> list[_Row]:
    return list(rows)


class _ManagedPipeline(Pipeline):
    raw: Extract[_Row] = Extract(asset="rows")
    copied = _Copy.step(rows=raw)
    output: Load[_Row] = Load(input=copied.result, asset="output")


class _ProcessWorkerRow(Data):
    id: str
    payload: str


class _ProcessWorkerPipeline(Pipeline):
    source: Extract[_ProcessWorkerRow] = Extract(asset="source")
    output: Load[_ProcessWorkerRow] = Load(input=source, asset="output")


def _context() -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(subject="phase-058", issuer="tests"),
        tenant=TenantRef(tenant_id="tenant-058"),
        workspace=WorkspaceRef(tenant_id="tenant-058", workspace_id="workspace-058"),
        environment=EnvironmentRef(name="test"),
        security_domain=SecurityDomain(domain_id="default"),
    )


def _managed_service(
    tmp_path: Path, *, execution_route: str = "local"
) -> tuple[
    ControlPlaneContext,
    MemoryAuthorizer,
    MemoryDurableWorkStore,
    ManagedApplicationService,
]:
    ctx = _context()
    authz = MemoryAuthorizer()
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
        authz.grant(ctx, action)
    durable = MemoryDurableWorkStore()
    service = ManagedApplicationService(
        authorizer=authz,
        definitions=MemoryDefinitionRepository(),
        submissions=MemorySubmissionStore(),
        durable_work=durable,
        events=MemoryEventStore(),
        profile="development",
        report_root=tmp_path / "reports",
        execution_route=execution_route,
    )
    service.register_definition(
        ctx,
        "pipeline-058",
        pipeline_to_dict(definition_from_pipeline(_ManagedPipeline)),
    )
    return ctx, authz, durable, service


def _spec(name: str) -> ManagedDeploymentSpec:
    return ManagedDeploymentSpec.from_current_runtime(
        name=name,
        work_pool_name=f"process-{name}",
        worker_backend_entry_point="phase058_test_backend",
        lockfile_sha256="a" * 64,
    )


@contextmanager
def _prefect_postgres_server(
    postgres_url: str, *, database_name: str, prefect_home: Path
) -> Generator[tuple[str, Callable[[], None], Callable[[], None]], None, None]:
    """Run a separately supervised Prefect API backed by its own PostgreSQL DB."""
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url

    base_url = make_url(postgres_url)
    admin_engine = create_engine(postgres_url, pool_pre_ping=True)
    try:
        with admin_engine.connect().execution_options(
            isolation_level="AUTOCOMMIT"
        ) as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
    finally:
        admin_engine.dispose()

    database_url = base_url.set(database=database_name).set(
        drivername="postgresql+asyncpg"
    )
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    api_url = f"http://127.0.0.1:{port}/api"
    server_environment = os.environ.copy()
    server_environment.update(
        {
            "PREFECT_API_URL": api_url,
            "PREFECT_SERVER_API_HOST": "127.0.0.1",
            "PREFECT_SERVER_API_PORT": str(port),
            "PREFECT_SERVER_DATABASE_CONNECTION_URL": database_url.render_as_string(
                hide_password=False
            ),
            "PREFECT_SERVER_ANALYTICS_ENABLED": "false",
            "PREFECT_LOGGING_TO_API_ENABLED": "false",
            "PREFECT_HOME": str(prefect_home),
        }
    )

    def start_server() -> subprocess.Popen[bytes]:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "prefect",
                "server",
                "start",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--no-ui",
                "--analytics-off",
            ],
            env=server_environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(
                        "self-hosted Prefect server exited before readiness"
                    )
                try:
                    with urllib.request.urlopen(
                        f"{api_url}/health", timeout=1
                    ) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(0.2)
            else:
                raise TimeoutError("self-hosted Prefect server did not become ready")
        except BaseException:
            stop_server(process)
            raise
        return process

    def stop_server(process: subprocess.Popen[bytes]) -> None:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)

    server: subprocess.Popen[bytes] | None = None

    def restart_server() -> None:
        nonlocal server
        if server is not None:
            stop_server(server)
        server = start_server()

    def stop_current_server() -> None:
        nonlocal server
        if server is not None:
            stop_server(server)
            server = None

    try:
        server = start_server()
        yield api_url, restart_server, stop_current_server
    finally:
        if server is not None:
            stop_server(server)
        cleanup_engine = create_engine(postgres_url, pool_pre_ping=True)
        try:
            with cleanup_engine.connect().execution_options(
                isolation_level="AUTOCOMMIT"
            ) as connection:
                connection.exec_driver_sql(
                    f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)'
                )
        finally:
            cleanup_engine.dispose()


def _claim_dispatch_in_process(
    url: str,
    store_id: str,
    ctx: ControlPlaneContext,
    submission_id: str,
    owner_id: str,
    now: datetime,
) -> tuple[int, str] | None:
    from sqlalchemy import create_engine

    from etlantic_sqlmodel.control_plane import SQLModelDurableWorkStore

    engine = create_engine(url, pool_pre_ping=True)
    try:
        claim = SQLModelDurableWorkStore(engine, store_id=store_id).claim_dispatch(
            ctx,
            submission_id,
            owner_id=owner_id,
            now=now,
        )
        return (
            (claim.lease_fencing_token, claim.creation_key)
            if claim is not None
            else None
        )
    finally:
        engine.dispose()


def _retire_route_in_process(
    database_url: str,
    store_id: str,
    artifact_root: str,
    prefect_api_url: str,
    ctx: ControlPlaneContext,
    binding: ManagedDeploymentBinding,
    barrier: Any,
    results: Any,
    crash_after_pause_marker: str | None = None,
) -> None:
    os.environ["PREFECT_API_URL"] = prefect_api_url
    from prefect.client.orchestration import PrefectClient

    from etlantic import Profile
    from etlantic.control_plane import MemoryAuthorizer
    from etlantic_prefect.deployment import PrefectDeploymentRegistrar
    from etlantic_sqlmodel.managed import SQLModelBackendConfig, create_managed_backend

    stage = "authorizer"
    authorizer = MemoryAuthorizer()
    authorizer.grant(ctx, "execution.route.manage")
    backend = create_managed_backend(
        SQLModelBackendConfig(
            database_url=database_url,
            store_id=store_id,
            profile=Profile(
                name="phase058-route-retirement",
                security_mode="development",
                plugin_allowlist={"etlantic": None},
            ),
            artifact_root=artifact_root,
            execution_route=binding.execution_route,
        ),
        authorizer=authorizer,
    )
    if crash_after_pause_marker is not None:
        original_transition = (
            ManagedApplicationService.transition_execution_route_lifecycle
        )

        def crash_before_retired_cas(
            self: ManagedApplicationService,
            ctx: ControlPlaneContext,
            execution_route: str,
            *,
            expected_revision: int,
            status: ExecutionRouteLifecycle,
        ) -> dict[str, Any]:
            if status == "retired":
                Path(crash_after_pause_marker).write_text("paused", encoding="utf-8")
                os._exit(81)
            return original_transition(
                self,
                ctx,
                execution_route,
                expected_revision=expected_revision,
                status=status,
            )

        ManagedApplicationService.transition_execution_route_lifecycle = (
            crash_before_retired_cas
        )
    try:
        stage = "barrier"
        barrier.wait(timeout=60)
        stage = "retire"
        result = asyncio.run(
            PrefectDeploymentRegistrar(
                client_factory=lambda: PrefectClient(prefect_api_url)
            ).retire(
                binding,
                backend=backend,
                context=ctx,
                expected_fingerprint=binding.fingerprint,
            )
        )
        results.put(
            {
                "stage": stage,
                "status": result.get("status"),
                "reason": result.get("reason"),
                "deployment_paused": result.get("deployment_paused"),
                "deployment_retained": result.get("deployment_retained"),
            }
        )
    except BaseException as exc:
        results.put(
            {
                "stage": stage,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "prefect_api_configured": bool(os.environ.get("PREFECT_API_URL")),
            }
        )
    finally:
        backend.close()


def _wait_for_marker(path: Path, *, timeout_seconds: float = 60) -> None:
    deadline = time.monotonic() + timeout_seconds
    while not path.is_file():
        if time.monotonic() >= deadline:
            raise TimeoutError(f"worker did not reach the crash marker: {path.name}")
        time.sleep(0.02)


def test_managed_deployment_binding_round_trips_and_rejects_tampering() -> None:
    spec = _spec("binding-test")
    binding = ManagedDeploymentBinding(spec=spec, deployment_id=uuid4())

    assert ManagedDeploymentBinding.from_dict(binding.to_dict()) == binding
    assert (
        ManagedDeploymentBinding.from_environment(binding.to_environment()) == binding
    )

    tampered = binding.to_environment()
    tampered["ETLANTIC_PREFECT_ROUTE_ID"] = "prefect:" + "0" * 64
    with pytest.raises(RuntimeError, match="inconsistent"):
        ManagedDeploymentBinding.from_environment(tampered)

    raw = binding.to_dict()
    raw["execution_route"] = "prefect:" + "0" * 64
    with pytest.raises(ValueError, match="fingerprint"):
        ManagedDeploymentBinding.from_dict(raw)
    with pytest.raises(RuntimeError, match="Process work pool"):
        ManagedDeploymentBinding.verify_remote_work_pool(
            SimpleNamespace(type="kubernetes")
        )

    drifted_spec = replace(spec, prefect_version="0.0.0")
    drifted_binding = ManagedDeploymentBinding(
        spec=drifted_spec, deployment_id=binding.deployment_id
    )
    with pytest.raises(RuntimeError, match="runtime does not match"):
        ManagedDeploymentBinding.from_environment(drifted_binding.to_environment())


def test_managed_execution_reference_enforces_schema_and_identifier_bounds() -> None:
    reference = ManagedExecutionReference(
        submission_id="s" * 512,
        plan_fingerprint="a" * 64,
        envelope_sha256="b" * 64,
    )
    assert ManagedExecutionReference.from_dict(reference.to_dict()) == reference

    oversized = reference.to_dict()
    oversized["submission_id"] = "s" * 513
    with pytest.raises(ValueError, match="submission_id"):
        ManagedExecutionReference.from_dict(oversized)

    unexpected = reference.to_dict()
    unexpected["tenant_id"] = "caller-controlled"
    with pytest.raises(ValueError, match="unknown or missing"):
        ManagedExecutionReference.from_dict(unexpected)


def test_remote_status_and_cancellation_remain_separate_observations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from prefect.client.schemas.objects import State, StateType
    from prefect.client.schemas.responses import SetStateStatus

    from etlantic_prefect.worker import (
        _reconciliation_projection,
        _remote_flow_run_observation,
        _request_remote_cancellation,
    )

    binding = ManagedDeploymentBinding(
        spec=_spec("observation-test"), deployment_id=uuid4()
    )
    dispatch = SimpleNamespace(
        status="dispatched",
        execution_route=binding.execution_route,
        prefect_flow_run_id=str(uuid4()),
        dispatch_attempts=1,
    )

    class _Client:
        def __enter__(self) -> _Client:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read_flow_run(self, flow_run_id: UUID) -> Any:
            assert str(flow_run_id) == dispatch.prefect_flow_run_id
            return SimpleNamespace(state=State(type=StateType.RUNNING, name="Running"))

        def set_flow_run_state(
            self, flow_run_id: UUID, state: Any, *, force: bool
        ) -> Any:
            assert flow_run_id == dispatch.prefect_flow_run_id
            assert state.type is StateType.CANCELLING
            assert force is False
            return SimpleNamespace(
                status=SetStateStatus.ACCEPT,
                state=State(type=StateType.CANCELLING, name="Cancelling"),
            )

    import prefect.client.orchestration

    def _get_client(**_kwargs: Any) -> _Client:
        return _Client()

    monkeypatch.setattr(prefect.client.orchestration, "get_client", _get_client)
    observation = _remote_flow_run_observation(dispatch, binding)
    assert observation["status"] == "Running"
    assert observation["state_type"] == "RUNNING"
    assert observation["flow_run_id"] == dispatch.prefect_flow_run_id
    assert observation["observed_at"]
    assert observation["dispatch_status"] == "dispatched"

    cancellation = _request_remote_cancellation(dispatch, binding)
    assert cancellation["status"] == "requested"
    assert cancellation["prefect_status"] == "ACCEPT"
    assert cancellation["state"] == "Cancelling"
    assert _request_remote_cancellation(None, binding) == {"status": "not_dispatched"}
    assert _reconciliation_projection("completed", {"status": "Completed"}) == {
        "status": "consistent"
    }
    assert _reconciliation_projection("accepted", {"status": "Failed"}) == {
        "status": "canonical_reconciliation_required"
    }
    assert _reconciliation_projection("completed", {"status": "Running"}) == {
        "status": "remote_lagging"
    }
    assert _reconciliation_projection("failed", {"status": "Completed"}) == {
        "status": "conflict"
    }
    assert _reconciliation_projection("cancel_requested", {"status": "Cancelling"}) == {
        "status": "cancellation_pending"
    }
    assert _reconciliation_projection("cancel_requested", {"status": "Completed"}) == {
        "status": "canonical_reconciliation_required"
    }

    dispatch.status = "reconciliation_required"
    dispatch.generation = 3
    dispatch.last_error_code = "dispatch_generation_exhausted"

    class _FailedClient(_Client):
        def read_flow_run(self, flow_run_id: UUID) -> Any:
            assert str(flow_run_id) == dispatch.prefect_flow_run_id
            return SimpleNamespace(state=State(type=StateType.FAILED, name="Failed"))

    def _get_failed_client(**_kwargs: Any) -> _FailedClient:
        return _FailedClient()

    monkeypatch.setattr(prefect.client.orchestration, "get_client", _get_failed_client)
    exhausted = _remote_flow_run_observation(dispatch, binding)
    assert exhausted["status"] == "Failed"
    assert exhausted["dispatch_status"] == "reconciliation_required"
    assert exhausted["generation"] == 3
    assert exhausted["error_code"] == "dispatch_generation_exhausted"
    assert _reconciliation_projection("accepted", exhausted)["status"] == (
        "canonical_reconciliation_required"
    )


def test_managed_cancellation_is_durable_before_remote_retry_and_status_reconcile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import prefect.client.orchestration
    from prefect.client.schemas.objects import State, StateType
    from prefect.client.schemas.responses import SetStateStatus

    import etlantic_prefect.worker as worker

    binding = ManagedDeploymentBinding(
        spec=_spec(f"cancel-test-{uuid4().hex[:8]}"), deployment_id=uuid4()
    )
    ctx, _authz, durable, service = _managed_service(
        tmp_path, execution_route=binding.execution_route
    )
    receipt = service.submit_run(
        ctx, "pipeline-058", idempotency_key="managed-cancel-phase-058"
    )
    outside_ctx = ControlPlaneContext(
        principal=Principal(subject="outside-tenant", issuer="tests"),
        tenant=TenantRef(tenant_id="outside-tenant"),
        workspace=WorkspaceRef(
            tenant_id="outside-tenant", workspace_id="outside-workspace"
        ),
        environment=EnvironmentRef(name="test"),
        security_domain=SecurityDomain(domain_id="default"),
    )
    with pytest.raises(ControlPlaneError) as status_denied:
        service.get_run_status(outside_ctx, str(receipt.resource_id))
    assert status_denied.value.status == 404
    with pytest.raises(ControlPlaneError) as cancellation_denied:
        service.cancel_run(outside_ctx, str(receipt.resource_id))
    assert cancellation_denied.value.status == 404
    assert durable.get_submission(ctx, receipt.submission_id).status == "accepted"

    dispatch = durable.prepare_dispatch(ctx, receipt.submission_id)
    claim = durable.claim_dispatch(
        ctx, receipt.submission_id, owner_id="cancel-test-dispatcher"
    )
    assert claim is not None
    flow_run_id = str(uuid4())
    durable.link_dispatch(
        ctx,
        receipt.submission_id,
        owner_id="cancel-test-dispatcher",
        fencing_token=claim.lease_fencing_token,
        prefect_flow_run_id=flow_run_id,
    )
    assert dispatch.status == "pending"
    submission = durable.get_submission(ctx, receipt.submission_id)
    reference = ManagedExecutionReference.from_submission(submission).to_dict()
    backend = SimpleNamespace(
        durable_work=durable,
        managed_service=service,
        close=lambda: None,
    )
    monkeypatch.setattr(worker, "_load_trusted_backend", lambda: (backend, ctx))
    for key, value in binding.to_environment().items():
        monkeypatch.setenv(key, value)

    cancellation_calls = 0

    class _Client:
        def __enter__(self) -> _Client:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def set_flow_run_state(
            self, requested_id: UUID, state: Any, *, force: bool
        ) -> Any:
            nonlocal cancellation_calls
            assert requested_id == flow_run_id
            assert state.type is StateType.CANCELLING
            assert force is False
            assert durable.get_submission(ctx, receipt.submission_id).status == (
                "cancel_requested"
            )
            cancellation_calls += 1
            if cancellation_calls == 1:
                raise ConnectionError("simulated lost cancellation response")
            return SimpleNamespace(
                status=SetStateStatus.ACCEPT,
                state=State(type=StateType.CANCELLING, name="Cancelling"),
            )

        def read_flow_run(self, requested_id: UUID) -> Any:
            assert str(requested_id) == flow_run_id
            return SimpleNamespace(
                state=State(type=StateType.COMPLETED, name="Completed")
            )

    def _get_client(**_kwargs: Any) -> _Client:
        return _Client()

    monkeypatch.setattr(prefect.client.orchestration, "get_client", _get_client)

    first = worker.request_managed_run_cancellation(reference)
    assert first["cancellation_durable"] is True
    assert first["status"] == "cancel_requested"
    assert first["remote_cancellation"]["status"] == "unavailable"
    assert durable.get_submission(ctx, receipt.submission_id).status == (
        "cancel_requested"
    )

    second = worker.request_managed_run_cancellation(reference)
    assert second["status"] == "cancel_requested"
    assert second["remote_cancellation"]["status"] == "requested"
    assert cancellation_calls == 2

    status = worker.get_managed_run_status(reference)
    assert status["status"] == "cancel_requested"
    assert status["remote_orchestration"]["status"] == "Completed"
    assert status["reconciliation"]["status"] == "canonical_reconciliation_required"
    assert durable.get_submission(ctx, receipt.submission_id).status == (
        "cancel_requested"
    )


def test_remote_terminal_disagreement_does_not_rewrite_completed_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import prefect.client.orchestration
    from prefect.client.schemas.objects import State, StateType

    import etlantic_prefect.worker as worker

    binding = ManagedDeploymentBinding(
        spec=_spec(f"terminal-disagreement-{uuid4().hex[:8]}"),
        deployment_id=uuid4(),
    )
    ctx, _authz, durable, managed = _managed_service(
        tmp_path, execution_route=binding.execution_route
    )
    receipt = managed.submit_run(
        ctx, "pipeline-058", idempotency_key="managed-terminal-disagreement"
    )
    dispatch = durable.prepare_dispatch(ctx, receipt.submission_id)
    claim = durable.claim_dispatch(
        ctx, receipt.submission_id, owner_id="terminal-disagreement-dispatcher"
    )
    assert claim is not None
    flow_run_id = str(uuid4())
    durable.link_dispatch(
        ctx,
        receipt.submission_id,
        owner_id="terminal-disagreement-dispatcher",
        fencing_token=claim.lease_fencing_token,
        prefect_flow_run_id=flow_run_id,
    )
    assert dispatch.status == "pending"

    lease = durable.acquire_lease(
        ctx,
        receipt.submission_id,
        owner_id="terminal-disagreement-worker",
        ttl_seconds=60,
    )
    attempt = durable.start_attempt(
        ctx,
        receipt.submission_id,
        owner_id=lease.owner_id,
        fencing_token=lease.fencing_token,
    )
    durable.finish_attempt(
        ctx,
        attempt.attempt_id,
        owner_id=lease.owner_id,
        fencing_token=lease.fencing_token,
        status="completed",
    )

    submission = durable.get_submission(ctx, receipt.submission_id)
    reference = ManagedExecutionReference.from_submission(submission).to_dict()
    backend = SimpleNamespace(
        durable_work=durable,
        managed_service=managed,
        close=lambda: None,
    )
    monkeypatch.setattr(worker, "_load_trusted_backend", lambda: (backend, ctx))
    for key, value in binding.to_environment().items():
        monkeypatch.setenv(key, value)

    class _Client:
        def __enter__(self) -> _Client:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read_flow_run(self, requested_id: UUID) -> Any:
            assert str(requested_id) == flow_run_id
            return SimpleNamespace(state=State(type=StateType.FAILED, name="Failed"))

    def _get_client(**_kwargs: Any) -> _Client:
        return _Client()

    monkeypatch.setattr(prefect.client.orchestration, "get_client", _get_client)
    projection = worker.get_managed_run_status(reference)

    assert projection["status"] == "completed"
    assert projection["remote_orchestration"]["status"] == "Failed"
    assert projection["reconciliation"]["status"] == "conflict"
    assert durable.get_submission(ctx, receipt.submission_id).status == "completed"
    assert durable.list_attempts(ctx, receipt.submission_id)[0].status == "completed"


def test_dispatch_identity_survives_uncertain_delivery_and_is_fenced(
    tmp_path: Path,
) -> None:
    route = "prefect:" + "b" * 64
    ctx, _authz, durable, service = _managed_service(tmp_path, execution_route=route)
    receipt = service.submit_run(
        ctx, "pipeline-058", idempotency_key="dispatch-phase-058"
    )
    accepted = durable.get_submission(ctx, receipt.submission_id)
    assert accepted.execution_route == route

    prepared = durable.prepare_dispatch(ctx, receipt.submission_id)
    assert durable.prepare_dispatch(ctx, receipt.submission_id) == prepared
    now = datetime.now(UTC)
    first = durable.claim_dispatch(
        ctx, receipt.submission_id, owner_id="dispatcher-a", now=now
    )
    assert first is not None
    assert (
        durable.claim_dispatch(
            ctx, receipt.submission_id, owner_id="dispatcher-b", now=now
        )
        is None
    )
    uncertain = durable.release_dispatch(
        ctx,
        receipt.submission_id,
        owner_id="dispatcher-a",
        fencing_token=first.lease_fencing_token,
        outcome_uncertain=True,
        error_code="prefect_create_uncertain",
        now=now,
    )
    assert uncertain.status == "uncertain"
    assert uncertain.retry_after_at is not None
    assert (
        durable.claim_dispatch(
            ctx,
            receipt.submission_id,
            owner_id="dispatcher-b",
            now=now + timedelta(seconds=1),
        )
        is None
    )

    recovered = durable.claim_dispatch(
        ctx,
        receipt.submission_id,
        owner_id="dispatcher-b",
        now=now + timedelta(seconds=3),
    )
    assert recovered is not None
    assert recovered.creation_key == first.creation_key
    linked = durable.link_dispatch(
        ctx,
        receipt.submission_id,
        owner_id="dispatcher-b",
        fencing_token=recovered.lease_fencing_token,
        prefect_flow_run_id="flow-run-058",
        now=now + timedelta(seconds=3),
    )
    assert linked.status == "dispatched"
    assert linked.prefect_flow_run_id == "flow-run-058"
    assert (
        durable.link_dispatch(
            ctx,
            receipt.submission_id,
            owner_id="dispatcher-b",
            fencing_token=recovered.lease_fencing_token,
            prefect_flow_run_id="flow-run-058",
            now=now + timedelta(seconds=3),
        )
        == linked
    )
    with pytest.raises(ControlPlaneError):
        durable.link_dispatch(
            ctx,
            receipt.submission_id,
            owner_id="dispatcher-b",
            fencing_token=recovered.lease_fencing_token,
            prefect_flow_run_id="different-flow-run",
            now=now + timedelta(seconds=3),
        )


def test_dispatcher_recovers_lost_create_response_with_prefect_idempotency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import prefect.client.orchestration
    from prefect.client.schemas.actions import WorkPoolCreate
    from prefect.settings import PREFECT_API_URL, temporary_settings
    from prefect.testing.utilities import prefect_test_harness

    import etlantic.control_plane.durable_memory as durable_memory

    real_get_client = prefect.client.orchestration.get_client
    scope = uuid4().hex[:10]
    spec = _spec(f"phase058-recovery-{scope}")
    registrar = PrefectDeploymentRegistrar()
    now = [datetime.now(UTC)]
    create_calls: list[dict[str, Any]] = []
    accepted_remote_runs: list[Any] = []

    class _LostResponseClient:
        def __init__(self) -> None:
            self._manager = real_get_client()
            self._client: Any = None

        async def __aenter__(self) -> _LostResponseClient:
            self._client = await self._manager.__aenter__()
            return self

        async def __aexit__(self, *args: Any) -> Any:
            return await self._manager.__aexit__(*args)

        def __getattr__(self, name: str) -> Any:
            return getattr(self._client, name)

        async def create_flow_run_from_deployment(
            self, *args: Any, **kwargs: Any
        ) -> Any:
            create_calls.append(dict(kwargs))
            flow_run = await self._client.create_flow_run_from_deployment(
                *args, **kwargs
            )
            accepted_remote_runs.append(flow_run)
            if len(create_calls) == 1:
                raise ConnectionError("simulated response loss after remote create")
            return flow_run

    monkeypatch.setattr(durable_memory, "_now", lambda: now[0])

    def _get_client(**_kwargs: Any) -> _LostResponseClient:
        return _LostResponseClient()

    monkeypatch.setattr(prefect.client.orchestration, "get_client", _get_client)

    async def scenario() -> None:
        async with real_get_client() as client:
            await client.create_work_pool(
                WorkPoolCreate(name=spec.work_pool_name, type="process")
            )
        preview = await registrar.preview(spec)
        binding = await registrar.register(
            spec, expected_fingerprint=preview["spec"]["fingerprint"]
        )
        ctx, _authz, durable, service = _managed_service(
            tmp_path, execution_route=binding.execution_route
        )
        receipt = service.submit_run(
            ctx, "pipeline-058", idempotency_key=f"lost-create-{scope}"
        )
        dispatcher = PrefectDispatcher(
            backend=SimpleNamespace(durable_work=durable),  # type: ignore[arg-type]
            context=ctx,
            binding=binding,
            owner_id=f"dispatcher-{scope}",
        )

        first = await dispatcher.tick(limit=1)
        assert len(first) == 1
        assert first[0]["submission_id"] == receipt.submission_id
        assert first[0]["status"] == "uncertain"
        assert first[0]["error_code"] == "prefect_create_uncertain"
        assert len(accepted_remote_runs) == 1
        first_diagnostics = dispatcher.diagnostics()
        assert first_diagnostics["ticks"] == 1
        assert first_diagnostics["dispatch_attempts"] == 1
        assert first_diagnostics["uncertain_creates"] == 1
        assert first_diagnostics["remote_api_failures"] == 1
        assert first_diagnostics["dispatch_errors"] == 1
        assert first_diagnostics["queue_age_high_water_seconds"] is not None
        assert receipt.submission_id not in str(first_diagnostics)

        now[0] += timedelta(seconds=3)
        second = await dispatcher.tick(limit=1)
        assert len(second) == 1
        assert second[0]["submission_id"] == receipt.submission_id
        assert second[0]["status"] == "dispatched"
        assert second[0]["prefect_flow_run_id"] == str(accepted_remote_runs[0].id)
        assert len(accepted_remote_runs) == 2
        assert accepted_remote_runs[1].id == accepted_remote_runs[0].id
        assert create_calls[0]["idempotency_key"] == create_calls[1]["idempotency_key"]
        assert create_calls[0]["parameters"] == create_calls[1]["parameters"]
        diagnostics = dispatcher.diagnostics()
        assert diagnostics["ticks"] == 2
        assert diagnostics["failed_ticks"] == 0
        assert diagnostics["dispatch_attempts"] == 2
        assert diagnostics["uncertain_creates"] == 1
        assert diagnostics["remote_api_failures"] == 1
        queue_age_high_water = diagnostics["queue_age_high_water_seconds"]
        assert isinstance(queue_age_high_water, (int, float))
        assert queue_age_high_water >= 0
        assert str(accepted_remote_runs[0].id) not in str(diagnostics)
        dispatch = durable.get_dispatch(ctx, receipt.submission_id)
        assert dispatch.dispatch_attempts == 2
        assert dispatch.creation_key == create_calls[0]["idempotency_key"]

    postgres_url = os.environ.get("ETLANTIC_CP_TEST_URL")
    if postgres_url:
        with _prefect_postgres_server(
            postgres_url,
            database_name=f"prefect_058_dispatch_{scope[:12]}",
            prefect_home=tmp_path / "prefect-dispatch-home",
        ) as (prefect_api_url, _restart_prefect_server, _stop_prefect_server):
            monkeypatch.setenv("PREFECT_API_URL", prefect_api_url)
            with temporary_settings({PREFECT_API_URL: prefect_api_url}):
                asyncio.run(scenario())
    else:
        with prefect_test_harness():
            asyncio.run(scenario())


def test_sqlmodel_dispatch_snapshot_survives_store_reconstruction(
    tmp_path: Path,
) -> None:
    sqlmodel_cp = pytest.importorskip("etlantic_sqlmodel.control_plane")
    route = "prefect:" + "e" * 64
    ctx, _authz, memory, service = _managed_service(tmp_path, execution_route=route)
    receipt = service.submit_run(
        ctx, "pipeline-058", idempotency_key="sqlmodel-source-058"
    )
    original = memory.get_submission(ctx, receipt.submission_id)
    assert original.input_snapshot is not None
    envelope = ExecutionEnvelope.from_json(original.input_snapshot)

    engine = sqlmodel_cp.create_sqlite_engine(
        f"sqlite:///{tmp_path / 'dispatch-snapshot.db'}"
    )
    try:
        sqlmodel_cp.create_durable_tables(engine)
        store = sqlmodel_cp.SQLModelDurableWorkStore(engine, store_id="phase-0-58")
        accepted, created = store.accept(
            ctx,
            idempotency_key="sqlmodel-dispatch-058",
            operation="run.submit",
            plan_fingerprint=envelope.plan_fingerprint,
            revision_id=envelope.revision_id,
            input_snapshot=original.input_snapshot,
            submission_id="sub-sqlmodel-058",
            run_id="run-sqlmodel-058",
            execution_route=route,
        )
        assert created is True
        active_route = store.get_execution_route_state(ctx, route)
        assert active_route.status == "active"
        dispatch = store.prepare_dispatch(ctx, accepted.submission_id)
        final_flow_run_id = ""
        exhausted: DispatchRecord | None = None
        for generation in range(1, 4):
            claim = store.claim_dispatch(
                ctx, accepted.submission_id, owner_id=f"sql-generation-{generation}"
            )
            assert claim is not None
            final_flow_run_id = str(uuid4())
            store.link_dispatch(
                ctx,
                accepted.submission_id,
                owner_id=f"sql-generation-{generation}",
                fencing_token=claim.lease_fencing_token,
                prefect_flow_run_id=final_flow_run_id,
            )
            exhausted = store.rearm_dispatch_after_remote_failure(
                ctx,
                accepted.submission_id,
                expected_flow_run_id=final_flow_run_id,
            )
        assert exhausted is not None
        assert exhausted.status == "reconciliation_required"
        dispatch = store.rearm_reconciliation_required_dispatch(
            ctx,
            accepted.submission_id,
            expected_generation=3,
            expected_flow_run_id=final_flow_run_id,
            evidence_sha256="f" * 64,
        )
        assert dispatch.status == "pending"
        assert len(dispatch.reconciliation_history) == 1
        draining_route = store.transition_execution_route_state(
            ctx,
            route,
            expected_revision=active_route.revision,
            status="draining",
        )
        reopened = sqlmodel_cp.SQLModelDurableWorkStore(engine, store_id="phase-0-58")
        assert reopened.get_dispatch(ctx, accepted.submission_id) == dispatch
        assert reopened.get_execution_route_state(ctx, route) == draining_route
        workload = reopened.execution_route_workload(ctx, route)
        assert workload.active_submissions == 1
        assert workload.unpublished_outboxes == 1
        assert workload.drained is False
        assert dispatch.retry_after_at is None
    finally:
        engine.dispose()


def test_postgresql_dispatch_claim_is_single_and_retry_identity_is_stable(
    tmp_path: Path,
) -> None:
    url = os.environ.get("ETLANTIC_CP_TEST_URL")
    if not url:
        pytest.skip(
            "set ETLANTIC_CP_TEST_URL for live PostgreSQL dispatch qualification"
        )
    sqlmodel_cp = pytest.importorskip("etlantic_sqlmodel.control_plane")
    from sqlalchemy import create_engine, delete

    from etlantic_sqlmodel.control_plane.models import (
        DurableOutboxEntityRow,
        DurableSnapshotRow,
        DurableSubmissionEntityRow,
    )
    from sqlmodel import Session

    route = "prefect:" + "f" * 64
    ctx, _authz, memory, managed = _managed_service(tmp_path, execution_route=route)
    receipt = managed.submit_run(
        ctx, "pipeline-058", idempotency_key="postgres-dispatch-source-058"
    )
    original = memory.get_submission(ctx, receipt.submission_id)
    assert original.input_snapshot is not None
    envelope = ExecutionEnvelope.from_json(original.input_snapshot)
    store_id = f"phase058-dispatch-{uuid4().hex}"
    engine = create_engine(url, pool_pre_ping=True)
    sqlmodel_cp.create_durable_tables(engine)
    store = sqlmodel_cp.SQLModelDurableWorkStore(engine, store_id=store_id)
    submission_id = f"sub-{uuid4().hex}"
    try:
        accepted, created = store.accept(
            ctx,
            idempotency_key=f"pg-dispatch-{uuid4().hex}",
            operation="run.submit",
            plan_fingerprint=envelope.plan_fingerprint,
            revision_id=envelope.revision_id,
            input_snapshot=original.input_snapshot,
            submission_id=submission_id,
            run_id=f"run-{uuid4().hex}",
            execution_route=route,
        )
        assert created is True
        initial = store.prepare_dispatch(ctx, accepted.submission_id)
        now = datetime.now(UTC)
        owners = ["postgres-dispatcher-a", "postgres-dispatcher-b"]
        with ProcessPoolExecutor(
            max_workers=2, mp_context=get_context("spawn")
        ) as workers:
            claims = list(
                workers.map(
                    _claim_dispatch_in_process,
                    [url] * 2,
                    [store_id] * 2,
                    [ctx] * 2,
                    [accepted.submission_id] * 2,
                    owners,
                    [now] * 2,
                )
            )
        claimed = [
            (owner, result)
            for owner, result in zip(owners, claims, strict=True)
            if result
        ]
        assert len(claimed) == 1
        winner, winning_claim = claimed[0]
        assert winning_claim is not None
        fencing_token, creation_key = winning_claim
        assert creation_key == initial.creation_key

        reopened = sqlmodel_cp.SQLModelDurableWorkStore(engine, store_id=store_id)
        leased = reopened.get_dispatch(ctx, accepted.submission_id)
        assert leased.status == "leased"
        uncertain = reopened.release_dispatch(
            ctx,
            accepted.submission_id,
            owner_id=winner,
            fencing_token=fencing_token,
            outcome_uncertain=True,
            error_code="prefect_create_uncertain",
            now=now,
        )
        assert uncertain.retry_after_at is not None
        assert (
            reopened.claim_dispatch(
                ctx,
                accepted.submission_id,
                owner_id="postgres-dispatcher-recovery",
                now=now + timedelta(seconds=1),
            )
            is None
        )
        retry = reopened.claim_dispatch(
            ctx,
            accepted.submission_id,
            owner_id="postgres-dispatcher-recovery",
            now=now + timedelta(seconds=3),
        )
        assert retry is not None
        assert retry.creation_key == creation_key
        linked = reopened.link_dispatch(
            ctx,
            accepted.submission_id,
            owner_id="postgres-dispatcher-recovery",
            fencing_token=retry.lease_fencing_token,
            prefect_flow_run_id=str(uuid4()),
            now=now + timedelta(seconds=3),
        )
        assert linked.status == "dispatched"
        assert reopened.get_dispatch(ctx, accepted.submission_id) == linked
    finally:
        with Session(engine) as session, session.begin():
            session.exec(
                delete(DurableOutboxEntityRow).where(
                    DurableOutboxEntityRow.store_id == store_id
                )
            )
            session.exec(
                delete(DurableSubmissionEntityRow).where(
                    DurableSubmissionEntityRow.store_id == store_id
                )
            )
            session.exec(
                delete(DurableSnapshotRow).where(
                    DurableSnapshotRow.store_id == store_id
                )
            )
        engine.dispose()


def test_postgresql_exhausted_dispatch_reconciliation_persists_audit(
    tmp_path: Path,
) -> None:
    url = os.environ.get("ETLANTIC_CP_TEST_URL")
    if not url:
        pytest.skip(
            "set ETLANTIC_CP_TEST_URL for live PostgreSQL reconciliation qualification"
        )
    sqlmodel_cp = pytest.importorskip("etlantic_sqlmodel.control_plane")
    from sqlalchemy import create_engine, text

    route = "prefect:" + "d" * 64
    ctx, _authz, memory, managed = _managed_service(tmp_path, execution_route=route)
    receipt = managed.submit_run(
        ctx, "pipeline-058", idempotency_key="postgres-dispatch-reconcile-source"
    )
    original = memory.get_submission(ctx, receipt.submission_id)
    assert original.input_snapshot is not None
    envelope = ExecutionEnvelope.from_json(original.input_snapshot)
    store_id = f"phase058-reconcile-{uuid4().hex}"
    engine = create_engine(url, pool_pre_ping=True)
    sqlmodel_cp.create_durable_tables(engine)
    store = sqlmodel_cp.SQLModelDurableWorkStore(engine, store_id=store_id)
    try:
        accepted, created = store.accept(
            ctx,
            idempotency_key=f"pg-dispatch-reconcile-{uuid4().hex}",
            operation="run.submit",
            plan_fingerprint=envelope.plan_fingerprint,
            revision_id=envelope.revision_id,
            input_snapshot=original.input_snapshot,
            submission_id=f"sub-{uuid4().hex}",
            run_id=f"run-{uuid4().hex}",
            execution_route=route,
        )
        assert created is True
        exhausted: DispatchRecord | None = None
        final_flow_run_id = ""
        for generation in range(1, 4):
            prepared = store.prepare_dispatch(ctx, accepted.submission_id)
            assert prepared.generation == generation
            claim = store.claim_dispatch(
                ctx,
                accepted.submission_id,
                owner_id=f"postgres-reconcile-{generation}",
            )
            assert claim is not None
            final_flow_run_id = f"flow-run-{uuid4()}"
            store.link_dispatch(
                ctx,
                accepted.submission_id,
                owner_id=f"postgres-reconcile-{generation}",
                fencing_token=claim.lease_fencing_token,
                prefect_flow_run_id=final_flow_run_id,
            )
            exhausted = store.rearm_dispatch_after_remote_failure(
                ctx,
                accepted.submission_id,
                expected_flow_run_id=final_flow_run_id,
            )
        assert exhausted is not None
        assert exhausted.generation == 3
        assert exhausted.status == "reconciliation_required"
        assert (
            store.claim_dispatch(
                ctx, accepted.submission_id, owner_id="postgres-auto-retry"
            )
            is None
        )

        evidence = "e" * 64
        rearmed = store.rearm_reconciliation_required_dispatch(
            ctx,
            accepted.submission_id,
            expected_generation=exhausted.generation,
            expected_flow_run_id=final_flow_run_id,
            evidence_sha256=evidence,
        )
        assert rearmed.status == "pending"
        assert rearmed.generation == exhausted.generation + 1
        assert rearmed.creation_key != exhausted.creation_key
        assert rearmed.prefect_flow_run_id is None
        assert len(rearmed.reconciliation_history) == 1
        audit = rearmed.reconciliation_history[0]
        assert audit.from_generation == exhausted.generation
        assert audit.to_generation == rearmed.generation
        assert audit.principal_subject == ctx.principal.subject
        assert audit.evidence_sha256 == evidence

        reopened = sqlmodel_cp.SQLModelDurableWorkStore(engine, store_id=store_id)
        persisted = reopened.get_dispatch(ctx, accepted.submission_id)
        assert persisted == rearmed
        with pytest.raises(ControlPlaneError) as stale:
            reopened.rearm_reconciliation_required_dispatch(
                ctx,
                accepted.submission_id,
                expected_generation=exhausted.generation,
                expected_flow_run_id=final_flow_run_id,
                evidence_sha256=evidence,
            )
        assert stale.value.extensions["reason"] == "stale_dispatch_reconciliation"
    finally:
        with engine.begin() as connection:
            for table in (
                "cp_durable_outbox_entity",
                "cp_durable_submission_entity",
                "cp_durable_snapshot",
            ):
                connection.execute(
                    text(f"DELETE FROM {table} WHERE store_id = :store_id"),
                    {"store_id": store_id},
                )
        engine.dispose()


def test_dispatcher_exposes_supervisor_status_and_drain(tmp_path: Path) -> None:
    binding = ManagedDeploymentBinding(
        spec=_spec("dispatcher-lifecycle"), deployment_id=uuid4()
    )
    ctx, _authz, durable, _service = _managed_service(
        tmp_path, execution_route=binding.execution_route
    )
    registered_roles: list[Any] = []
    dispatcher = PrefectDispatcher(
        backend=cast(
            ManagedBackend,
            SimpleNamespace(
                durable_work=durable,
                register_runtime_role=registered_roles.append,
            ),
        ),
        context=ctx,
        binding=binding,
        owner_id="dispatcher-test",
    )
    assert len(registered_roles) == 1
    assert registered_roles[0].status().role == "dispatcher"
    assert dispatcher.status().role == "dispatcher"
    assert dispatcher.status().admission == "accepting"
    assert dispatcher.request_drain().admission == "stopped"
    assert asyncio.run(dispatcher.tick()) == []


def test_dispatcher_diagnostics_capture_stale_remote_links_without_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import prefect.client.orchestration
    from prefect.exceptions import ObjectNotFound

    binding = ManagedDeploymentBinding(
        spec=_spec("dispatcher-stale-link-diagnostics"), deployment_id=uuid4()
    )
    ctx, _authz, durable, service = _managed_service(
        tmp_path, execution_route=binding.execution_route
    )
    failed = service.submit_run(ctx, "pipeline-058", idempotency_key="stale-failed-run")
    missing = service.submit_run(
        ctx, "pipeline-058", idempotency_key="stale-missing-run"
    )
    failed_flow_id = str(uuid4())
    missing_flow_id = str(uuid4())
    for receipt, flow_run_id in (
        (failed, failed_flow_id),
        (missing, missing_flow_id),
    ):
        durable.prepare_dispatch(ctx, receipt.submission_id)
        claim = durable.claim_dispatch(
            ctx,
            receipt.submission_id,
            owner_id="diagnostics-test-dispatcher",
        )
        assert claim is not None
        durable.link_dispatch(
            ctx,
            receipt.submission_id,
            owner_id="diagnostics-test-dispatcher",
            fencing_token=claim.lease_fencing_token,
            prefect_flow_run_id=flow_run_id,
        )

    class _Client:
        async def __aenter__(self) -> _Client:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def read_flow_run(self, flow_run_id: UUID) -> Any:
            if str(flow_run_id) == missing_flow_id:
                raise ObjectNotFound(RuntimeError("fixture remote run is missing"))
            return SimpleNamespace(
                state=SimpleNamespace(type=SimpleNamespace(value="FAILED"))
            )

        async def create_flow_run_from_deployment(
            self, *_args: Any, **_kwargs: Any
        ) -> Any:
            return SimpleNamespace(id=uuid4())

    def _get_client(**_kwargs: Any) -> _Client:
        return _Client()

    monkeypatch.setattr(prefect.client.orchestration, "get_client", _get_client)

    async def skip_remote_binding(_self: PrefectDispatcher) -> None:
        return None

    monkeypatch.setattr(
        PrefectDispatcher, "_verify_remote_binding", skip_remote_binding
    )
    dispatcher = PrefectDispatcher(
        backend=SimpleNamespace(durable_work=durable),  # type: ignore[arg-type]
        context=ctx,
        binding=binding,
        owner_id="diagnostics-test-dispatcher",
    )

    asyncio.run(dispatcher.tick(limit=10))

    diagnostics = dispatcher.diagnostics()
    assert diagnostics["remote_missing_observations"] == 1
    assert diagnostics["remote_terminal_failure_observations"] == 1
    assert diagnostics["remote_api_failures"] == 0
    assert failed_flow_id not in str(diagnostics)
    assert missing_flow_id not in str(diagnostics)


def test_backend_close_waits_for_registered_dispatcher_before_disposal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _TrackedEngine:
        disposed = False

        def dispose(self) -> None:
            self.disposed = True

    binding = ManagedDeploymentBinding(
        spec=_spec("dispatcher-close-race"), deployment_id=uuid4()
    )
    ctx, authz, durable, service = _managed_service(
        tmp_path, execution_route=binding.execution_route
    )
    engine = _TrackedEngine()
    backend = ManagedBackend(
        authorizer=authz,
        engine=engine,
        managed_service=service,
        registry=SimpleNamespace(),
        definitions=SimpleNamespace(),
        submissions=SimpleNamespace(),
        events=SimpleNamespace(),
        durable_work=durable,
        schedule_store=MemoryScheduleStore(),
        input_resources=SimpleNamespace(),
        report_store_factory=lambda _ctx: None,
    )
    dispatcher = PrefectDispatcher(
        backend=backend,
        context=ctx,
        binding=binding,
        owner_id="dispatcher-close-race",
    )
    entered = asyncio.Event()
    release = asyncio.Event()

    async def hold_remote_check(_self: PrefectDispatcher) -> None:
        entered.set()
        await release.wait()

    async def skip_reconciliation(
        _self: PrefectDispatcher, *, limit: int, now: datetime | None = None
    ) -> None:
        del limit, now

    monkeypatch.setattr(PrefectDispatcher, "_verify_remote_binding", hold_remote_check)
    monkeypatch.setattr(
        PrefectDispatcher, "_reconcile_remote_failures", skip_reconciliation
    )

    async def exercise() -> None:
        tick = asyncio.create_task(dispatcher.tick(limit=1))
        await asyncio.wait_for(entered.wait(), timeout=1)
        with pytest.raises(RuntimeError, match="roles are still active"):
            backend.close()
        assert dispatcher.status().admission == "draining"
        assert dispatcher.status().in_flight == 1
        assert not engine.disposed

        release.set()
        assert await tick == []
        assert dispatcher.status().admission == "stopped"
        assert dispatcher.status().in_flight == 0
        backend.close()
        assert engine.disposed

    asyncio.run(exercise())


def test_managed_schedule_pins_route_across_runtime_configuration_change(
    tmp_path: Path,
) -> None:
    route_at_creation = "prefect:" + "c" * 64
    route_after_change = "prefect:" + "d" * 64
    ctx, authz, durable, managed = _managed_service(
        tmp_path, execution_route=route_at_creation
    )
    schedules = MemoryScheduleStore()
    service = ScheduleApplicationService(
        authorizer=authz,
        schedule_store=schedules,
        managed_service=managed,
        durable_work=durable,
    )
    schedule = service.create(
        ctx,
        "pipeline-058",
        spec=ScheduleSpec(kind="interval", interval_seconds=60),
    )
    assert schedule.execution_route == route_at_creation
    assert schedule.to_dict()["execution_route"] == route_at_creation

    managed.execution_route = route_after_change
    submission_id, _fingerprint = managed.submit_scheduled_run(
        ctx, schedule, "2026-10-11T12:00:00Z"
    )
    accepted = durable.get_submission(ctx, submission_id)
    assert accepted.execution_route == route_at_creation


def test_managed_schedule_route_transfer_waits_for_drain_and_survives_reload(
    tmp_path: Path,
) -> None:
    route_a = "prefect:" + "e" * 64
    route_b = "prefect:" + "f" * 64
    ctx, authz, durable, managed = _managed_service(tmp_path, execution_route=route_a)
    schedules = MemoryScheduleStore()
    service = ScheduleApplicationService(
        authorizer=authz,
        schedule_store=schedules,
        managed_service=managed,
        durable_work=durable,
        clock=lambda: datetime(2026, 10, 11, 12, 0, tzinfo=UTC),
    )
    original = service.create(
        ctx,
        "pipeline-058",
        spec=ScheduleSpec(kind="interval", interval_seconds=60),
    )
    original_firing, created = service.trigger(
        ctx,
        original.schedule_id,
        nominal_fire_time=datetime(2026, 10, 11, 12, 0, tzinfo=UTC),
    )
    assert created is True
    assert original_firing.submission_id is not None
    original_submission = durable.get_submission(ctx, original_firing.submission_id)
    assert original_submission.execution_route == route_a

    managed.execution_route = route_b
    with pytest.raises(ControlPlaneError) as active_transfer:
        service.amend(
            ctx,
            original.schedule_id,
            expected_revision_id=original.revision_id,
            spec=ScheduleSpec(kind="interval", interval_seconds=120),
            transfer_execution_route=True,
        )
    assert active_transfer.value.extensions.get("reason") == "active_firing"

    lease = durable.acquire_lease(
        ctx,
        original_firing.submission_id,
        owner_id="schedule-drain-test",
        ttl_seconds=60,
    )
    attempt = durable.start_attempt(
        ctx,
        original_firing.submission_id,
        owner_id=lease.owner_id,
        fencing_token=lease.fencing_token,
    )
    durable.finish_attempt(
        ctx,
        attempt.attempt_id,
        owner_id=lease.owner_id,
        fencing_token=lease.fencing_token,
        status="completed",
    )

    amended = service.amend(
        ctx,
        original.schedule_id,
        expected_revision_id=original.revision_id,
        spec=ScheduleSpec(kind="interval", interval_seconds=120),
        transfer_execution_route=True,
    )
    assert amended.revision_id != original.revision_id
    assert amended.execution_route == route_b
    assert amended.policy_fingerprint != original.policy_fingerprint
    assert amended.metadata["amends_revision_id"] == original.revision_id
    assert amended.metadata["execution_route_amended_from"] == route_a
    assert durable.get_submission(
        ctx, original_firing.submission_id
    ).execution_route == (route_a)

    next_firing, next_created = service.trigger(
        ctx,
        original.schedule_id,
        nominal_fire_time=datetime(2026, 10, 11, 12, 2, tzinfo=UTC),
    )
    assert next_created is True
    assert next_firing.revision_id == amended.revision_id
    assert next_firing.submission_id is not None
    next_submission = durable.get_submission(ctx, next_firing.submission_id)
    assert next_submission.execution_route == route_b

    restarted_store = MemoryScheduleStore()
    restarted_store.load(schedules.dump())
    restored = restarted_store.get(ctx, original.schedule_id)
    assert restored.revision_id == amended.revision_id
    assert restored.execution_route == route_b
    assert restored.policy_fingerprint == amended.policy_fingerprint
    prior_firing, next_persisted_firing = restarted_store.list_firings(
        ctx, original.schedule_id
    )
    assert prior_firing.revision_id == original.revision_id
    assert prior_firing.submission_id == original_firing.submission_id
    assert next_persisted_firing.revision_id == amended.revision_id


def test_managed_schedule_duplicate_firing_reuses_one_accepted_submission(
    tmp_path: Path,
) -> None:
    route_at_creation = "prefect:" + "8" * 64
    route_after_change = "prefect:" + "9" * 64
    ctx, authz, durable, managed = _managed_service(
        tmp_path, execution_route=route_at_creation
    )
    schedule_store = MemoryScheduleStore()
    service = ScheduleApplicationService(
        authorizer=authz,
        schedule_store=schedule_store,
        managed_service=managed,
        durable_work=durable,
    )
    schedule = service.create(
        ctx,
        "pipeline-058",
        spec=ScheduleSpec(kind="interval", interval_seconds=60),
    )
    nominal_fire_time = datetime(2026, 10, 11, 16, 0, tzinfo=UTC)

    first, first_created = service.trigger(
        ctx, schedule.schedule_id, nominal_fire_time=nominal_fire_time
    )
    managed.execution_route = route_after_change
    replay, replay_created = service.trigger(
        ctx, schedule.schedule_id, nominal_fire_time=nominal_fire_time
    )

    assert first_created is True
    assert replay_created is False
    assert replay.firing_id == first.firing_id
    assert replay.submission_id == first.submission_id
    assert len(schedule_store.list_firings(ctx, schedule.schedule_id)) == 1
    accepted = durable.get_submission(ctx, first.submission_id)
    assert accepted.execution_route == route_at_creation
    assert len(durable.list_attempts(ctx, first.submission_id)) == 0


def test_prefect_process_deployment_registration_is_versioned_and_idempotent(
    tmp_path: Path,
) -> None:
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.actions import WorkPoolCreate
    from prefect.testing.utilities import prefect_test_harness

    spec = _spec(f"phase058-{uuid4().hex[:10]}")
    registrar = PrefectDeploymentRegistrar()

    async def scenario() -> None:
        async with get_client() as client:
            await client.create_work_pool(
                WorkPoolCreate(name=spec.work_pool_name, type="process")
            )
        preview = await registrar.preview(spec)
        assert preview["deployment_exists"] is False
        binding = await registrar.register(
            spec, expected_fingerprint=preview["spec"]["fingerprint"]
        )
        repeated = await registrar.register(spec, expected_fingerprint=spec.fingerprint)
        assert repeated == binding

        async with get_client() as client:
            remote = await client.read_deployment(binding.deployment_id)
        assert binding.verify_remote_deployment(remote)
        assert remote.paused is False
        assert remote.schedules == []
        assert remote.parameters == {}
        assert remote.job_variables == {"env": binding.to_environment()}

        ready_preview = await registrar.preview(spec)
        assert ready_preview["binding_ready"] is True
        assert ready_preview["paused"] is False
        assert ready_preview["execution_route"] == binding.execution_route
        assert ready_preview["job_variables"] == ["env"]
        assert "ETLANTIC_PREFECT_ROUTE_ID" in ready_preview["environment_variables"]

        ctx, _authz, durable, managed = _managed_service(
            tmp_path, execution_route=binding.execution_route
        )
        receipt = managed.submit_run(
            ctx, "pipeline-058", idempotency_key="prefect-dispatch-058"
        )
        dispatcher = PrefectDispatcher(
            backend=SimpleNamespace(durable_work=durable),  # type: ignore[arg-type]
            context=ctx,
            binding=binding,
            owner_id="phase058-dispatcher",
        )
        dispatched = await dispatcher.tick(limit=10)
        assert len(dispatched) == 1
        assert dispatched[0]["status"] == "dispatched"
        assert dispatched[0]["prefect_flow_run_id"]
        assert dispatched[0]["queue_age_seconds"] is not None
        assert dispatcher.status().ready is True
        stored_dispatch = durable.get_dispatch(ctx, receipt.submission_id)
        assert stored_dispatch.status == "dispatched"
        assert (
            stored_dispatch.prefect_flow_run_id == dispatched[0]["prefect_flow_run_id"]
        )

        from etlantic_prefect.worker import _remote_flow_run_observation

        observation = _remote_flow_run_observation(stored_dispatch, binding)
        assert observation["flow_run_id"] == stored_dispatch.prefect_flow_run_id
        assert observation["status"] not in {"missing", "unavailable"}
        async with get_client() as client:
            remote_run = await client.read_flow_run(
                UUID(str(stored_dispatch.prefect_flow_run_id))
            )
        assert remote_run.deployment_id == binding.deployment_id

        from prefect.client.schemas.actions import DeploymentUpdate

        tampered_environment = {
            **binding.to_environment(),
            "UNTRUSTED_OVERRIDE": "unexpected",
        }
        async with get_client() as client:
            await client.update_deployment(
                binding.deployment_id,
                DeploymentUpdate(job_variables={"env": tampered_environment}),
            )
        with pytest.raises(RuntimeError, match="binding"):
            await registrar.preview(spec)
        async with get_client() as client:
            await client.update_deployment(
                binding.deployment_id,
                DeploymentUpdate(job_variables={"env": binding.to_environment()}),
            )
        with pytest.raises(ValueError, match="fingerprint changed"):
            await registrar.register(spec, expected_fingerprint="0" * 64)

    with prefect_test_harness():
        asyncio.run(scenario())


def test_deployment_retirement_drains_route_and_retains_binding(
    tmp_path: Path,
) -> None:
    from etlantic_prefect.worker import managed_execution_flow

    spec = _spec("retirement")
    binding = ManagedDeploymentBinding(spec=spec, deployment_id=uuid4())
    route = binding.execution_route
    ctx, authz, durable, service = _managed_service(tmp_path, execution_route=route)
    authz.grant(ctx, "execution.route.manage")
    accepted = service.submit_run(
        ctx, "pipeline-058", idempotency_key="phase058-retirement-accepted"
    )
    pending_dispatch = durable.prepare_dispatch(ctx, accepted.submission_id)
    assert pending_dispatch.status == "pending"
    deployment = SimpleNamespace(
        id=binding.deployment_id,
        name=spec.deployment_name,
        version=spec.fingerprint,
        work_pool_name=spec.work_pool_name,
        entrypoint="etlantic_prefect.worker.managed_execution_flow",
        path=None,
        parameters={},
        enforce_parameter_schema=True,
        paused=False,
        schedules=[],
        tags=list(spec.tags),
        job_variables={"env": binding.to_environment()},
        parameter_openapi_schema=managed_execution_flow.parameters.model_dump(
            mode="json", exclude_unset=True
        ),
    )

    class _RetirementClient:
        def __init__(self) -> None:
            self.active_runs: list[object] = []
            self.pause_calls = 0
            self.resume_calls = 0

        async def __aenter__(self) -> _RetirementClient:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def read_deployment(self, _deployment_id: UUID) -> Any:
            return deployment

        async def read_work_pool(self, _pool_name: str) -> Any:
            return SimpleNamespace(type="process")

        async def read_flow_runs(self, **_kwargs: object) -> list[object]:
            return list(self.active_runs[:1])

        async def pause_deployment(self, _deployment_id: UUID) -> None:
            self.pause_calls += 1
            deployment.paused = True

        async def resume_deployment(self, _deployment_id: UUID) -> None:
            self.resume_calls += 1
            deployment.paused = False

    client = _RetirementClient()
    registrar = PrefectDeploymentRegistrar(client_factory=lambda: client)
    backend = cast(ManagedBackend, SimpleNamespace(managed_service=service))

    active = service.get_execution_route_lifecycle(ctx, route)
    assert active["status"] == "active"
    draining = service.transition_execution_route_lifecycle(
        ctx, route, expected_revision=active["revision"], status="draining"
    )
    assert draining["workload"]["active_submissions"] == 1
    with pytest.raises(ControlPlaneError) as blocked:
        service.transition_execution_route_lifecycle(
            ctx,
            route,
            expected_revision=draining["revision"],
            status="retired",
        )
    assert blocked.value.extensions["reason"] == "execution_route_not_drained"

    # A caller can recover the existing acceptance during drain, but new work
    # cannot enter the route. Cancellation acknowledges its durable outbox.
    replay = service.submit_run(
        ctx, "pipeline-058", idempotency_key="phase058-retirement-accepted"
    )
    assert replay.submission_id == accepted.submission_id
    with pytest.raises(ControlPlaneError) as denied:
        service.submit_run(
            ctx, "pipeline-058", idempotency_key="phase058-retirement-new"
        )
    assert denied.value.extensions["reason"] == "execution_route_draining"
    durable.cancel_submission(ctx, accepted.submission_id)
    durable.reconcile_cancelled_submissions(ctx, limit=10)
    assert durable.get_dispatch(ctx, accepted.submission_id).status == "cancelled"
    assert service.get_execution_route_lifecycle(ctx, route)["workload"]["drained"]

    async def scenario() -> None:
        client.active_runs.append(object())
        pending = await registrar.retire(
            binding,
            backend=backend,
            context=ctx,
            expected_fingerprint=binding.fingerprint,
        )
        assert pending["status"] == "draining"
        assert pending["reason"] == "remote_flow_runs_remain"
        assert pending["deployment_paused"] is False
        assert client.pause_calls == 0

        client.active_runs.clear()
        retired = await registrar.retire(
            binding,
            backend=backend,
            context=ctx,
            expected_fingerprint=binding.fingerprint,
        )
        assert retired["status"] == "retired"
        assert retired["deployment_paused"] is True
        assert retired["deployment_retained"] is True
        assert client.pause_calls == 1
        retired_replay = service.submit_run(
            ctx, "pipeline-058", idempotency_key="phase058-retirement-accepted"
        )
        assert retired_replay.submission_id == accepted.submission_id
        with pytest.raises(ControlPlaneError) as retired_denial:
            service.submit_run(
                ctx,
                "pipeline-058",
                idempotency_key="phase058-retirement-after-retire",
            )
        assert retired_denial.value.extensions["reason"] == "execution_route_retired"

        restored = await registrar.reactivate(
            binding,
            backend=backend,
            context=ctx,
            expected_fingerprint=binding.fingerprint,
        )
        assert restored["status"] == "active"
        assert client.resume_calls == 1

    asyncio.run(scenario())
    state = durable.get_execution_route_state(ctx, route)
    assert [item.to_status for item in state.history] == [
        "draining",
        "retired",
        "active",
    ]
    assert state.history[0].principal_subject == ctx.principal.subject
    assert service.events is not None
    lifecycle_events = [
        event
        for event in service.events.list_after_cursor(ctx, None, limit=20)
        if event.kind == "execution.route_lifecycle_changed"
    ]
    assert len(lifecycle_events) == 3


def test_schedule_route_reservation_blocks_retirement_until_deleted(
    tmp_path: Path,
) -> None:
    route = "prefect:" + "1" * 64
    ctx, authz, durable, managed = _managed_service(tmp_path, execution_route=route)
    authz.grant(ctx, "execution.route.manage")
    schedules = MemoryScheduleStore()
    service = ScheduleApplicationService(
        authorizer=authz,
        schedule_store=schedules,
        managed_service=managed,
        durable_work=durable,
    )
    schedule = service.create(
        ctx,
        "pipeline-058",
        spec=ScheduleSpec(kind="interval", interval_seconds=60),
    )
    assert durable.execution_route_reference_counts(ctx, route) == {
        "canonical_submissions": 0,
        "schedule_reservations": 1,
    }

    lifecycle = managed.get_execution_route_lifecycle(ctx, route)
    draining = managed.transition_execution_route_lifecycle(
        ctx, route, expected_revision=lifecycle["revision"], status="draining"
    )
    with pytest.raises(ControlPlaneError) as retirement_blocked:
        managed.transition_execution_route_lifecycle(
            ctx,
            route,
            expected_revision=draining["revision"],
            status="retired",
        )
    assert retirement_blocked.value.extensions["reason"] == (
        "execution_route_referenced"
    )
    with pytest.raises(ControlPlaneError) as admission_blocked:
        service.create(
            ctx,
            "pipeline-058",
            spec=ScheduleSpec(kind="interval", interval_seconds=60),
        )
    assert admission_blocked.value.extensions["reason"] == "execution_route_draining"

    deleted = service.delete(ctx, schedule.schedule_id)
    assert deleted.status == "deleted"
    assert (
        durable.execution_route_reference_counts(ctx, route)["schedule_reservations"]
        == 0
    )
    retired = managed.transition_execution_route_lifecycle(
        ctx, route, expected_revision=draining["revision"], status="retired"
    )
    assert retired["status"] == "retired"


def test_prefect_deployment_cleanup_fences_reactivation_and_recovers_lost_delete(
    tmp_path: Path,
) -> None:
    from prefect.exceptions import ObjectNotFound

    from etlantic_prefect.worker import managed_execution_flow

    spec = _spec("cleanup")
    binding = ManagedDeploymentBinding(spec=spec, deployment_id=uuid4())
    ctx, authz, durable, service = _managed_service(
        tmp_path, execution_route=binding.execution_route
    )
    authz.grant(ctx, "execution.route.manage")
    deployment: Any | None = SimpleNamespace(
        id=binding.deployment_id,
        name=spec.deployment_name,
        version=spec.fingerprint,
        work_pool_name=spec.work_pool_name,
        entrypoint="etlantic_prefect.worker.managed_execution_flow",
        path=None,
        parameters={},
        enforce_parameter_schema=True,
        paused=True,
        schedules=[],
        tags=list(spec.tags),
        job_variables={"env": binding.to_environment()},
        parameter_openapi_schema=managed_execution_flow.parameters.model_dump(
            mode="json", exclude_unset=True
        ),
    )

    class _CleanupClient:
        def __init__(self) -> None:
            self.delete_calls = 0
            self.read_calls = 0
            self.lose_delete_response = True

        async def __aenter__(self) -> _CleanupClient:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def read_deployment(self, _deployment_id: UUID) -> Any:
            self.read_calls += 1
            if deployment is None:
                raise ObjectNotFound(ConnectionError("deployment was deleted"))
            return deployment

        async def read_work_pool(self, _pool_name: str) -> Any:
            return SimpleNamespace(type="process")

        async def read_flow_runs(self, **_kwargs: object) -> list[object]:
            return []

        async def pause_deployment(self, _deployment_id: UUID) -> None:
            assert deployment is not None
            deployment.paused = True

        async def delete_deployment(self, _deployment_id: UUID) -> None:
            nonlocal deployment
            self.delete_calls += 1
            deployment = None
            if self.lose_delete_response:
                self.lose_delete_response = False
                raise ConnectionError("Prefect delete response was lost")

    client = _CleanupClient()
    registrar = PrefectDeploymentRegistrar(client_factory=lambda: client)
    backend = cast(
        ManagedBackend,
        SimpleNamespace(managed_service=service, schedule_store=MemoryScheduleStore()),
    )
    active = service.get_execution_route_lifecycle(ctx, binding.execution_route)
    draining = service.transition_execution_route_lifecycle(
        ctx,
        binding.execution_route,
        expected_revision=active["revision"],
        status="draining",
    )
    retired = service.transition_execution_route_lifecycle(
        ctx,
        binding.execution_route,
        expected_revision=draining["revision"],
        status="retired",
    )
    retired_at = datetime.fromisoformat(retired["changed_at"])
    assert retired["references"] == {
        "canonical_submissions": 0,
        "schedule_reservations": 0,
    }

    async def scenario() -> None:
        retention = await registrar.cleanup(
            binding,
            backend=backend,
            context=ctx,
            expected_fingerprint=binding.fingerprint,
            now=retired_at + timedelta(days=30) - timedelta(seconds=1),
        )
        assert retention["status"] == "retired"
        assert retention["reason"] == "retention_period_not_elapsed"
        assert client.read_calls == 0

        with pytest.raises(ConnectionError, match="response was lost"):
            await registrar.cleanup(
                binding,
                backend=backend,
                context=ctx,
                expected_fingerprint=binding.fingerprint,
                now=retired_at + timedelta(days=30),
            )
        pending = service.get_execution_route_lifecycle(ctx, binding.execution_route)
        assert pending["status"] == "cleanup_pending"
        calls_before_reactivation = client.read_calls
        with pytest.raises(ControlPlaneError) as reactivation_blocked:
            await registrar.reactivate(
                binding,
                backend=backend,
                context=ctx,
                expected_fingerprint=binding.fingerprint,
            )
        assert reactivation_blocked.value.extensions["reason"] == (
            "execution_route_cleanup_started"
        )
        assert client.read_calls == calls_before_reactivation

        cleaned = await registrar.cleanup(
            binding,
            backend=backend,
            context=ctx,
            expected_fingerprint=binding.fingerprint,
        )
        assert cleaned["status"] == "cleaned"
        assert cleaned["deployment_deleted"] is True
        assert client.delete_calls == 1

    asyncio.run(scenario())
    assert [
        transition.to_status
        for transition in durable.get_execution_route_state(
            ctx, binding.execution_route
        ).history
    ] == ["draining", "retired", "cleanup_pending", "cleaned"]


def test_postgresql_multiprocess_retirement_and_revision_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    postgres_url = os.environ.get("ETLANTIC_CP_TEST_URL")
    if not postgres_url:
        pytest.skip("set ETLANTIC_CP_TEST_URL for live route retirement qualification")

    from prefect.client.orchestration import PrefectClient
    from prefect.client.schemas.actions import WorkPoolCreate
    from prefect.exceptions import ObjectNotFound
    from sqlalchemy import create_engine, text

    from etlantic import Profile
    from etlantic.control_plane import MemoryAuthorizer
    from etlantic.registry import PlanningContext
    from etlantic_sqlmodel.managed import SQLModelBackendConfig, create_managed_backend
    from etlantic_sqlmodel.migrations import upgrade

    scope = uuid4().hex
    ctx = ControlPlaneContext(
        principal=Principal(subject=f"retirement-{scope}", issuer="phase058-tests"),
        tenant=TenantRef(tenant_id=f"tenant-{scope}"),
        workspace=WorkspaceRef(
            tenant_id=f"tenant-{scope}", workspace_id=f"workspace-{scope}"
        ),
        environment=EnvironmentRef(name="test"),
        security_domain=SecurityDomain(domain_id="default"),
    )
    store_id = f"phase058-route-retirement-{scope}"
    artifact_root = tmp_path / "artifacts"
    engine = create_engine(postgres_url, pool_pre_ping=True)
    try:
        upgrade(engine)
    finally:
        engine.dispose()

    pref_db_name = f"prefect_058_retire_{scope[:16]}"
    with _prefect_postgres_server(
        postgres_url,
        database_name=pref_db_name,
        prefect_home=tmp_path / "prefect-home",
    ) as (prefect_api_url, _restart_prefect_server, _stop_prefect_server):
        monkeypatch.setenv("PREFECT_API_URL", prefect_api_url)
        spec_v1 = ManagedDeploymentSpec.from_current_runtime(
            name=f"phase058-retire-{scope[:10]}",
            work_pool_name=f"phase058-retire-pool-{scope[:10]}",
            worker_backend_entry_point="phase058_process_backend",
            lockfile_sha256=hashlib.sha256(
                (Path(__file__).parents[2] / "uv.lock").read_bytes()
            ).hexdigest(),
        )
        spec_v2 = replace(
            spec_v1,
            lockfile_sha256=hashlib.sha256(
                f"phase058-retirement-revision-two-{scope}".encode()
            ).hexdigest(),
        )
        registrar = PrefectDeploymentRegistrar(
            client_factory=lambda: PrefectClient(prefect_api_url)
        )

        async def register_revisions() -> tuple[
            ManagedDeploymentBinding, ManagedDeploymentBinding
        ]:
            async with PrefectClient(prefect_api_url) as client:
                await client.create_work_pool(
                    WorkPoolCreate(name=spec_v1.work_pool_name, type="process")
                )
            preview_v1 = await registrar.preview(spec_v1)
            binding_v1 = await registrar.register(
                spec_v1, expected_fingerprint=preview_v1["spec"]["fingerprint"]
            )
            preview_v2 = await registrar.preview(spec_v2)
            binding_v2 = await registrar.register(
                spec_v2, expected_fingerprint=preview_v2["spec"]["fingerprint"]
            )
            assert binding_v1.deployment_id != binding_v2.deployment_id
            assert binding_v1.execution_route != binding_v2.execution_route
            return binding_v1, binding_v2

        binding_v1, binding_v2 = asyncio.run(register_revisions())

        async def verify_registered_revisions() -> tuple[Any, Any]:
            async with PrefectClient(prefect_api_url) as client:
                return (
                    await client.read_deployment(binding_v1.deployment_id),
                    await client.read_deployment(binding_v2.deployment_id),
                )

        v1_before_workers, v2_before_workers = asyncio.run(
            verify_registered_revisions()
        )
        assert binding_v1.verify_remote_deployment(
            v1_before_workers, require_active=False
        )
        assert binding_v2.verify_remote_deployment(v2_before_workers)
        authorizer = MemoryAuthorizer()
        for action in (
            "definition.write",
            "definition.read",
            "definition.validate",
            "definition.plan",
            "run.submit",
            "run.cancel",
            "run.read",
            "run.report",
            "execution.route.manage",
        ):
            authorizer.grant(ctx, action)

        def planning_context_factory(
            _context: ControlPlaneContext, effective_profile: Profile
        ) -> PlanningContext:
            return PlanningContext.create(profile=effective_profile)

        backend_config = SQLModelBackendConfig(
            database_url=postgres_url,
            store_id=store_id,
            profile=Profile(
                name="phase058-route-retirement",
                security_mode="development",
                plugin_allowlist={"etlantic": None},
            ),
            artifact_root=str(artifact_root),
            execution_route=binding_v1.execution_route,
        )
        backend = create_managed_backend(
            backend_config,
            authorizer=authorizer,
            planning_context_factory=planning_context_factory,
        )
        reopened: ManagedBackend | None = None
        backend_open = True
        try:
            backend.managed_service.register_definition(
                ctx,
                "phase058-retirement-pipeline",
                pipeline_to_dict(definition_from_pipeline(_ManagedPipeline)),
            )
            accepted_receipt = backend.managed_service.submit_run(
                ctx,
                "phase058-retirement-pipeline",
                idempotency_key=f"phase058-retirement-accepted-{scope}",
            )
            accepted = backend.durable_work.get_submission(
                ctx, accepted_receipt.submission_id
            )
            assert accepted.execution_route == binding_v1.execution_route
            active = backend.managed_service.get_execution_route_lifecycle(
                ctx, binding_v1.execution_route
            )
            draining = backend.managed_service.transition_execution_route_lifecycle(
                ctx,
                binding_v1.execution_route,
                expected_revision=active["revision"],
                status="draining",
            )
            assert draining["status"] == "draining"
            assert draining["workload"]["active_submissions"] == 1
            with pytest.raises(ControlPlaneError) as denied_during_drain:
                backend.managed_service.submit_run(
                    ctx,
                    "phase058-retirement-pipeline",
                    idempotency_key=f"phase058-retirement-new-during-drain-{scope}",
                )
            assert denied_during_drain.value.extensions["reason"] == (
                "execution_route_draining"
            )
            pending_retirement = asyncio.run(
                registrar.retire(
                    binding_v1,
                    backend=backend,
                    context=ctx,
                    expected_fingerprint=binding_v1.fingerprint,
                )
            )
            assert pending_retirement["reason"] == "canonical_work_remains"
            assert pending_retirement["deployment_paused"] is False

            _restart_prefect_server()

            async def read_revisions_after_api_restart() -> tuple[Any, Any]:
                async with PrefectClient(prefect_api_url) as client:
                    return (
                        await client.read_deployment(binding_v1.deployment_id),
                        await client.read_deployment(binding_v2.deployment_id),
                    )

            restarted_v1, restarted_v2 = asyncio.run(read_revisions_after_api_restart())
            assert binding_v1.verify_remote_deployment(restarted_v1)
            assert binding_v2.verify_remote_deployment(restarted_v2)
            assert (
                backend.managed_service.get_execution_route_lifecycle(
                    ctx, binding_v1.execution_route
                )["status"]
                == "draining"
            )
            with pytest.raises(ControlPlaneError) as denied_after_api_restart:
                backend.managed_service.submit_run(
                    ctx,
                    "phase058-retirement-pipeline",
                    idempotency_key=f"phase058-retirement-after-api-restart-{scope}",
                )
            assert denied_after_api_restart.value.extensions["reason"] == (
                "execution_route_draining"
            )

            cancellation = backend.managed_service.cancel_run(
                ctx, str(accepted_receipt.resource_id)
            )
            assert cancellation["status"] == "cancel_requested"
            backend.durable_work.reconcile_cancelled_submissions(ctx, limit=10)
            assert backend.managed_service.get_execution_route_lifecycle(
                ctx, binding_v1.execution_route
            )["workload"]["drained"]

            process_context = get_context("spawn")
            crash_barrier = process_context.Barrier(2)
            crash_results = process_context.Queue()
            crash_marker = tmp_path / f"phase058-retirement-crash-{scope}"
            crash_process = process_context.Process(
                target=_retire_route_in_process,
                args=(
                    postgres_url,
                    store_id,
                    str(artifact_root),
                    prefect_api_url,
                    ctx,
                    binding_v1,
                    crash_barrier,
                    crash_results,
                    str(crash_marker),
                ),
                name=f"phase058-retire-crash-{scope[:8]}",
            )
            crash_process.start()
            crash_barrier.wait(timeout=60)
            _wait_for_marker(crash_marker)
            crash_process.join(timeout=30)
            assert not crash_process.is_alive()
            assert crash_process.exitcode == 81
            interrupted_lifecycle = (
                backend.managed_service.get_execution_route_lifecycle(
                    ctx, binding_v1.execution_route
                )
            )
            assert interrupted_lifecycle["status"] == "draining"

            async def read_paused_revision_after_crash() -> Any:
                async with PrefectClient(prefect_api_url) as client:
                    return await client.read_deployment(binding_v1.deployment_id)

            paused_after_crash = asyncio.run(read_paused_revision_after_crash())
            assert paused_after_crash.paused is True

            _restart_prefect_server()

            async def read_paused_revision_after_api_restart() -> tuple[Any, Any]:
                async with PrefectClient(prefect_api_url) as client:
                    return (
                        await client.read_deployment(binding_v1.deployment_id),
                        await client.read_deployment(binding_v2.deployment_id),
                    )

            paused_v1_after_api_restart, active_v2_after_api_restart = asyncio.run(
                read_paused_revision_after_api_restart()
            )
            assert binding_v1.verify_remote_deployment(
                paused_v1_after_api_restart, require_active=False
            )
            assert paused_v1_after_api_restart.paused is True
            assert binding_v2.verify_remote_deployment(active_v2_after_api_restart)
            assert (
                backend.managed_service.get_execution_route_lifecycle(
                    ctx, binding_v1.execution_route
                )["status"]
                == "draining"
            )
            with pytest.raises(ControlPlaneError) as denied_after_paused_api_restart:
                backend.managed_service.submit_run(
                    ctx,
                    "phase058-retirement-pipeline",
                    idempotency_key=(
                        f"phase058-retirement-after-paused-api-restart-{scope}"
                    ),
                )
            assert denied_after_paused_api_restart.value.extensions["reason"] == (
                "execution_route_draining"
            )
            recovered_retirement = asyncio.run(
                registrar.retire(
                    binding_v1,
                    backend=backend,
                    context=ctx,
                    expected_fingerprint=binding_v1.fingerprint,
                )
            )
            assert recovered_retirement["status"] == "retired"
            assert recovered_retirement["deployment_paused"] is True

            barrier = process_context.Barrier(3)
            results = process_context.Queue()
            retire_args = (
                postgres_url,
                store_id,
                str(artifact_root),
                prefect_api_url,
                ctx,
                binding_v1,
                barrier,
                results,
            )
            processes = [
                process_context.Process(
                    target=_retire_route_in_process,
                    args=retire_args,
                    name=f"phase058-retire-{index}-{scope[:8]}",
                )
                for index in range(2)
            ]
            for process in processes:
                process.start()
            barrier.wait(timeout=60)
            for process in processes:
                process.join(timeout=90)
                assert not process.is_alive()
                assert process.exitcode == 0
            retire_results = [results.get(timeout=5) for _ in processes]
            assert all(result.get("error_type") is None for result in retire_results), (
                repr(retire_results)
            )
            assert all(result["status"] == "retired" for result in retire_results)
            assert all(result["deployment_paused"] is True for result in retire_results)
            assert all(
                result["deployment_retained"] is True for result in retire_results
            )

            retired = backend.managed_service.get_execution_route_lifecycle(
                ctx, binding_v1.execution_route
            )
            assert retired["status"] == "retired"
            assert [item["to_status"] for item in retired["history"]] == [
                "draining",
                "retired",
            ]
            assert (
                backend.durable_work.get_submission(
                    ctx, accepted_receipt.submission_id
                ).execution_route
                == binding_v1.execution_route
            )

            async def read_retired_revisions() -> tuple[Any, Any]:
                async with PrefectClient(prefect_api_url) as client:
                    return (
                        await client.read_deployment(binding_v1.deployment_id),
                        await client.read_deployment(binding_v2.deployment_id),
                    )

            retired_remote, v2_remote = asyncio.run(read_retired_revisions())
            assert binding_v1.verify_remote_deployment(
                retired_remote, require_active=False
            )
            assert retired_remote.paused is True
            assert binding_v2.verify_remote_deployment(v2_remote)

            backend.close()
            backend_open = False
            reopened = create_managed_backend(
                backend_config,
                authorizer=authorizer,
                planning_context_factory=planning_context_factory,
            )
            persisted_retirement = (
                reopened.managed_service.get_execution_route_lifecycle(
                    ctx, binding_v1.execution_route
                )
            )
            assert persisted_retirement["status"] == "retired"
            assert (
                reopened.durable_work.get_submission(
                    ctx, accepted_receipt.submission_id
                ).execution_route
                == binding_v1.execution_route
            )
            rollback_binding = asyncio.run(
                registrar.register(spec_v1, expected_fingerprint=spec_v1.fingerprint)
            )
            assert rollback_binding == binding_v1
            rollback = asyncio.run(
                registrar.reactivate(
                    binding_v1,
                    backend=reopened,
                    context=ctx,
                    expected_fingerprint=binding_v1.fingerprint,
                )
            )
            assert rollback["status"] == "active"
            restored_lifecycle = reopened.managed_service.get_execution_route_lifecycle(
                ctx, binding_v1.execution_route
            )
            assert [item["to_status"] for item in restored_lifecycle["history"]] == [
                "draining",
                "retired",
                "active",
            ]

            async def read_rolled_back_revisions() -> tuple[Any, Any]:
                async with PrefectClient(prefect_api_url) as client:
                    return (
                        await client.read_deployment(binding_v1.deployment_id),
                        await client.read_deployment(binding_v2.deployment_id),
                    )

            restored_remote, retained_v2_remote = asyncio.run(
                read_rolled_back_revisions()
            )
            assert binding_v1.verify_remote_deployment(restored_remote)
            assert binding_v2.verify_remote_deployment(retained_v2_remote)

            orphan_retirement = asyncio.run(
                registrar.retire(
                    binding_v2,
                    backend=reopened,
                    context=ctx,
                    expected_fingerprint=binding_v2.fingerprint,
                )
            )
            assert orphan_retirement["status"] == "retired"
            orphan_cleanup = asyncio.run(
                registrar.cleanup(
                    binding_v2,
                    backend=reopened,
                    context=ctx,
                    expected_fingerprint=binding_v2.fingerprint,
                    minimum_retention_seconds=0,
                )
            )
            assert orphan_cleanup["status"] == "cleaned"
            assert orphan_cleanup["deployment_deleted"] is True

            async def verify_orphan_deployment_deleted() -> None:
                async with PrefectClient(prefect_api_url) as client:
                    with pytest.raises(ObjectNotFound):
                        await client.read_deployment(binding_v2.deployment_id)

            asyncio.run(verify_orphan_deployment_deleted())
        finally:
            if backend_open:
                backend.close()
            if reopened is not None:
                reopened.close()
            cleanup_engine = create_engine(postgres_url, pool_pre_ping=True)
            try:
                with cleanup_engine.begin() as connection:
                    for table in (
                        "cp_event_idempotency",
                        "cp_events",
                        "cp_submissions",
                        "cp_definitions",
                        "cp_run_reports",
                        "cp_registry_aliases",
                        "cp_registry_promotions",
                        "cp_registry_revisions",
                        "cp_registry_environments",
                        "cp_registry_logical",
                        "cp_registry_workspaces",
                    ):
                        connection.execute(
                            text(
                                f"DELETE FROM {table} WHERE tenant_id = :tenant "
                                "AND workspace_id = :workspace"
                            ),
                            {
                                "tenant": ctx.tenant.tenant_id,
                                "workspace": ctx.workspace.workspace_id,
                            },
                        )
                    connection.execute(
                        text(
                            "DELETE FROM cp_registry_tenants WHERE tenant_id = :tenant"
                        ),
                        {"tenant": ctx.tenant.tenant_id},
                    )
                    for table in (
                        "cp_durable_submission_entity",
                        "cp_durable_outbox_entity",
                        "cp_durable_snapshot",
                        "cp_cp4_governance_snapshot",
                    ):
                        connection.execute(
                            text(f"DELETE FROM {table} WHERE store_id = :store_id"),
                            {"store_id": store_id},
                        )
            finally:
                cleanup_engine.dispose()


def test_managed_deployment_rejects_native_prefect_schedules() -> None:
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.actions import WorkPoolCreate
    from prefect.client.schemas.schedules import IntervalSchedule
    from prefect.testing.utilities import prefect_test_harness

    spec = _spec(f"phase058-native-schedule-{uuid4().hex[:10]}")
    registrar = PrefectDeploymentRegistrar()

    async def scenario() -> None:
        async with get_client() as client:
            await client.create_work_pool(
                WorkPoolCreate(name=spec.work_pool_name, type="process")
            )
        preview = await registrar.preview(spec)
        binding = await registrar.register(
            spec, expected_fingerprint=preview["spec"]["fingerprint"]
        )
        async with get_client() as client:
            await client.create_deployment_schedules(
                binding.deployment_id,
                schedules=[(IntervalSchedule(interval=timedelta(seconds=60)), True)],
            )
        with pytest.raises(RuntimeError, match="deployment"):
            await registrar.preview(spec)

    with prefect_test_harness():
        asyncio.run(scenario())


def test_queued_submission_stays_bound_to_its_deployment_revision(
    tmp_path: Path,
) -> None:
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.actions import WorkPoolCreate
    from prefect.testing.utilities import prefect_test_harness

    spec_v1 = _spec(f"phase058-retained-{uuid4().hex[:10]}")
    spec_v2 = replace(spec_v1, lockfile_sha256="b" * 64)
    registrar = PrefectDeploymentRegistrar()

    async def scenario() -> None:
        async with get_client() as client:
            await client.create_work_pool(
                WorkPoolCreate(name=spec_v1.work_pool_name, type="process")
            )
        preview_v1 = await registrar.preview(spec_v1)
        binding_v1 = await registrar.register(
            spec_v1, expected_fingerprint=preview_v1["spec"]["fingerprint"]
        )
        ctx, _authz, durable, managed = _managed_service(
            tmp_path, execution_route=binding_v1.execution_route
        )
        accepted = managed.submit_run(
            ctx,
            "pipeline-058",
            idempotency_key="queued-before-deployment-revision",
        )
        accepted_record = durable.get_submission(ctx, accepted.submission_id)
        assert accepted_record.execution_route == binding_v1.execution_route

        preview_v2 = await registrar.preview(spec_v2)
        binding_v2 = await registrar.register(
            spec_v2, expected_fingerprint=preview_v2["spec"]["fingerprint"]
        )
        assert binding_v2.deployment_id != binding_v1.deployment_id
        assert binding_v2.execution_route != binding_v1.execution_route
        rollback_binding = await registrar.register(
            spec_v1, expected_fingerprint=spec_v1.fingerprint
        )
        assert rollback_binding == binding_v1
        async with get_client() as client:
            old_deployment = await client.read_deployment(binding_v1.deployment_id)
            new_deployment = await client.read_deployment(binding_v2.deployment_id)
        assert binding_v1.verify_remote_deployment(old_deployment)
        assert binding_v2.verify_remote_deployment(new_deployment)

        new_dispatcher = PrefectDispatcher(
            backend=cast(ManagedBackend, SimpleNamespace(durable_work=durable)),
            context=ctx,
            binding=binding_v2,
            owner_id="phase058-new-revision-dispatcher",
        )
        assert await new_dispatcher.tick(limit=10) == []
        old_dispatcher = PrefectDispatcher(
            backend=cast(ManagedBackend, SimpleNamespace(durable_work=durable)),
            context=ctx,
            binding=binding_v1,
            owner_id="phase058-old-revision-dispatcher",
        )
        dispatched = await old_dispatcher.tick(limit=10)
        assert len(dispatched) == 1
        assert dispatched[0]["submission_id"] == accepted.submission_id
        stored_dispatch = durable.get_dispatch(ctx, accepted.submission_id)
        assert stored_dispatch.execution_route == binding_v1.execution_route
        assert stored_dispatch.status == "dispatched"
        async with get_client() as client:
            remote_run = await client.read_flow_run(
                UUID(str(stored_dispatch.prefect_flow_run_id))
            )
        assert remote_run.deployment_id == binding_v1.deployment_id

    with prefect_test_harness():
        asyncio.run(scenario())


def test_dispatcher_rejects_deployment_drift_before_claiming_work(
    tmp_path: Path,
) -> None:
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.actions import DeploymentUpdate, WorkPoolCreate
    from prefect.testing.utilities import prefect_test_harness

    spec = _spec(f"phase058-drift-{uuid4().hex[:10]}")
    registrar = PrefectDeploymentRegistrar()

    async def scenario() -> None:
        async with get_client() as client:
            await client.create_work_pool(
                WorkPoolCreate(name=spec.work_pool_name, type="process")
            )
        preview = await registrar.preview(spec)
        binding = await registrar.register(
            spec, expected_fingerprint=preview["spec"]["fingerprint"]
        )
        ctx, _authz, durable, managed = _managed_service(
            tmp_path, execution_route=binding.execution_route
        )
        receipt = managed.submit_run(
            ctx, "pipeline-058", idempotency_key="deployment-drift-before-claim"
        )
        dispatcher = PrefectDispatcher(
            backend=cast(ManagedBackend, SimpleNamespace(durable_work=durable)),
            context=ctx,
            binding=binding,
            owner_id="phase058-drift-dispatcher",
        )
        drifted_environment = {
            **binding.to_environment(),
            "UNTRUSTED_OVERRIDE": "unexpected",
        }
        async with get_client() as client:
            await client.update_deployment(
                binding.deployment_id,
                DeploymentUpdate(job_variables={"env": drifted_environment}),
            )

        with pytest.raises(RuntimeError, match="binding"):
            await dispatcher.tick(limit=1)

        candidates = durable.pending_dispatches(
            ctx, execution_route=binding.execution_route, limit=10
        )
        assert [item.submission_id for item in candidates] == [receipt.submission_id]
        assert durable.list_attempts(ctx, receipt.submission_id) == []

    with prefect_test_harness():
        asyncio.run(scenario())


def test_remote_failure_rearm_is_versioned_and_requires_no_etl_attempt(
    tmp_path: Path,
) -> None:
    route = f"prefect:{'a' * 64}"
    ctx, authz, durable, managed = _managed_service(tmp_path, execution_route=route)
    receipt = managed.submit_run(
        ctx, "pipeline-058", idempotency_key="remote-preclaim-failure-rearm"
    )

    first = durable.prepare_dispatch(ctx, receipt.submission_id)
    first_claim = durable.claim_dispatch(
        ctx, receipt.submission_id, owner_id="first-dispatcher"
    )
    assert first_claim is not None
    first_flow_run_id = str(uuid4())
    durable.link_dispatch(
        ctx,
        receipt.submission_id,
        owner_id="first-dispatcher",
        fencing_token=first_claim.lease_fencing_token,
        prefect_flow_run_id=first_flow_run_id,
    )

    rearmed = durable.rearm_dispatch_after_remote_failure(
        ctx,
        receipt.submission_id,
        expected_flow_run_id=first_flow_run_id,
    )
    assert rearmed is not None
    assert rearmed.status == "pending"
    assert rearmed.generation == first.generation + 1
    assert rearmed.creation_key != first.creation_key
    assert rearmed.prefect_flow_run_id is None
    assert durable.prepare_dispatch(ctx, receipt.submission_id) == rearmed

    second_claim = durable.claim_dispatch(
        ctx, receipt.submission_id, owner_id="second-dispatcher"
    )
    assert second_claim is not None
    second_flow_run_id = str(uuid4())
    durable.link_dispatch(
        ctx,
        receipt.submission_id,
        owner_id="second-dispatcher",
        fencing_token=second_claim.lease_fencing_token,
        prefect_flow_run_id=second_flow_run_id,
    )
    lease = durable.acquire_lease(
        ctx, receipt.submission_id, owner_id="worker", ttl_seconds=30
    )
    assert (
        durable.rearm_dispatch_after_remote_failure(
            ctx,
            receipt.submission_id,
            expected_flow_run_id=second_flow_run_id,
        )
        is None
    )

    bounded = managed.submit_run(
        ctx, "pipeline-058", idempotency_key="remote-failure-generation-cap"
    )
    for generation in range(1, 4):
        current = durable.prepare_dispatch(ctx, bounded.submission_id)
        assert current.generation == generation
        claim = durable.claim_dispatch(
            ctx, bounded.submission_id, owner_id=f"generation-{generation}"
        )
        assert claim is not None
        flow_run_id = str(uuid4())
        durable.link_dispatch(
            ctx,
            bounded.submission_id,
            owner_id=f"generation-{generation}",
            fencing_token=claim.lease_fencing_token,
            prefect_flow_run_id=flow_run_id,
        )
        rearmed = durable.rearm_dispatch_after_remote_failure(
            ctx, bounded.submission_id, expected_flow_run_id=flow_run_id
        )
        if generation < 3:
            assert rearmed is not None
            assert rearmed.generation == generation + 1
        else:
            assert rearmed is not None
            assert rearmed.status == "reconciliation_required"
            assert rearmed.generation == generation
            assert rearmed.prefect_flow_run_id == flow_run_id
            assert rearmed.last_error_code == "dispatch_generation_exhausted"

    assert durable.pending_dispatches(ctx, execution_route=route, limit=10) == []
    exhausted = durable.get_dispatch(ctx, bounded.submission_id)
    assert (
        durable.claim_dispatch(
            ctx, bounded.submission_id, owner_id="automatic-retry-after-cap"
        )
        is None
    )
    evidence = "Prefect confirmed the failed flow never reached ETLantic claim."
    with pytest.raises(ControlPlaneError) as unauthorized:
        managed.rearm_exhausted_prefect_dispatch(
            ctx,
            bounded.submission_id,
            expected_generation=exhausted.generation,
            expected_flow_run_id=str(exhausted.prefect_flow_run_id),
            evidence=evidence,
        )
    assert unauthorized.value.status == 404
    authz.grant(ctx, "execution.dispatch.reconcile")
    reconciliation = managed.rearm_exhausted_prefect_dispatch(
        ctx,
        bounded.submission_id,
        expected_generation=exhausted.generation,
        expected_flow_run_id=str(exhausted.prefect_flow_run_id),
        evidence=evidence,
    )
    reauthorized = durable.get_dispatch(ctx, bounded.submission_id)
    evidence_digest = hashlib.sha256(evidence.encode("utf-8")).hexdigest()
    assert reconciliation["dispatch"]["status"] == "pending"
    assert reauthorized.generation == exhausted.generation + 1
    assert reauthorized.creation_key != exhausted.creation_key
    assert len(reauthorized.reconciliation_history) == 1
    audit = reauthorized.reconciliation_history[0]
    assert audit.from_generation == exhausted.generation
    assert audit.to_generation == reauthorized.generation
    assert audit.principal_subject == ctx.principal.subject
    assert audit.evidence_sha256 == evidence_digest
    assert evidence not in json.dumps(reconciliation)
    assert managed.events is not None
    reconciliation_events = [
        event
        for event in managed.events.list_after_cursor(ctx, None, limit=100)
        if event.kind == "execution.dispatch_reconciled"
    ]
    assert len(reconciliation_events) == 1
    event_payload = reconciliation_events[0].payload
    assert event_payload is not None
    assert event_payload["evidence_sha256"] == evidence_digest
    with pytest.raises(ControlPlaneError) as stale:
        managed.rearm_exhausted_prefect_dispatch(
            ctx,
            bounded.submission_id,
            expected_generation=exhausted.generation,
            expected_flow_run_id=str(exhausted.prefect_flow_run_id),
            evidence=evidence,
        )
    assert stale.value.extensions["reason"] == "stale_dispatch_reconciliation"
    durable.start_attempt(
        ctx,
        receipt.submission_id,
        owner_id="worker",
        fencing_token=lease.fencing_token,
    )

    assert (
        durable.rearm_dispatch_after_remote_failure(
            ctx,
            receipt.submission_id,
            expected_flow_run_id=second_flow_run_id,
        )
        is None
    )
    assert (
        durable.rearm_dispatch_after_remote_failure(
            ctx,
            receipt.submission_id,
            expected_flow_run_id=first_flow_run_id,
        )
        is None
    )


def test_exhausted_dispatch_can_be_cancelled_before_route_retirement(
    tmp_path: Path,
) -> None:
    route = f"prefect:{'c' * 64}"
    ctx, _authz, durable, managed = _managed_service(tmp_path, execution_route=route)
    receipt = managed.submit_run(
        ctx, "pipeline-058", idempotency_key="exhausted-dispatch-cancel"
    )
    exhausted: DispatchRecord | None = None
    for generation in range(1, 4):
        dispatch = durable.prepare_dispatch(ctx, receipt.submission_id)
        assert dispatch.generation == generation
        claim = durable.claim_dispatch(
            ctx, receipt.submission_id, owner_id=f"cancel-generation-{generation}"
        )
        assert claim is not None
        flow_run_id = str(uuid4())
        durable.link_dispatch(
            ctx,
            receipt.submission_id,
            owner_id=f"cancel-generation-{generation}",
            fencing_token=claim.lease_fencing_token,
            prefect_flow_run_id=flow_run_id,
        )
        exhausted = durable.rearm_dispatch_after_remote_failure(
            ctx, receipt.submission_id, expected_flow_run_id=flow_run_id
        )
    assert exhausted is not None
    assert exhausted.status == "reconciliation_required"

    durable.cancel_submission(ctx, receipt.submission_id)
    cancelled = durable.reconcile_cancelled_submissions(ctx, limit=10)

    assert [item.submission_id for item in cancelled] == [receipt.submission_id]
    assert durable.get_dispatch(ctx, receipt.submission_id).status == "cancelled"
    assert durable.execution_route_workload(ctx, route).drained is True


def test_cancellation_preserves_uncertain_and_leased_dispatches_for_reconciliation(
    tmp_path: Path,
) -> None:
    route = f"prefect:{'d' * 64}"
    ctx, _authz, durable, managed = _managed_service(tmp_path, execution_route=route)
    uncertain_receipt = managed.submit_run(
        ctx, "pipeline-058", idempotency_key="uncertain-dispatch-cancel"
    )
    uncertain = durable.prepare_dispatch(ctx, uncertain_receipt.submission_id)
    uncertain_claim = durable.claim_dispatch(
        ctx, uncertain_receipt.submission_id, owner_id="uncertain-dispatcher"
    )
    assert uncertain_claim is not None
    uncertain = durable.release_dispatch(
        ctx,
        uncertain_receipt.submission_id,
        owner_id="uncertain-dispatcher",
        fencing_token=uncertain_claim.lease_fencing_token,
        outcome_uncertain=True,
        error_code="prefect_create_uncertain",
    )
    assert uncertain.status == "uncertain"

    leased_receipt = managed.submit_run(
        ctx, "pipeline-058", idempotency_key="leased-dispatch-cancel"
    )
    leased = durable.prepare_dispatch(ctx, leased_receipt.submission_id)
    leased_claim = durable.claim_dispatch(
        ctx, leased_receipt.submission_id, owner_id="leased-dispatcher"
    )
    assert leased_claim is not None
    assert leased.status == "pending"

    durable.cancel_submission(ctx, uncertain_receipt.submission_id)
    durable.cancel_submission(ctx, leased_receipt.submission_id)
    durable.reconcile_cancelled_submissions(ctx, limit=10)

    assert durable.get_dispatch(ctx, uncertain_receipt.submission_id).status == (
        "uncertain"
    )
    assert durable.get_dispatch(ctx, leased_receipt.submission_id).status == "leased"
    workload = durable.execution_route_workload(ctx, route)
    assert workload.active_submissions == 0
    assert workload.incomplete_dispatches == 2
    assert workload.drained is False


def test_missing_prefect_run_rearms_only_after_grace_and_without_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import prefect.client.orchestration
    from prefect.exceptions import ObjectNotFound

    binding = ManagedDeploymentBinding(
        spec=_spec("missing-run-reconciliation"), deployment_id=uuid4()
    )
    ctx, _authz, durable, _managed = _managed_service(
        tmp_path, execution_route=binding.execution_route
    )
    accepted = _managed.submit_run(
        ctx, "pipeline-058", idempotency_key="missing-remote-run"
    )
    linked_at = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    prepared = durable.prepare_dispatch(ctx, accepted.submission_id)
    claim = durable.claim_dispatch(
        ctx,
        accepted.submission_id,
        owner_id="missing-run-dispatcher",
        now=linked_at,
    )
    assert claim is not None
    flow_run_id = str(uuid4())
    linked = durable.link_dispatch(
        ctx,
        accepted.submission_id,
        owner_id="missing-run-dispatcher",
        fencing_token=claim.lease_fencing_token,
        prefect_flow_run_id=flow_run_id,
        now=linked_at + timedelta(seconds=1),
    )
    assert linked.generation == prepared.generation

    class _MissingRunClient:
        async def __aenter__(self) -> _MissingRunClient:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def read_flow_run(self, _flow_run_id: UUID) -> Any:
            raise ObjectNotFound(RuntimeError("simulated deleted flow run"))

    def _get_client(**_kwargs: Any) -> Any:
        return _MissingRunClient()

    monkeypatch.setattr(
        prefect.client.orchestration,
        "get_client",
        _get_client,
    )
    dispatcher = PrefectDispatcher(
        backend=cast(ManagedBackend, SimpleNamespace(durable_work=durable)),
        context=ctx,
        binding=binding,
        owner_id="missing-run-reconciler",
    )
    reconcile = cast(Any, dispatcher)._reconcile_remote_failures

    async def scenario() -> None:
        await reconcile(limit=10, now=linked_at + timedelta(seconds=300))
        assert durable.get_dispatch(ctx, accepted.submission_id).status == "dispatched"
        await reconcile(limit=10, now=linked_at + timedelta(seconds=302))

    asyncio.run(scenario())
    rearmed = durable.get_dispatch(ctx, accepted.submission_id)
    assert rearmed.status == "pending"
    assert rearmed.generation == linked.generation + 1
    assert rearmed.prefect_flow_run_id is None
    assert rearmed.last_error_code == "remote_missing_before_claim"
    assert durable.list_attempts(ctx, accepted.submission_id) == []


def test_dispatch_reconciliation_scan_advances_beyond_first_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import prefect.client.orchestration
    from prefect.exceptions import ObjectNotFound

    binding = ManagedDeploymentBinding(
        spec=_spec("missing-run-pagination"), deployment_id=uuid4()
    )
    ctx, _authz, durable, managed = _managed_service(
        tmp_path, execution_route=binding.execution_route
    )
    linked_at = datetime.now(UTC) - timedelta(hours=1)
    submission_ids: list[str] = []
    for index in range(3):
        accepted = managed.submit_run(
            ctx,
            "pipeline-058",
            idempotency_key=f"missing-remote-run-page-{index}",
        )
        submission_ids.append(accepted.submission_id)
        durable.prepare_dispatch(ctx, accepted.submission_id)
        claim = durable.claim_dispatch(
            ctx,
            accepted.submission_id,
            owner_id=f"missing-run-page-{index}",
            now=linked_at,
        )
        assert claim is not None
        durable.link_dispatch(
            ctx,
            accepted.submission_id,
            owner_id=f"missing-run-page-{index}",
            fencing_token=claim.lease_fencing_token,
            prefect_flow_run_id=str(uuid4()),
            now=linked_at + timedelta(seconds=1),
        )

    class _MissingRunClient:
        async def __aenter__(self) -> _MissingRunClient:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def read_flow_run(self, _flow_run_id: UUID) -> Any:
            raise ObjectNotFound(RuntimeError("simulated deleted flow run"))

    def _get_client(**_kwargs: Any) -> Any:
        return _MissingRunClient()

    monkeypatch.setattr(
        prefect.client.orchestration,
        "get_client",
        _get_client,
    )
    dispatcher = PrefectDispatcher(
        backend=cast(ManagedBackend, SimpleNamespace(durable_work=durable)),
        context=ctx,
        binding=binding,
        owner_id="missing-run-page-reconciler",
    )
    reconcile = cast(Any, dispatcher)._reconcile_remote_failures

    async def scenario() -> None:
        for _ in range(3):
            await reconcile(limit=1, now=linked_at + timedelta(seconds=4000))

    asyncio.run(scenario())
    assert {
        durable.get_dispatch(ctx, submission_id).status
        for submission_id in submission_ids
    } == {"pending"}
    assert {
        durable.get_dispatch(ctx, submission_id).last_error_code
        for submission_id in submission_ids
    } == {"remote_missing_before_claim"}


def test_process_worker_executes_targeted_csv_and_postgresql_transfers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = os.environ.get("ETLANTIC_CP_TEST_URL")
    if not url:
        pytest.skip("set ETLANTIC_CP_TEST_URL for live Process-worker qualification")

    from httpx import ConnectError
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.actions import DeploymentUpdate, WorkPoolCreate
    from prefect.settings import PREFECT_API_URL, temporary_settings
    from prefect.workers.process import ProcessWorker
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    from etlantic import Profile
    from etlantic.control_plane import MemoryPolicyProvider
    from etlantic.control_plane.schedule_clock import FakeScheduleClock
    from etlantic.registry import BindingDescriptor, PlanningContext
    from etlantic.runtime.request import MaterializationPolicy, RunRequest
    from etlantic.secrets import SecretRef
    from etlantic_prefect.worker import (
        get_managed_run_status,
        request_managed_run_cancellation,
    )
    from etlantic_sqlmodel.control_plane import SQLModelApprovalStore
    from etlantic_sqlmodel.managed import SQLModelBackendConfig, create_managed_backend
    from etlantic_sqlmodel.migrations import upgrade

    scope = uuid4().hex
    store_id = f"phase058-process-{scope}"
    ctx = ControlPlaneContext(
        principal=Principal(subject=f"process-{scope}", issuer="phase058-tests"),
        tenant=TenantRef(tenant_id=f"tenant-{scope}"),
        workspace=WorkspaceRef(
            tenant_id=f"tenant-{scope}", workspace_id=f"workspace-{scope}"
        ),
        environment=EnvironmentRef(name="test"),
        security_domain=SecurityDomain(domain_id="default"),
    )
    row_id = f"phase058-{scope}"
    payload = f"payload-{scope}"
    csv_postgres_table = f"etlantic_phase058_{scope[:16]}"
    csv_postgres_effects = f"etlantic_phase058_fx_{scope[:16]}"
    postgres_postgres_table = f"etlantic_phase058_pp_{scope[:16]}"
    postgres_postgres_effects = f"etlantic_phase058_ppfx_{scope[:16]}"
    scheduled_table = f"etlantic_phase058_sched_{scope[:16]}"
    scheduled_effects = f"etlantic_phase058_schedfx_{scope[:16]}"
    unsettled_table = f"etlantic_phase058_unsettled_{scope[:16]}"
    unsettled_effects = f"etlantic_phase058_unsettledfx_{scope[:16]}"
    partial_table = f"etlantic_phase058_partial_{scope[:16]}"
    partial_effects = f"etlantic_phase058_partialfx_{scope[:16]}"
    policy_denied_table = f"etlantic_phase058_denied_{scope[:16]}"
    policy_denied_effects = f"etlantic_phase058_deniedfx_{scope[:16]}"
    approval_denied_table = f"etlantic_phase058_approval_{scope[:16]}"
    approval_denied_effects = f"etlantic_phase058_approvalfx_{scope[:16]}"
    cancelled_table = f"etlantic_phase058_cancelled_{scope[:16]}"
    cancelled_effects = f"etlantic_phase058_cancelledfx_{scope[:16]}"
    commit_cancel_table = f"etlantic_phase058_commitcancel_{scope[:16]}"
    commit_cancel_effects = f"etlantic_phase058_commitcancelfx_{scope[:16]}"
    artifact_crash_table = f"etlantic_phase058_artifactcrash_{scope[:16]}"
    artifact_crash_effects = f"etlantic_phase058_artifactcrashfx_{scope[:16]}"
    outage_table = f"etlantic_phase058_outage_{scope[:16]}"
    outage_effects = f"etlantic_phase058_outagefx_{scope[:16]}"
    mid_outage_table = f"etlantic_phase058_midoutage_{scope[:16]}"
    mid_outage_effects = f"etlantic_phase058_midoutagefx_{scope[:16]}"
    nontransactional_table = f"etlantic_phase058_nontx_{scope[:16]}"
    nontransactional_effects = f"etlantic_phase058_nontxfx_{scope[:16]}"
    rotated_credential_role = f"p058_worker_{scope[:12]}"
    rotated_credential_password = uuid4().hex
    drift_table = f"etlantic_phase058_drift_{scope[:16]}"
    drift_effects = f"etlantic_phase058_driftfx_{scope[:16]}"
    scheduled_clock = FakeScheduleClock(datetime(2026, 10, 11, 12, 0, tzinfo=UTC))
    source_kind = "csv"
    destination_table = csv_postgres_table
    destination_effects = csv_postgres_effects
    profile = Profile(
        name="phase058-process-worker",
        security_mode="development",
        plugin_allowlist={"etlantic": None},
    )
    reference: Any = None

    def planning_context_factory(
        _ctx: ControlPlaneContext, effective_profile: Any
    ) -> PlanningContext:
        planning = PlanningContext.create(profile=effective_profile)
        if source_kind == "csv":
            source = BindingDescriptor(
                binding="source",
                provider="local-files",
                kind="source",
                config={"input_resource": reference.to_dict()},
            )
        else:
            source = BindingDescriptor(
                binding="source",
                provider="postgresql",
                kind="source",
                location=csv_postgres_table,
                secret_ref=SecretRef(
                    provider="env",
                    name="ETLANTIC_PHASE058_POSTGRES_URL",
                    key="value",
                ),
                config={"schema": "public", "mode": "snapshot"},
            )
        planning.registry.register_binding(source)
        planning.registry.register_binding(
            BindingDescriptor(
                binding="output",
                provider="postgresql",
                location=destination_table,
                secret_ref=SecretRef(
                    provider="env",
                    name="ETLANTIC_PHASE058_POSTGRES_URL",
                    key="value",
                ),
                config={
                    "schema": "public",
                    "mode": "replace",
                    "effect_table": f"public.{destination_effects}",
                },
                kind="sink",
            )
        )
        return planning

    engine = create_engine(url, pool_pre_ping=True)
    try:
        upgrade(engine)
        with engine.begin() as connection:
            for table in (
                csv_postgres_table,
                postgres_postgres_table,
                scheduled_table,
                unsettled_table,
                partial_table,
                policy_denied_table,
                approval_denied_table,
                cancelled_table,
                commit_cancel_table,
                artifact_crash_table,
                outage_table,
                mid_outage_table,
                nontransactional_table,
                drift_table,
            ):
                connection.execute(
                    text(
                        f'CREATE TABLE public."{table}" '
                        "(id text PRIMARY KEY, payload text NOT NULL)"
                    )
                )
            for table in (
                csv_postgres_effects,
                postgres_postgres_effects,
                scheduled_effects,
                unsettled_effects,
                partial_effects,
                policy_denied_effects,
                approval_denied_effects,
                cancelled_effects,
                commit_cancel_effects,
                artifact_crash_effects,
                outage_effects,
                mid_outage_effects,
                nontransactional_effects,
                drift_effects,
            ):
                connection.execute(
                    text(
                        f'CREATE TABLE public."{table}" ('
                        "effect_id text PRIMARY KEY, intent_fingerprint text NOT NULL, "
                        "publication_id text NOT NULL UNIQUE, row_count bigint NOT NULL, "
                        "committed_at timestamptz NOT NULL DEFAULT now())"
                    )
                )
            connection.execute(
                text(
                    f'INSERT INTO public."{partial_table}" (id, payload) '
                    "VALUES (:id, :payload)"
                ),
                {"id": f"stale-{row_id}", "payload": "pre-existing"},
            )
            quoted_role = engine.dialect.identifier_preparer.quote(
                rotated_credential_role
            )
            database_name = make_url(url).database
            assert database_name is not None
            quoted_database = engine.dialect.identifier_preparer.quote(database_name)
            connection.exec_driver_sql(
                f"CREATE ROLE {quoted_role} LOGIN "
                f"PASSWORD '{rotated_credential_password}'"
            )
            connection.exec_driver_sql(
                f"GRANT CONNECT ON DATABASE {quoted_database} TO {quoted_role}"
            )
            connection.exec_driver_sql(f"GRANT USAGE ON SCHEMA public TO {quoted_role}")
            connection.exec_driver_sql(
                "GRANT SELECT, INSERT, UPDATE, DELETE "
                f'ON TABLE public."{artifact_crash_table}", '
                f'public."{artifact_crash_effects}" TO {quoted_role}'
            )
    finally:
        engine.dispose()

    backend: Any = None
    try:
        prefect_database_name = f"prefect_058_{scope[:16]}"
        with _prefect_postgres_server(
            url,
            database_name=prefect_database_name,
            prefect_home=tmp_path / "prefect-home",
        ) as (prefect_api_url, restart_prefect_server, stop_prefect_server):
            monkeypatch.setenv("PREFECT_API_URL", prefect_api_url)
            spec = ManagedDeploymentSpec.from_current_runtime(
                name=f"phase058-{scope[:10]}",
                work_pool_name=f"phase058-process-{scope[:10]}",
                worker_backend_entry_point="phase058_process_backend",
                lockfile_sha256=hashlib.sha256(
                    (Path(__file__).parents[2] / "uv.lock").read_bytes()
                ).hexdigest(),
            )
            registrar = PrefectDeploymentRegistrar()

            async def scenario() -> None:
                nonlocal backend, reference
                nonlocal source_kind, destination_table, destination_effects

                async with get_client() as client:
                    await client.create_work_pool(
                        WorkPoolCreate(name=spec.work_pool_name, type="process")
                    )
                preview = await registrar.preview(spec)
                binding = await registrar.register(
                    spec, expected_fingerprint=preview["spec"]["fingerprint"]
                )
                for key, value in binding.to_environment().items():
                    monkeypatch.setenv(key, value)

                if os.environ.get("ETLANTIC_PHASE058_INSTALLED_BACKEND_PLUGIN") == "1":
                    from importlib.metadata import distribution
                    from importlib.util import find_spec
                    from sysconfig import get_paths

                    installed_distribution = distribution(
                        "etlantic-phase058-test-worker-plugin"
                    )
                    assert any(
                        entry.group == "etlantic.prefect_worker_backends"
                        and entry.name == "phase058_process_backend"
                        and entry.value == "phase058_worker_backend:build_backend"
                        for entry in installed_distribution.entry_points
                    )
                    module_spec = find_spec("phase058_worker_backend")
                    assert module_spec is not None and module_spec.origin is not None
                    assert (
                        Path(module_spec.origin)
                        .resolve()
                        .is_relative_to(Path(sys.prefix).resolve())
                    )
                    site_packages = Path(get_paths()["purelib"]).resolve()
                    for module_name in (
                        "etlantic",
                        "etlantic_prefect",
                        "etlantic_sql",
                        "etlantic_sqlmodel",
                        "etlantic_fastapi",
                        "prefect",
                    ):
                        installed_module = find_spec(module_name)
                        assert (
                            installed_module is not None
                            and installed_module.origin is not None
                            and Path(installed_module.origin)
                            .resolve()
                            .is_relative_to(site_packages)
                        ), f"{module_name} did not resolve from the installed wheel"
                    assert "PYTHONPATH" not in os.environ
                else:
                    helper_path = (
                        Path(__file__).parent
                        / "worker_plugin"
                        / "src"
                        / "phase058_worker_backend"
                        / "__init__.py"
                    )
                    plugin_root = tmp_path / "worker-plugin-dist"
                    plugin_root.mkdir()
                    (plugin_root / "phase058_worker_backend.py").write_bytes(
                        helper_path.read_bytes()
                    )
                    dist_info = (
                        plugin_root
                        / "etlantic_phase058_test_worker_plugin-0.1.0.dist-info"
                    )
                    dist_info.mkdir()
                    (dist_info / "METADATA").write_text(
                        "Metadata-Version: 2.1\n"
                        "Name: etlantic-phase058-test-worker-plugin\n"
                        "Version: 0.1.0\n",
                        encoding="utf-8",
                    )
                    (dist_info / "WHEEL").write_text(
                        "Wheel-Version: 1.0\n"
                        "Generator: etlantic-phase058-test\n"
                        "Root-Is-Purelib: true\n"
                        "Tag: py3-none-any\n",
                        encoding="utf-8",
                    )
                    (dist_info / "entry_points.txt").write_text(
                        "[etlantic.prefect_worker_backends]\n"
                        "phase058_process_backend = phase058_worker_backend:build_backend\n",
                        encoding="utf-8",
                    )
                    inherited_path = os.environ.get("PYTHONPATH", "")
                    monkeypatch.setenv(
                        "PYTHONPATH",
                        os.pathsep.join(
                            part for part in (str(plugin_root), inherited_path) if part
                        ),
                    )
                for key, value in {
                    "ETLANTIC_PHASE058_DATABASE_URL": url,
                    "ETLANTIC_PHASE058_STORE_ID": store_id,
                    "ETLANTIC_PHASE058_PRINCIPAL": ctx.principal.subject,
                    "ETLANTIC_PHASE058_TENANT": ctx.tenant.tenant_id,
                    "ETLANTIC_PHASE058_WORKSPACE": ctx.workspace.workspace_id,
                    "ETLANTIC_PHASE058_SECURITY_DOMAIN": ctx.security_domain.domain_id,
                    "ETLANTIC_PHASE058_ARTIFACT_ROOT": str(tmp_path / "artifacts"),
                    "ETLANTIC_PHASE058_POSTGRES_URL": url,
                }.items():
                    monkeypatch.setenv(key, value)
                monkeypatch.setenv("ETLANTIC_PHASE058_ENABLE_POLICY", "1")

                authorizer = MemoryAuthorizer()
                for action in (
                    "definition.write",
                    "run.submit",
                    "run.read",
                    "run.report",
                    "run.cancel",
                    "input.read",
                    "schedule.write",
                ):
                    authorizer.grant(ctx, action)
                backend = create_managed_backend(
                    SQLModelBackendConfig(
                        database_url=url,
                        store_id=store_id,
                        profile=profile,
                        artifact_root=str(tmp_path / "artifacts"),
                        execution_route=binding.execution_route,
                        schedule_clock=scheduled_clock,
                    ),
                    authorizer=authorizer,
                    planning_context_factory=planning_context_factory,
                )
                staged = backend.input_resources.stage(
                    ctx,
                    f"id,payload\n{row_id},{payload}\n".encode(),
                    media_type="text/csv",
                    format="csv",
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
                content = f"id,payload\n{row_id},{payload}\n".encode()
                reference = backend.input_resources.finalize(
                    ctx,
                    staged.upload_id,
                    expected_sha256=hashlib.sha256(content).hexdigest(),
                    expected_byte_length=len(content),
                )
                managed = backend.managed_service
                managed.register_definition(
                    ctx,
                    "phase058-process-pipeline",
                    pipeline_to_dict(definition_from_pipeline(_ProcessWorkerPipeline)),
                )
                for key, value in {
                    "ETLANTIC_PHASE058_SOURCE_KIND": source_kind,
                    "ETLANTIC_PHASE058_INPUT_REFERENCE": json.dumps(
                        reference.to_dict(), separators=(",", ":")
                    ),
                    "ETLANTIC_PHASE058_SOURCE_TABLE": csv_postgres_table,
                    "ETLANTIC_PHASE058_DESTINATION_TABLE": destination_table,
                    "ETLANTIC_PHASE058_EFFECT_TABLE": destination_effects,
                }.items():
                    monkeypatch.setenv(key, value)
                submitter_code = """
import json
import os
from phase058_worker_backend import build_backend
from etlantic.runtime.request import MaterializationPolicy, RunRequest

backend, context = build_backend()
try:
    receipt = backend.managed_service.submit_run(
        context,
        "phase058-process-pipeline",
        idempotency_key=os.environ["ETLANTIC_PHASE058_SUBMISSION_KEY"],
        request=RunRequest(materialization=MaterializationPolicy.DURABLE),
    )
    print(json.dumps({"submission_id": receipt.submission_id, "resource_id": receipt.resource_id}))
finally:
    backend.close()
"""
                submitter_env = os.environ.copy()
                submitter_env["ETLANTIC_PHASE058_SUBMISSION_KEY"] = (
                    f"phase058-first-{scope}"
                )
                submitter = subprocess.run(
                    [sys.executable, "-c", submitter_code],
                    env=submitter_env,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                assert submitter.returncode == 0, (
                    "separate submitter process failed before returning its receipt"
                )
                first = SimpleNamespace(**json.loads(submitter.stdout))
                undispatched = backend.durable_work.pending_dispatches(
                    ctx,
                    execution_route=binding.execution_route,
                    limit=10,
                )
                assert [item.submission_id for item in undispatched] == [
                    first.submission_id
                ]
                # An ordinary host poll must not race the route-specific Prefect
                # dispatcher for this durably accepted submission.
                ordinary_host = backend.create_execution_host(
                    owner_id=f"ordinary-host-{scope}"
                )
                assert ordinary_host.tick(ctx, limit=1) == 0
                assert (
                    backend.durable_work.get_submission(ctx, first.submission_id).status
                    == "accepted"
                )
                assert (
                    backend.durable_work.list_attempts(ctx, first.submission_id) == []
                )
                dispatcher = PrefectDispatcher(
                    backend=backend,
                    context=ctx,
                    binding=binding,
                    owner_id=f"dispatcher-{scope}",
                )
                dispatch_receipts = await dispatcher.tick(limit=1)
                assert len(dispatch_receipts) == 1
                assert dispatch_receipts[0]["submission_id"] == first.submission_id
                assert dispatch_receipts[0]["status"] == "dispatched"

                second = managed.submit_run(
                    ctx,
                    "phase058-process-pipeline",
                    idempotency_key=f"phase058-second-{scope}",
                    request=RunRequest(materialization=MaterializationPolicy.DURABLE),
                )

                await ProcessWorker(
                    work_pool_name=spec.work_pool_name,
                    name=f"phase058-worker-{scope[:10]}",
                ).start(run_once=True, printer=lambda *_args, **_kwargs: None)

                first_record = backend.durable_work.get_submission(
                    ctx, first.submission_id
                )
                second_record = backend.durable_work.get_submission(
                    ctx, second.submission_id
                )
                assert first_record.status == "completed"
                report = managed.get_run_report(ctx, first.resource_id)
                assert second_record.status == "accepted"
                assert (
                    backend.durable_work.list_attempts(ctx, second.submission_id) == []
                )
                assert report["status"] == "succeeded"
                assert report["run_id"] == first.resource_id
                result_engine = create_engine(url, pool_pre_ping=True)
                try:
                    with result_engine.connect() as connection:
                        rows = connection.execute(
                            text(
                                f'SELECT id, payload FROM public."{csv_postgres_table}"'
                            )
                        ).all()
                        effects = connection.execute(
                            text(
                                f'SELECT row_count FROM public."{csv_postgres_effects}"'
                            )
                        ).all()
                    assert rows == [(row_id, payload)]
                    assert effects == [(1,)]
                finally:
                    result_engine.dispose()
                restart_prefect_server()
                async with get_client() as client:
                    remote = await client.read_flow_run(
                        UUID(str(dispatch_receipts[0]["prefect_flow_run_id"]))
                    )
                    persisted_deployment = await client.read_deployment(
                        binding.deployment_id
                    )
                assert remote.deployment_id == binding.deployment_id
                assert remote.state is not None
                assert (
                    getattr(remote.state.type, "value", remote.state.type)
                    == "COMPLETED"
                )
                assert persisted_deployment.id == binding.deployment_id

                managed.cancel_run(ctx, str(second.resource_id))
                assert backend.durable_work.get_submission(
                    ctx, second.submission_id
                ).status in {"cancel_requested", "cancelled"}

                destination_table = drift_table
                destination_effects = drift_effects
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_DESTINATION_TABLE", destination_table
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_EFFECT_TABLE", destination_effects
                )
                drifted_submission = managed.submit_run(
                    ctx,
                    "phase058-process-pipeline",
                    idempotency_key=f"phase058-worker-drift-{scope}",
                    request=RunRequest(materialization=MaterializationPolicy.DURABLE),
                )
                drift_dispatch = await dispatcher.tick(limit=1)
                assert len(drift_dispatch) == 1
                assert (
                    drift_dispatch[0]["submission_id"]
                    == drifted_submission.submission_id
                )
                drifted_environment = {
                    **binding.to_environment(),
                    "UNTRUSTED_OVERRIDE": "unexpected",
                }
                async with get_client() as client:
                    await client.update_deployment(
                        binding.deployment_id,
                        DeploymentUpdate(job_variables={"env": drifted_environment}),
                    )
                try:
                    await ProcessWorker(
                        work_pool_name=spec.work_pool_name,
                        name=f"phase058-drift-worker-{scope[:10]}",
                    ).start(run_once=True, printer=lambda *_args, **_kwargs: None)
                finally:
                    async with get_client() as client:
                        await client.update_deployment(
                            binding.deployment_id,
                            DeploymentUpdate(
                                job_variables={"env": binding.to_environment()}
                            ),
                        )
                async with get_client() as client:
                    drifted_flow_run = await client.read_flow_run(
                        UUID(str(drift_dispatch[0]["prefect_flow_run_id"]))
                    )
                assert drifted_flow_run.state is not None
                assert (
                    getattr(
                        drifted_flow_run.state.type,
                        "value",
                        drifted_flow_run.state.type,
                    )
                    == "FAILED"
                )
                drifted_record = backend.durable_work.get_submission(
                    ctx, drifted_submission.submission_id
                )
                assert drifted_record.status == "accepted"
                assert (
                    backend.durable_work.list_attempts(
                        ctx, drifted_submission.submission_id
                    )
                    == []
                )
                drift_engine = create_engine(url, pool_pre_ping=True)
                try:
                    with drift_engine.connect() as connection:
                        drift_rows = connection.execute(
                            text(f'SELECT id, payload FROM public."{drift_table}"')
                        ).all()
                        drift_effect_rows = connection.execute(
                            text(f'SELECT effect_id FROM public."{drift_effects}"')
                        ).all()
                    assert drift_rows == []
                    assert drift_effect_rows == []
                finally:
                    drift_engine.dispose()
                recovered_dispatch = await dispatcher.tick(limit=1)
                assert len(recovered_dispatch) == 1
                assert recovered_dispatch[0]["status"] == "dispatched"
                assert recovered_dispatch[0]["generation"] == 2
                assert (
                    recovered_dispatch[0]["prefect_flow_run_id"]
                    != drift_dispatch[0]["prefect_flow_run_id"]
                )
                await ProcessWorker(
                    work_pool_name=spec.work_pool_name,
                    name=f"phase058-drift-recovery-worker-{scope[:10]}",
                ).start(run_once=True, printer=lambda *_args, **_kwargs: None)
                recovered_submission = backend.durable_work.get_submission(
                    ctx, drifted_submission.submission_id
                )
                assert recovered_submission.status == "completed"
                recovered_attempts = backend.durable_work.list_attempts(
                    ctx, drifted_submission.submission_id
                )
                assert len(recovered_attempts) == 1
                assert recovered_attempts[0].status == "completed"
                drift_recovery_engine = create_engine(url, pool_pre_ping=True)
                try:
                    with drift_recovery_engine.connect() as connection:
                        recovered_rows = connection.execute(
                            text(f'SELECT id, payload FROM public."{drift_table}"')
                        ).all()
                        recovered_effect_rows = connection.execute(
                            text(f'SELECT row_count FROM public."{drift_effects}"')
                        ).all()
                    assert recovered_rows == [(row_id, payload)]
                    assert recovered_effect_rows == [(1,)]
                finally:
                    drift_recovery_engine.dispose()

                source_kind = "postgresql"
                destination_table = postgres_postgres_table
                destination_effects = postgres_postgres_effects
                monkeypatch.setenv("ETLANTIC_PHASE058_SOURCE_KIND", source_kind)
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_DESTINATION_TABLE", destination_table
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_EFFECT_TABLE", destination_effects
                )
                third = managed.submit_run(
                    ctx,
                    "phase058-process-pipeline",
                    idempotency_key=f"phase058-postgres-copy-{scope}",
                    request=RunRequest(materialization=MaterializationPolicy.DURABLE),
                )
                second_dispatch = await dispatcher.tick(limit=1)
                assert len(second_dispatch) == 1
                assert second_dispatch[0]["submission_id"] == third.submission_id
                assert second_dispatch[0]["status"] == "dispatched"
                await ProcessWorker(
                    work_pool_name=spec.work_pool_name,
                    name=f"phase058-worker-{scope[:10]}",
                ).start(run_once=True, printer=lambda *_args, **_kwargs: None)

                third_record = backend.durable_work.get_submission(
                    ctx, third.submission_id
                )
                assert third_record.status == "completed"
                assert (
                    managed.get_run_report(ctx, third.resource_id)["status"]
                    == "succeeded"
                )
                result_engine = create_engine(url, pool_pre_ping=True)
                try:
                    with result_engine.connect() as connection:
                        copied_rows = connection.execute(
                            text(
                                f'SELECT id, payload FROM public."{postgres_postgres_table}"'
                            )
                        ).all()
                        copy_effects = connection.execute(
                            text(
                                f'SELECT row_count FROM public."{postgres_postgres_effects}"'
                            )
                        ).all()
                    assert copied_rows == [(row_id, payload)]
                    assert copy_effects == [(1,)]
                finally:
                    result_engine.dispose()
                async with get_client() as client:
                    copied_remote = await client.read_flow_run(
                        UUID(str(second_dispatch[0]["prefect_flow_run_id"]))
                    )
                assert copied_remote.deployment_id == binding.deployment_id
                assert copied_remote.state is not None
                assert (
                    getattr(copied_remote.state.type, "value", copied_remote.state.type)
                    == "COMPLETED"
                )

                source_kind = "postgresql"
                destination_table = scheduled_table
                destination_effects = scheduled_effects
                monkeypatch.setenv("ETLANTIC_PHASE058_SOURCE_KIND", source_kind)
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_DESTINATION_TABLE", destination_table
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_EFFECT_TABLE", destination_effects
                )
                schedule = backend.schedule_service.create(
                    ctx,
                    "phase058-process-pipeline",
                    spec=ScheduleSpec(
                        kind="interval", interval_seconds=60, overlap="queue"
                    ),
                )
                assert schedule.execution_route == binding.execution_route
                scheduled_clock.advance(timedelta(seconds=60))
                scheduler_a = backend.create_scheduler(
                    owner_id=f"scheduler-a-{scope}", ttl_seconds=300
                )
                scheduler_b = backend.create_scheduler(
                    owner_id=f"scheduler-b-{scope}", ttl_seconds=300
                )
                schedule_barrier = Barrier(2)

                def concurrent_schedule_tick(candidate: Any) -> int:
                    schedule_barrier.wait(timeout=10)
                    return candidate.tick(ctx)

                schedule_claims = await asyncio.gather(
                    asyncio.to_thread(concurrent_schedule_tick, scheduler_a),
                    asyncio.to_thread(concurrent_schedule_tick, scheduler_b),
                )
                assert sorted(schedule_claims) == [0, 1]
                firings = backend.schedule_store.list_firings(ctx, schedule.schedule_id)
                assert len(firings) == 1
                firing = firings[0]
                assert firing.status == "accepted"
                assert firing.submission_id is not None
                scheduled_submission = backend.durable_work.get_submission(
                    ctx, firing.submission_id
                )
                assert scheduled_submission.execution_route == binding.execution_route
                scheduled_dispatch = await dispatcher.tick(limit=1)
                assert len(scheduled_dispatch) == 1
                assert scheduled_dispatch[0]["submission_id"] == firing.submission_id
                await ProcessWorker(
                    work_pool_name=spec.work_pool_name,
                    name=f"phase058-scheduled-worker-{scope[:10]}",
                ).start(run_once=True, printer=lambda *_args, **_kwargs: None)
                scheduled_submission = backend.durable_work.get_submission(
                    ctx, firing.submission_id
                )
                assert scheduled_submission.status == "completed"
                assert (
                    managed.get_run_report(ctx, scheduled_submission.resource_id)[
                        "status"
                    ]
                    == "succeeded"
                )
                result_engine = create_engine(url, pool_pre_ping=True)
                try:
                    with result_engine.connect() as connection:
                        scheduled_rows = connection.execute(
                            text(f'SELECT id, payload FROM public."{scheduled_table}"')
                        ).all()
                        scheduled_effect_rows = connection.execute(
                            text(f'SELECT row_count FROM public."{scheduled_effects}"')
                        ).all()
                    assert scheduled_rows == [(row_id, payload)]
                    assert scheduled_effect_rows == [(1,)]
                finally:
                    result_engine.dispose()

                destination_table = postgres_postgres_table
                destination_effects = postgres_postgres_effects
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_DESTINATION_TABLE", destination_table
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_EFFECT_TABLE", destination_effects
                )

                def effect_ledger_count() -> int:
                    effect_engine = create_engine(url, pool_pre_ping=True)
                    try:
                        with effect_engine.connect() as connection:
                            return int(
                                connection.execute(
                                    text(
                                        f'SELECT count(*) FROM public."{postgres_postgres_effects}"'
                                    )
                                ).scalar_one()
                            )
                    finally:
                        effect_engine.dispose()

                create_then_crash = managed.submit_run(
                    ctx,
                    "phase058-process-pipeline",
                    idempotency_key=f"phase058-dispatch-crash-after-create-{scope}",
                    request=RunRequest(materialization=MaterializationPolicy.DURABLE),
                )
                link_marker = tmp_path / f"phase058-dispatch-created-{scope}"
                link_release = tmp_path / f"phase058-dispatch-release-{scope}"
                crash_dispatch_env = os.environ.copy()
                crash_dispatch_env["ETLANTIC_PHASE058_DISPATCH_LINK_MARKER"] = str(
                    link_marker
                )
                crash_dispatch_env["ETLANTIC_PHASE058_DISPATCH_LINK_RELEASE"] = str(
                    link_release
                )
                crash_dispatch_env["ETLANTIC_PHASE058_DISPATCH_OWNER"] = (
                    f"dispatcher-crash-{scope}"
                )
                crash_dispatch_code = """
import asyncio
import os
import time
from pathlib import Path
from phase058_worker_backend import build_backend
from etlantic_prefect import PrefectDispatcher

backend, context = build_backend()
marker = Path(os.environ["ETLANTIC_PHASE058_DISPATCH_LINK_MARKER"])
release = Path(os.environ["ETLANTIC_PHASE058_DISPATCH_LINK_RELEASE"])
def crash_before_link(*args, **kwargs):
    marker.write_text(kwargs["prefect_flow_run_id"], encoding="utf-8")
    deadline = time.monotonic() + 60
    while not release.exists():
        if time.monotonic() >= deadline:
            raise TimeoutError("dispatch link crash gate was not released")
        time.sleep(0.02)
    os._exit(76)
backend.durable_work.link_dispatch = crash_before_link
dispatcher = PrefectDispatcher.from_environment(
    backend,
    context,
    owner_id=os.environ["ETLANTIC_PHASE058_DISPATCH_OWNER"],
    lease_seconds=1,
)
asyncio.run(dispatcher.tick(limit=1))
backend.close()
"""
                dispatch_process = subprocess.Popen(
                    [sys.executable, "-c", crash_dispatch_code],
                    env=crash_dispatch_env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                dispatch_process_error: BaseException | None = None
                try:
                    await asyncio.wait_for(
                        asyncio.to_thread(_wait_for_marker, link_marker),
                        timeout=65,
                    )
                    created_flow_run_id = link_marker.read_text(encoding="utf-8")
                    interrupted_dispatch = backend.durable_work.get_dispatch(
                        ctx, create_then_crash.submission_id
                    )
                    assert interrupted_dispatch.status == "leased"
                    assert interrupted_dispatch.prefect_flow_run_id is None
                    async with get_client() as client:
                        remote_before_link = await client.read_flow_run(
                            UUID(created_flow_run_id)
                        )
                    assert remote_before_link.deployment_id == binding.deployment_id
                finally:
                    link_release.touch(exist_ok=True)
                    try:
                        await asyncio.wait_for(
                            asyncio.to_thread(dispatch_process.communicate, timeout=60),
                            timeout=65,
                        )
                    except BaseException as exc:
                        dispatch_process_error = exc
                assert dispatch_process_error is None, repr(dispatch_process_error)
                assert dispatch_process.returncode == 76
                interrupted_dispatch = backend.durable_work.get_dispatch(
                    ctx, create_then_crash.submission_id
                )
                assert interrupted_dispatch.status == "leased"
                assert interrupted_dispatch.prefect_flow_run_id is None
                assert interrupted_dispatch.lease_expires_at is not None
                lease_expires_at = datetime.fromisoformat(
                    interrupted_dispatch.lease_expires_at.replace("Z", "+00:00")
                )
                while lease_expires_at > datetime.now(UTC):
                    await asyncio.sleep(0.05)
                recovered_dispatch = PrefectDispatcher(
                    backend=backend,
                    context=ctx,
                    binding=binding,
                    owner_id=f"dispatcher-link-recovery-{scope}",
                    lease_seconds=1,
                )
                recovered_receipts = await recovered_dispatch.tick(limit=1)
                assert len(recovered_receipts) == 1
                assert recovered_receipts[0]["status"] == "dispatched"
                assert (
                    recovered_receipts[0]["prefect_flow_run_id"] == created_flow_run_id
                )
                linked_dispatch = backend.durable_work.get_dispatch(
                    ctx, create_then_crash.submission_id
                )
                assert linked_dispatch.status == "dispatched"
                assert linked_dispatch.prefect_flow_run_id == created_flow_run_id
                await ProcessWorker(
                    work_pool_name=spec.work_pool_name,
                    name=f"phase058-link-recovery-worker-{scope[:8]}",
                ).start(run_once=True, printer=lambda *_args, **_kwargs: None)
                assert (
                    backend.durable_work.get_submission(
                        ctx, create_then_crash.submission_id
                    ).status
                    == "completed"
                )

                dispatch_crash_code = """
import asyncio
import os
import time
from pathlib import Path
from phase058_worker_backend import build_backend
from etlantic_prefect import PrefectDispatcher

backend, context = build_backend()
marker = Path(os.environ["ETLANTIC_PHASE058_DISPATCH_FAULT_MARKER"])
release = Path(os.environ["ETLANTIC_PHASE058_DISPATCH_FAULT_RELEASE"])
stage = os.environ["ETLANTIC_PHASE058_DISPATCH_FAULT_STAGE"]
def wait_then_exit(exit_code, value):
    marker.write_text(value, encoding="utf-8")
    deadline = time.monotonic() + 60
    while not release.exists():
        if time.monotonic() >= deadline:
            raise TimeoutError("dispatch fault gate was not released")
        time.sleep(0.02)
    os._exit(exit_code)
if stage == "before_remote_create":
    original_claim = backend.durable_work.claim_dispatch
    def crash_after_claim(*args, **kwargs):
        claim = original_claim(*args, **kwargs)
        if claim is not None:
            wait_then_exit(74, claim.creation_key)
        return claim
    backend.durable_work.claim_dispatch = crash_after_claim
elif stage == "after_link":
    original_link = backend.durable_work.link_dispatch
    def crash_after_link(*args, **kwargs):
        linked = original_link(*args, **kwargs)
        wait_then_exit(75, linked.prefect_flow_run_id or "")
        return linked
    backend.durable_work.link_dispatch = crash_after_link
else:
    raise ValueError("unsupported dispatch crash stage")
dispatcher = PrefectDispatcher.from_environment(
    backend,
    context,
    owner_id=os.environ["ETLANTIC_PHASE058_DISPATCH_OWNER"],
    lease_seconds=1,
)
asyncio.run(dispatcher.tick(limit=1))
backend.close()
"""

                before_create = managed.submit_run(
                    ctx,
                    "phase058-process-pipeline",
                    idempotency_key=f"phase058-dispatch-crash-before-create-{scope}",
                    request=RunRequest(materialization=MaterializationPolicy.DURABLE),
                )
                before_create_marker = tmp_path / f"phase058-before-create-{scope}"
                before_create_release = (
                    tmp_path / f"phase058-release-before-create-{scope}"
                )
                before_create_env = os.environ.copy()
                before_create_env.update(
                    {
                        "ETLANTIC_PHASE058_DISPATCH_FAULT_STAGE": "before_remote_create",
                        "ETLANTIC_PHASE058_DISPATCH_FAULT_MARKER": str(
                            before_create_marker
                        ),
                        "ETLANTIC_PHASE058_DISPATCH_FAULT_RELEASE": str(
                            before_create_release
                        ),
                        "ETLANTIC_PHASE058_DISPATCH_OWNER": (
                            f"dispatcher-before-create-{scope}"
                        ),
                    }
                )
                before_create_process = subprocess.Popen(
                    [sys.executable, "-c", dispatch_crash_code],
                    env=before_create_env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                before_create_error: BaseException | None = None
                try:
                    await asyncio.wait_for(
                        asyncio.to_thread(_wait_for_marker, before_create_marker),
                        timeout=65,
                    )
                    before_create_dispatch = backend.durable_work.get_dispatch(
                        ctx, before_create.submission_id
                    )
                    assert before_create_dispatch.status == "leased"
                    assert before_create_dispatch.prefect_flow_run_id is None
                finally:
                    before_create_release.touch(exist_ok=True)
                    try:
                        await asyncio.wait_for(
                            asyncio.to_thread(
                                before_create_process.communicate, timeout=60
                            ),
                            timeout=65,
                        )
                    except BaseException as exc:
                        before_create_error = exc
                assert before_create_error is None, repr(before_create_error)
                assert before_create_process.returncode == 74
                before_create_dispatch = backend.durable_work.get_dispatch(
                    ctx, before_create.submission_id
                )
                assert before_create_dispatch.lease_expires_at is not None
                before_create_expiry = datetime.fromisoformat(
                    before_create_dispatch.lease_expires_at.replace("Z", "+00:00")
                )
                while before_create_expiry > datetime.now(UTC):
                    await asyncio.sleep(0.05)
                before_create_recovery = PrefectDispatcher(
                    backend=backend,
                    context=ctx,
                    binding=binding,
                    owner_id=f"dispatcher-before-create-recovery-{scope}",
                    lease_seconds=1,
                )
                before_create_receipts = await before_create_recovery.tick(limit=1)
                assert len(before_create_receipts) == 1
                assert before_create_receipts[0]["status"] == "dispatched"
                before_create_dispatch = backend.durable_work.get_dispatch(
                    ctx, before_create.submission_id
                )
                assert before_create_dispatch.status == "dispatched"
                before_create_flow_run_id = before_create_dispatch.prefect_flow_run_id
                assert before_create_flow_run_id is not None
                before_create_effects = effect_ledger_count()
                await ProcessWorker(
                    work_pool_name=spec.work_pool_name,
                    name=f"phase058-before-create-worker-{scope[:8]}",
                ).start(run_once=True, printer=lambda *_args, **_kwargs: None)
                assert (
                    backend.durable_work.get_submission(
                        ctx, before_create.submission_id
                    ).status
                    == "completed"
                )
                assert effect_ledger_count() == before_create_effects + 1

                linked_then_crash = managed.submit_run(
                    ctx,
                    "phase058-process-pipeline",
                    idempotency_key=f"phase058-dispatch-crash-after-link-{scope}",
                    request=RunRequest(materialization=MaterializationPolicy.DURABLE),
                )
                after_link_marker = tmp_path / f"phase058-after-link-{scope}"
                after_link_release = tmp_path / f"phase058-release-after-link-{scope}"
                after_link_env = os.environ.copy()
                after_link_env.update(
                    {
                        "ETLANTIC_PHASE058_DISPATCH_FAULT_STAGE": "after_link",
                        "ETLANTIC_PHASE058_DISPATCH_FAULT_MARKER": str(
                            after_link_marker
                        ),
                        "ETLANTIC_PHASE058_DISPATCH_FAULT_RELEASE": str(
                            after_link_release
                        ),
                        "ETLANTIC_PHASE058_DISPATCH_OWNER": (
                            f"dispatcher-after-link-{scope}"
                        ),
                    }
                )
                after_link_process = subprocess.Popen(
                    [sys.executable, "-c", dispatch_crash_code],
                    env=after_link_env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                after_link_error: BaseException | None = None
                try:
                    await asyncio.wait_for(
                        asyncio.to_thread(_wait_for_marker, after_link_marker),
                        timeout=65,
                    )
                    after_link_flow_run_id = after_link_marker.read_text(
                        encoding="utf-8"
                    )
                    linked_after_crash = backend.durable_work.get_dispatch(
                        ctx, linked_then_crash.submission_id
                    )
                    assert linked_after_crash.status == "dispatched"
                    assert (
                        linked_after_crash.prefect_flow_run_id == after_link_flow_run_id
                    )
                finally:
                    after_link_release.touch(exist_ok=True)
                    try:
                        await asyncio.wait_for(
                            asyncio.to_thread(
                                after_link_process.communicate, timeout=60
                            ),
                            timeout=65,
                        )
                    except BaseException as exc:
                        after_link_error = exc
                assert after_link_error is None, repr(after_link_error)
                assert after_link_process.returncode == 75
                assert await dispatcher.tick(limit=10) == []
                linked_after_crash = backend.durable_work.get_dispatch(
                    ctx, linked_then_crash.submission_id
                )
                assert linked_after_crash.status == "dispatched"
                assert linked_after_crash.prefect_flow_run_id == after_link_flow_run_id
                after_link_effects = effect_ledger_count()
                await ProcessWorker(
                    work_pool_name=spec.work_pool_name,
                    name=f"phase058-after-link-worker-{scope[:8]}",
                ).start(run_once=True, printer=lambda *_args, **_kwargs: None)
                assert (
                    backend.durable_work.get_submission(
                        ctx, linked_then_crash.submission_id
                    ).status
                    == "completed"
                )
                assert effect_ledger_count() == after_link_effects + 1
                async with get_client() as client:
                    after_link_remote = await client.read_flow_run(
                        UUID(after_link_flow_run_id)
                    )
                assert after_link_remote.state is not None
                assert (
                    getattr(
                        after_link_remote.state.type,
                        "value",
                        after_link_remote.state.type,
                    )
                    == "COMPLETED"
                )

                destination_table = cancelled_table
                destination_effects = cancelled_effects
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_DESTINATION_TABLE", destination_table
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_EFFECT_TABLE", destination_effects
                )
                cancelled_after_dispatch = managed.submit_run(
                    ctx,
                    "phase058-process-pipeline",
                    idempotency_key=f"phase058-cancel-after-dispatch-{scope}",
                    request=RunRequest(materialization=MaterializationPolicy.DURABLE),
                )
                cancellation_dispatch = await dispatcher.tick(limit=1)
                assert len(cancellation_dispatch) == 1
                assert (
                    cancellation_dispatch[0]["submission_id"]
                    == cancelled_after_dispatch.submission_id
                )
                cancellation_record = backend.durable_work.get_submission(
                    ctx, cancelled_after_dispatch.submission_id
                )
                cancellation_reference = ManagedExecutionReference.from_submission(
                    cancellation_record
                )
                cancellation_receipt = request_managed_run_cancellation(
                    cancellation_reference.to_dict()
                )
                assert cancellation_receipt["cancellation_durable"] is True
                assert cancellation_receipt["status"] == "cancel_requested"
                assert "remote_cancellation" in cancellation_receipt
                await ProcessWorker(
                    work_pool_name=spec.work_pool_name,
                    name=f"phase058-cancel-after-dispatch-worker-{scope[:8]}",
                ).start(run_once=True, printer=lambda *_args, **_kwargs: None)
                backend.durable_work.reconcile_cancelled_submissions(ctx, limit=100)
                assert (
                    backend.durable_work.get_submission(
                        ctx, cancelled_after_dispatch.submission_id
                    ).status
                    == "cancelled"
                )
                cancellation_engine = create_engine(url, pool_pre_ping=True)
                try:
                    with cancellation_engine.connect() as connection:
                        cancelled_rows = connection.execute(
                            text(f'SELECT id, payload FROM public."{cancelled_table}"')
                        ).all()
                        cancelled_effect_rows = connection.execute(
                            text(f'SELECT effect_id FROM public."{cancelled_effects}"')
                        ).all()
                    assert cancelled_rows == []
                    assert cancelled_effect_rows == []
                finally:
                    cancellation_engine.dispose()

                source_staging_cancel = managed.submit_run(
                    ctx,
                    "phase058-process-pipeline",
                    idempotency_key=f"phase058-cancel-during-staging-{scope}",
                    request=RunRequest(materialization=MaterializationPolicy.DURABLE),
                )
                source_staging_dispatch = await dispatcher.tick(limit=1)
                assert len(source_staging_dispatch) == 1
                assert (
                    source_staging_dispatch[0]["submission_id"]
                    == source_staging_cancel.submission_id
                )
                staging_marker = tmp_path / f"phase058-source-staging-{scope}"
                staging_release = tmp_path / f"phase058-source-staging-release-{scope}"
                staging_cancel_observed = (
                    tmp_path / f"phase058-source-staging-cancel-{scope}"
                )
                monkeypatch.setenv("ETLANTIC_PHASE058_HOLD_DURING_SOURCE_STAGING", "1")
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_SOURCE_STAGING_MARKER", str(staging_marker)
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_SOURCE_STAGING_RELEASE", str(staging_release)
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_SOURCE_STAGING_CANCEL_OBSERVED",
                    str(staging_cancel_observed),
                )
                source_staging_worker = asyncio.create_task(
                    ProcessWorker(
                        work_pool_name=spec.work_pool_name,
                        name=f"phase058-staging-cancel-worker-{scope[:8]}",
                    ).start(run_once=True, printer=lambda *_args, **_kwargs: None)
                )
                source_staging_worker_error: BaseException | None = None
                try:
                    await asyncio.wait_for(
                        asyncio.to_thread(_wait_for_marker, staging_marker),
                        timeout=65,
                    )
                    staging_attempts = backend.durable_work.list_attempts(
                        ctx, source_staging_cancel.submission_id
                    )
                    assert len(staging_attempts) == 1
                    assert staging_attempts[0].status == "running"
                    staging_engine = create_engine(url, pool_pre_ping=True)
                    try:
                        with staging_engine.connect() as connection:
                            assert (
                                connection.execute(
                                    text(
                                        f'SELECT id, payload FROM public."{cancelled_table}"'
                                    )
                                ).all()
                                == []
                            )
                            assert (
                                connection.execute(
                                    text(
                                        f'SELECT effect_id FROM public."{cancelled_effects}"'
                                    )
                                ).all()
                                == []
                            )
                    finally:
                        staging_engine.dispose()

                    staging_cancel_receipt = managed.cancel_run(
                        ctx, str(source_staging_cancel.resource_id)
                    )
                    assert staging_cancel_receipt["status"] == "cancel_requested"
                    await asyncio.wait_for(
                        asyncio.to_thread(_wait_for_marker, staging_cancel_observed),
                        timeout=10,
                    )
                    assert staging_cancel_observed.read_text(encoding="utf-8") == (
                        "observed"
                    )
                    staging_release.touch(exist_ok=True)
                    await asyncio.wait_for(source_staging_worker, timeout=60)
                except BaseException as exc:
                    source_staging_worker_error = exc
                finally:
                    staging_release.touch(exist_ok=True)
                    if not source_staging_worker.done():
                        try:
                            await asyncio.wait_for(source_staging_worker, timeout=60)
                        except BaseException as exc:
                            source_staging_worker_error = exc
                    for variable in (
                        "ETLANTIC_PHASE058_HOLD_DURING_SOURCE_STAGING",
                        "ETLANTIC_PHASE058_SOURCE_STAGING_MARKER",
                        "ETLANTIC_PHASE058_SOURCE_STAGING_RELEASE",
                        "ETLANTIC_PHASE058_SOURCE_STAGING_CANCEL_OBSERVED",
                    ):
                        monkeypatch.delenv(variable, raising=False)
                assert source_staging_worker_error is None, repr(
                    source_staging_worker_error
                )
                source_staging_record = backend.durable_work.get_submission(
                    ctx, source_staging_cancel.submission_id
                )
                assert source_staging_record.status == "cancelled"
                source_staging_attempts = backend.durable_work.list_attempts(
                    ctx, source_staging_cancel.submission_id
                )
                assert len(source_staging_attempts) == 1
                assert source_staging_attempts[0].status == "cancelled"
                source_staging_effect = backend.durable_work.get_effect(
                    ctx, f"{source_staging_cancel.submission_id}:execution"
                )
                assert source_staging_effect.status == "none"
                assert (
                    managed.get_run_report(ctx, str(source_staging_cancel.resource_id))[
                        "status"
                    ]
                    == "cancelled"
                )
                staging_engine = create_engine(url, pool_pre_ping=True)
                try:
                    with staging_engine.connect() as connection:
                        assert (
                            connection.execute(
                                text(
                                    f'SELECT id, payload FROM public."{cancelled_table}"'
                                )
                            ).all()
                            == []
                        )
                        assert (
                            connection.execute(
                                text(
                                    f'SELECT effect_id FROM public."{cancelled_effects}"'
                                )
                            ).all()
                            == []
                        )
                finally:
                    staging_engine.dispose()

                publication_cancel = managed.submit_run(
                    ctx,
                    "phase058-process-pipeline",
                    idempotency_key=f"phase058-cancel-during-report-publication-{scope}",
                    request=RunRequest(materialization=MaterializationPolicy.DURABLE),
                )
                publication_submission = backend.durable_work.get_submission(
                    ctx, publication_cancel.submission_id
                )
                publication_dispatch = await dispatcher.tick(limit=1)
                assert len(publication_dispatch) == 1
                assert (
                    publication_dispatch[0]["submission_id"]
                    == publication_cancel.submission_id
                )
                publication_marker = tmp_path / f"phase058-report-publication-{scope}"
                publication_release = (
                    tmp_path / f"phase058-report-publication-release-{scope}"
                )
                result_publication_marker = (
                    tmp_path / f"phase058-result-publication-{scope}"
                )
                result_publication_release = (
                    tmp_path / f"phase058-result-publication-release-{scope}"
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_REPORT_STORE_FAULT_RUN_ID",
                    publication_submission.run_id,
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_REPORT_STORE_FAULT_MARKER",
                    str(publication_marker),
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_REPORT_STORE_FAULT_RELEASE",
                    str(publication_release),
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_CRASH_AFTER_RESULT_PUBLICATION_RUN_ID",
                    publication_submission.run_id,
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_CRASH_AFTER_RESULT_PUBLICATION_MARKER",
                    str(result_publication_marker),
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_CRASH_AFTER_RESULT_PUBLICATION_RELEASE",
                    str(result_publication_release),
                )
                publication_worker = asyncio.create_task(
                    ProcessWorker(
                        work_pool_name=spec.work_pool_name,
                        name=f"phase058-publication-cancel-worker-{scope[:8]}",
                    ).start(run_once=True, printer=lambda *_args, **_kwargs: None)
                )
                publication_worker_error: BaseException | None = None
                result_publication_after_crash: Any = None
                try:
                    await asyncio.wait_for(
                        asyncio.to_thread(_wait_for_marker, publication_marker),
                        timeout=65,
                    )
                    publication_engine = create_engine(url, pool_pre_ping=True)
                    try:
                        with publication_engine.connect() as connection:
                            assert connection.execute(
                                text(
                                    f'SELECT id, payload FROM public."{cancelled_table}"'
                                )
                            ).all() == [(row_id, payload)]
                            assert connection.execute(
                                text(
                                    f'SELECT row_count FROM public."{cancelled_effects}"'
                                )
                            ).all() == [(1,)]
                    finally:
                        publication_engine.dispose()
                    publication_cancel_receipt = managed.cancel_run(
                        ctx, str(publication_cancel.resource_id)
                    )
                    assert publication_cancel_receipt["status"] == "cancel_requested"
                    assert (
                        backend.durable_work.get_submission(
                            ctx, publication_cancel.submission_id
                        ).status
                        == "cancel_requested"
                    )
                finally:
                    publication_release.touch(exist_ok=True)
                    try:
                        await asyncio.wait_for(
                            asyncio.to_thread(
                                _wait_for_marker, result_publication_marker
                            ),
                            timeout=30,
                        )
                        result_publication_after_crash = (
                            backend.durable_work.get_latest_result_publication(
                                ctx, publication_cancel.submission_id
                            )
                        )
                        assert result_publication_after_crash is not None
                        assert result_publication_after_crash.published_at is None
                        durable_report = json.loads(
                            result_publication_after_crash.report_json
                        )
                        durable_artifacts = [
                            item
                            for item in durable_report.get("artifacts", [])
                            if item.get("strategy") == "durable"
                        ]
                        assert durable_artifacts
                        artifact_files = {
                            path.name
                            for path in (tmp_path / "artifacts").rglob("*.json")
                        }
                        assert all(
                            hashlib.sha256(
                                str(item["identity"]).encode("utf-8")
                            ).hexdigest()
                            + ".json"
                            in artifact_files
                            for item in durable_artifacts
                        )
                    except BaseException as exc:
                        publication_worker_error = exc
                    finally:
                        result_publication_release.touch(exist_ok=True)
                    try:
                        await asyncio.wait_for(publication_worker, timeout=60)
                    except BaseException as exc:
                        if publication_worker_error is None:
                            publication_worker_error = exc
                    for variable in (
                        "ETLANTIC_PHASE058_REPORT_STORE_FAULT_RUN_ID",
                        "ETLANTIC_PHASE058_REPORT_STORE_FAULT_MARKER",
                        "ETLANTIC_PHASE058_REPORT_STORE_FAULT_RELEASE",
                        "ETLANTIC_PHASE058_CRASH_AFTER_RESULT_PUBLICATION_RUN_ID",
                        "ETLANTIC_PHASE058_CRASH_AFTER_RESULT_PUBLICATION_MARKER",
                        "ETLANTIC_PHASE058_CRASH_AFTER_RESULT_PUBLICATION_RELEASE",
                    ):
                        monkeypatch.delenv(variable, raising=False)
                assert publication_worker_error is None, repr(publication_worker_error)
                publication_record = backend.durable_work.get_submission(
                    ctx, publication_cancel.submission_id
                )
                assert publication_record.status == "cancel_requested"
                publication_attempts = backend.durable_work.list_attempts(
                    ctx, publication_cancel.submission_id
                )
                assert len(publication_attempts) == 1
                assert publication_attempts[0].status == "running"
                pending_result = backend.durable_work.get_latest_result_publication(
                    ctx, publication_cancel.submission_id
                )
                assert pending_result is not None
                assert pending_result.published_at is None
                publication_attempt = publication_attempts[0]
                backend.durable_work.release_lease(
                    ctx,
                    publication_cancel.submission_id,
                    owner_id=publication_attempt.owner_id,
                    fencing_token=publication_attempt.fencing_token,
                )
                recovery_host = backend.create_execution_host(
                    owner_id=f"phase058-report-publication-recovery-{scope[:8]}"
                )
                recovery_host.poll(
                    ctx, limit=10, execution_route=binding.execution_route
                )
                recovered_result = backend.durable_work.get_latest_result_publication(
                    ctx, publication_cancel.submission_id
                )
                assert recovered_result is not None
                assert recovered_result.published_at is not None
                assert result_publication_after_crash is not None
                assert result_publication_after_crash.report_sha256 == (
                    recovered_result.report_sha256
                )
                recovered_publication_attempts = backend.durable_work.list_attempts(
                    ctx, publication_cancel.submission_id
                )
                assert [item.status for item in recovered_publication_attempts] == [
                    "lost",
                    "completed",
                ]
                assert (
                    backend.durable_work.get_effect(
                        ctx, f"{publication_cancel.submission_id}:execution"
                    ).status
                    == "committed"
                )
                assert (
                    managed.get_run_report(ctx, str(publication_cancel.resource_id))[
                        "status"
                    ]
                    == "succeeded"
                )
                publication_engine = create_engine(url, pool_pre_ping=True)
                try:
                    with publication_engine.connect() as connection:
                        assert connection.execute(
                            text(f'SELECT id, payload FROM public."{cancelled_table}"')
                        ).all() == [(row_id, payload)]
                        assert connection.execute(
                            text(f'SELECT row_count FROM public."{cancelled_effects}"')
                        ).all() == [(1,)]
                finally:
                    publication_engine.dispose()

                source_kind = "csv"
                destination_table = artifact_crash_table
                destination_effects = artifact_crash_effects
                for key, value in {
                    "ETLANTIC_PHASE058_SOURCE_KIND": source_kind,
                    "ETLANTIC_PHASE058_DESTINATION_TABLE": destination_table,
                    "ETLANTIC_PHASE058_EFFECT_TABLE": destination_effects,
                }.items():
                    monkeypatch.setenv(key, value)
                artifact_write_crash = managed.submit_run(
                    ctx,
                    "phase058-process-pipeline",
                    idempotency_key=f"phase058-artifact-write-crash-{scope}",
                    request=RunRequest(materialization=MaterializationPolicy.DURABLE),
                )
                artifact_write_submission = backend.durable_work.get_submission(
                    ctx, artifact_write_crash.submission_id
                )
                submission_snapshot = artifact_write_submission.input_snapshot or ""
                assert str(make_url(url).password) not in submission_snapshot
                assert rotated_credential_password not in submission_snapshot
                artifact_write_dispatch = await dispatcher.tick(limit=1)
                assert len(artifact_write_dispatch) == 1
                assert (
                    artifact_write_dispatch[0]["submission_id"]
                    == artifact_write_crash.submission_id
                )
                artifact_write_marker = (
                    tmp_path / f"phase058-artifact-write-{scope}.json"
                )
                artifact_write_release = (
                    tmp_path / f"phase058-artifact-write-release-{scope}"
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_CRASH_DURING_ARTIFACT_WRITE_RUN_ID",
                    artifact_write_submission.run_id,
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_CRASH_DURING_ARTIFACT_WRITE_MARKER",
                    str(artifact_write_marker),
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_CRASH_DURING_ARTIFACT_WRITE_RELEASE",
                    str(artifact_write_release),
                )
                rotated_connector_url = make_url(url).set(
                    username=rotated_credential_role,
                    password=rotated_credential_password,
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_POSTGRES_URL", str(rotated_connector_url)
                )
                artifact_write_worker = asyncio.create_task(
                    ProcessWorker(
                        work_pool_name=spec.work_pool_name,
                        name=f"phase058-artifact-write-worker-{scope[:8]}",
                    ).start(run_once=True, printer=lambda *_args, **_kwargs: None)
                )
                artifact_write_worker_error: BaseException | None = None
                try:
                    await asyncio.wait_for(
                        asyncio.to_thread(_wait_for_marker, artifact_write_marker),
                        timeout=65,
                    )
                    interrupted_write = json.loads(
                        artifact_write_marker.read_text(encoding="utf-8")
                    )
                    interrupted_target = Path(interrupted_write["target"])
                    interrupted_temporary = Path(interrupted_write["temporary"])
                    assert interrupted_temporary.is_file()
                    assert interrupted_temporary.read_bytes() == b'[{"partial":'
                    assert not interrupted_target.exists()
                    assert (
                        backend.durable_work.list_attempts(
                            ctx, artifact_write_crash.submission_id
                        )[0].status
                        == "running"
                    )
                    assert (
                        backend.durable_work.get_latest_result_publication(
                            ctx, artifact_write_crash.submission_id
                        )
                        is None
                    )
                    with pytest.raises(ControlPlaneError) as no_artifact_write_effect:
                        backend.durable_work.get_effect(
                            ctx,
                            f"{artifact_write_crash.submission_id}:execution",
                        )
                    assert no_artifact_write_effect.value.status == 404
                    artifact_effect_engine = create_engine(url, pool_pre_ping=True)
                    try:
                        with artifact_effect_engine.connect() as connection:
                            assert (
                                connection.execute(
                                    text(
                                        f'SELECT id, payload FROM public."{artifact_crash_table}"'
                                    )
                                ).all()
                                == []
                            )
                            assert (
                                connection.execute(
                                    text(
                                        f'SELECT effect_id FROM public."{artifact_crash_effects}"'
                                    )
                                ).all()
                                == []
                            )
                    finally:
                        artifact_effect_engine.dispose()
                finally:
                    artifact_write_release.touch(exist_ok=True)
                    try:
                        await asyncio.wait_for(artifact_write_worker, timeout=60)
                    except BaseException as exc:
                        artifact_write_worker_error = exc
                    for variable in (
                        "ETLANTIC_PHASE058_CRASH_DURING_ARTIFACT_WRITE_RUN_ID",
                        "ETLANTIC_PHASE058_CRASH_DURING_ARTIFACT_WRITE_MARKER",
                        "ETLANTIC_PHASE058_CRASH_DURING_ARTIFACT_WRITE_RELEASE",
                    ):
                        monkeypatch.delenv(variable, raising=False)
                assert artifact_write_worker_error is None, repr(
                    artifact_write_worker_error
                )
                artifact_write_attempt = backend.durable_work.list_attempts(
                    ctx, artifact_write_crash.submission_id
                )[0]
                backend.durable_work.release_lease(
                    ctx,
                    artifact_write_crash.submission_id,
                    owner_id=artifact_write_attempt.owner_id,
                    fencing_token=artifact_write_attempt.fencing_token,
                )
                artifact_worker_fixture = cast(
                    _InstalledWorkerBackendFixture,
                    importlib.import_module("phase058_worker_backend"),
                )
                artifact_recovery_backend, artifact_recovery_ctx = (
                    artifact_worker_fixture.build_backend()
                )
                try:
                    artifact_recovery = artifact_recovery_backend.execute_submission(
                        artifact_recovery_ctx,
                        artifact_write_crash.submission_id,
                        owner_id=f"phase058-artifact-write-recovery-{scope}",
                        execution_route=binding.execution_route,
                    )
                    assert artifact_recovery["status"] == "completed"
                    artifact_recovery_attempts = (
                        artifact_recovery_backend.durable_work.list_attempts(
                            artifact_recovery_ctx,
                            artifact_write_crash.submission_id,
                        )
                    )
                    assert [item.status for item in artifact_recovery_attempts] == [
                        "lost",
                        "completed",
                    ]
                    assert (
                        artifact_recovery_backend.durable_work.get_effect(
                            artifact_recovery_ctx,
                            f"{artifact_write_crash.submission_id}:execution",
                        ).status
                        == "committed"
                    )
                    artifact_report = (
                        artifact_recovery_backend.managed_service.get_run_report(
                            artifact_recovery_ctx,
                            str(artifact_write_crash.resource_id),
                        )
                    )
                    assert artifact_report["status"] == "succeeded"
                    durable_artifact_refs = [
                        item
                        for item in artifact_report.get("artifacts", [])
                        if item.get("strategy") == "durable"
                    ]
                    assert durable_artifact_refs
                    assert interrupted_target.is_relative_to(tmp_path / "artifacts")
                    assert interrupted_target.is_file()
                    assert not interrupted_temporary.exists()
                    assert any(
                        interrupted_target.name
                        == hashlib.sha256(
                            str(item["identity"]).encode("utf-8")
                        ).hexdigest()
                        + ".json"
                        for item in durable_artifact_refs
                    )
                    assert json.loads(
                        interrupted_target.read_text(encoding="utf-8")
                    ) == [{"id": row_id, "payload": payload}]
                finally:
                    artifact_recovery_backend.close()
                    artifact_worker_fixture.restore_test_execution_host_factory()
                artifact_effect_engine = create_engine(url, pool_pre_ping=True)
                try:
                    with artifact_effect_engine.connect() as connection:
                        assert connection.execute(
                            text(
                                f'SELECT id, payload FROM public."{artifact_crash_table}"'
                            )
                        ).all() == [(row_id, payload)]
                        assert connection.execute(
                            text(
                                f'SELECT row_count FROM public."{artifact_crash_effects}"'
                            )
                        ).all() == [(1,)]
                finally:
                    artifact_effect_engine.dispose()

                monkeypatch.setenv("ETLANTIC_PHASE058_POSTGRES_URL", url)
                source_kind = "postgresql"
                destination_table = cancelled_table
                destination_effects = cancelled_effects
                for key, value in {
                    "ETLANTIC_PHASE058_SOURCE_KIND": source_kind,
                    "ETLANTIC_PHASE058_DESTINATION_TABLE": destination_table,
                    "ETLANTIC_PHASE058_EFFECT_TABLE": destination_effects,
                }.items():
                    monkeypatch.setenv(key, value)

                source_kind = "csv"
                destination_table = outage_table
                destination_effects = outage_effects
                for key, value in {
                    "ETLANTIC_PHASE058_SOURCE_KIND": source_kind,
                    "ETLANTIC_PHASE058_DESTINATION_TABLE": destination_table,
                    "ETLANTIC_PHASE058_EFFECT_TABLE": destination_effects,
                }.items():
                    monkeypatch.setenv(key, value)
                outage_submission = managed.submit_run(
                    ctx,
                    "phase058-process-pipeline",
                    idempotency_key=f"phase058-prefect-api-outage-{scope}",
                    request=RunRequest(materialization=MaterializationPolicy.DURABLE),
                )
                outage_backlog = [outage_submission]
                outage_backlog_size = 32
                for backlog_index in range(outage_backlog_size - 1):
                    outage_backlog.append(
                        managed.submit_run(
                            ctx,
                            "phase058-process-pipeline",
                            idempotency_key=(
                                f"phase058-prefect-api-outage-{backlog_index + 1}-{scope}"
                            ),
                            request=RunRequest(
                                materialization=MaterializationPolicy.DURABLE
                            ),
                        )
                    )
                stop_prefect_server()
                for _ in range(4):
                    with pytest.raises(ConnectError):
                        await dispatcher.tick(limit=1)
                    for queued in outage_backlog:
                        assert (
                            backend.durable_work.get_submission(
                                ctx, queued.submission_id
                            ).status
                            == "accepted"
                        )
                        assert (
                            backend.durable_work.list_attempts(
                                ctx, queued.submission_id
                            )
                            == []
                        )
                outage_role_status = dispatcher.status()
                assert outage_role_status.admission == "accepting"
                assert outage_role_status.prerequisites == "unusable"
                assert outage_role_status.reason_code == "dispatch_tick_failed"
                assert outage_role_status.in_flight == 0
                outage_diagnostics = dispatcher.diagnostics()
                assert outage_diagnostics["failed_ticks"] == 4
                assert outage_diagnostics["dispatch_attempts"] == 0
                assert outage_diagnostics["uncertain_creates"] == 0
                assert outage_diagnostics["remote_api_failures"] == 4
                outage_engine = create_engine(url, pool_pre_ping=True)
                try:
                    with outage_engine.connect() as connection:
                        assert (
                            connection.execute(
                                text(f'SELECT id, payload FROM public."{outage_table}"')
                            ).all()
                            == []
                        )
                        assert (
                            connection.execute(
                                text(f'SELECT effect_id FROM public."{outage_effects}"')
                            ).all()
                            == []
                        )
                finally:
                    outage_engine.dispose()

                restart_prefect_server()
                for queued in outage_backlog:
                    recovered_outage_dispatch = await dispatcher.tick(limit=1)
                    assert len(recovered_outage_dispatch) == 1
                    assert (
                        recovered_outage_dispatch[0]["submission_id"]
                        == queued.submission_id
                    )
                    assert recovered_outage_dispatch[0]["status"] == "dispatched"
                    assert recovered_outage_dispatch[0]["queue_age_seconds"] >= 0
                assert dispatcher.status().ready is True
                recovered_diagnostics = dispatcher.diagnostics()
                assert recovered_diagnostics["ticks"] == 4 + outage_backlog_size
                assert recovered_diagnostics["failed_ticks"] == 4
                assert recovered_diagnostics["dispatch_attempts"] == outage_backlog_size
                assert recovered_diagnostics["remote_api_failures"] == 4
                queue_age_high_water = recovered_diagnostics[
                    "queue_age_high_water_seconds"
                ]
                assert isinstance(queue_age_high_water, (int, float))
                assert queue_age_high_water >= 0
                for backlog_index, queued in enumerate(outage_backlog):
                    await ProcessWorker(
                        work_pool_name=spec.work_pool_name,
                        name=(f"phase058-outage-recovery-{backlog_index}-{scope[:8]}"),
                    ).start(run_once=True, printer=lambda *_args, **_kwargs: None)
                    outage_attempts = backend.durable_work.list_attempts(
                        ctx, queued.submission_id
                    )
                    assert [item.status for item in outage_attempts] == ["completed"]
                    assert (
                        backend.durable_work.get_submission(
                            ctx, queued.submission_id
                        ).status
                        == "completed"
                    )
                    assert (
                        managed.get_run_report(ctx, str(queued.resource_id))["status"]
                        == "succeeded"
                    )
                outage_engine = create_engine(url, pool_pre_ping=True)
                try:
                    with outage_engine.connect() as connection:
                        assert connection.execute(
                            text(f'SELECT id, payload FROM public."{outage_table}"')
                        ).all() == [(row_id, payload)]
                        assert (
                            sorted(
                                connection.execute(
                                    text(
                                        f'SELECT row_count FROM public."{outage_effects}"'
                                    )
                                ).all()
                            )
                            == [(1,)] * outage_backlog_size
                        )
                finally:
                    outage_engine.dispose()

                source_kind = "csv"
                destination_table = mid_outage_table
                destination_effects = mid_outage_effects
                for key, value in {
                    "ETLANTIC_PHASE058_SOURCE_KIND": source_kind,
                    "ETLANTIC_PHASE058_DESTINATION_TABLE": destination_table,
                    "ETLANTIC_PHASE058_EFFECT_TABLE": destination_effects,
                }.items():
                    monkeypatch.setenv(key, value)
                mid_execution_outage = managed.submit_run(
                    ctx,
                    "phase058-process-pipeline",
                    idempotency_key=f"phase058-mid-execution-api-outage-{scope}",
                    request=RunRequest(materialization=MaterializationPolicy.DURABLE),
                )
                mid_outage_dispatch = await dispatcher.tick(limit=1)
                assert len(mid_outage_dispatch) == 1
                assert (
                    mid_outage_dispatch[0]["submission_id"]
                    == mid_execution_outage.submission_id
                )
                mid_outage_marker = tmp_path / f"phase058-mid-outage-{scope}"
                mid_outage_release = tmp_path / f"phase058-release-mid-outage-{scope}"
                for key, value in {
                    "ETLANTIC_PHASE058_HOLD_AFTER_ADAPTER_SUBMISSION": mid_execution_outage.submission_id,
                    "ETLANTIC_PHASE058_HOLD_AFTER_ADAPTER_MARKER": str(
                        mid_outage_marker
                    ),
                    "ETLANTIC_PHASE058_HOLD_AFTER_ADAPTER_RELEASE": str(
                        mid_outage_release
                    ),
                }.items():
                    monkeypatch.setenv(key, value)
                mid_outage_worker = asyncio.create_task(
                    ProcessWorker(
                        work_pool_name=spec.work_pool_name,
                        name=f"phase058-mid-outage-worker-{scope[:8]}",
                    ).start(run_once=True, printer=lambda *_args, **_kwargs: None)
                )
                mid_outage_worker_error: BaseException | None = None
                try:
                    await asyncio.wait_for(
                        asyncio.to_thread(_wait_for_marker, mid_outage_marker),
                        timeout=65,
                    )
                    mid_outage_attempts = backend.durable_work.list_attempts(
                        ctx, mid_execution_outage.submission_id
                    )
                    assert len(mid_outage_attempts) == 1
                    assert mid_outage_attempts[0].status == "running"
                    assert (
                        managed.get_run_report(
                            ctx, str(mid_execution_outage.resource_id)
                        )["status"]
                        == "succeeded"
                    )
                    mid_outage_publication = (
                        backend.durable_work.get_latest_result_publication(
                            ctx, mid_execution_outage.submission_id
                        )
                    )
                    assert mid_outage_publication is not None
                    assert mid_outage_publication.published_at is None
                    mid_outage_engine = create_engine(url, pool_pre_ping=True)
                    try:
                        with mid_outage_engine.connect() as connection:
                            assert connection.execute(
                                text(
                                    f'SELECT id, payload FROM public."{mid_outage_table}"'
                                )
                            ).all() == [(row_id, payload)]
                            assert connection.execute(
                                text(
                                    f'SELECT row_count FROM public."{mid_outage_effects}"'
                                )
                            ).all() == [(1,)]
                    finally:
                        mid_outage_engine.dispose()

                    stop_prefect_server()
                    mid_outage_reference = ManagedExecutionReference.from_submission(
                        backend.durable_work.get_submission(
                            ctx, mid_execution_outage.submission_id
                        )
                    ).to_dict()
                    mid_outage_status = await asyncio.to_thread(
                        get_managed_run_status, mid_outage_reference
                    )
                    assert mid_outage_status["remote_orchestration"]["status"] == (
                        "unavailable"
                    )
                    assert mid_outage_status["reconciliation"]["status"] == (
                        "unavailable"
                    )
                    assert mid_outage_status["status"] in {"dispatched", "running"}
                    assert backend.durable_work.get_submission(
                        ctx, mid_execution_outage.submission_id
                    ).status in {"dispatched", "running"}
                    restart_prefect_server()
                finally:
                    mid_outage_release.touch(exist_ok=True)
                    try:
                        await asyncio.wait_for(mid_outage_worker, timeout=60)
                    except BaseException as exc:
                        mid_outage_worker_error = exc
                    for variable in (
                        "ETLANTIC_PHASE058_HOLD_AFTER_ADAPTER_SUBMISSION",
                        "ETLANTIC_PHASE058_HOLD_AFTER_ADAPTER_MARKER",
                        "ETLANTIC_PHASE058_HOLD_AFTER_ADAPTER_RELEASE",
                    ):
                        monkeypatch.delenv(variable, raising=False)
                assert mid_outage_worker_error is None, repr(mid_outage_worker_error)
                mid_outage_record = backend.durable_work.get_submission(
                    ctx, mid_execution_outage.submission_id
                )
                assert mid_outage_record.status == "completed"
                assert [
                    item.status
                    for item in backend.durable_work.list_attempts(
                        ctx, mid_execution_outage.submission_id
                    )
                ] == ["completed"]
                assert (
                    managed.get_run_report(ctx, str(mid_execution_outage.resource_id))[
                        "status"
                    ]
                    == "succeeded"
                )
                mid_outage_engine = create_engine(url, pool_pre_ping=True)
                try:
                    with mid_outage_engine.connect() as connection:
                        assert connection.execute(
                            text(f'SELECT id, payload FROM public."{mid_outage_table}"')
                        ).all() == [(row_id, payload)]
                        assert connection.execute(
                            text(f'SELECT row_count FROM public."{mid_outage_effects}"')
                        ).all() == [(1,)]
                finally:
                    mid_outage_engine.dispose()

                source_kind = "postgresql"
                destination_table = cancelled_table
                destination_effects = cancelled_effects
                for key, value in {
                    "ETLANTIC_PHASE058_SOURCE_KIND": source_kind,
                    "ETLANTIC_PHASE058_DESTINATION_TABLE": destination_table,
                    "ETLANTIC_PHASE058_EFFECT_TABLE": destination_effects,
                }.items():
                    monkeypatch.setenv(key, value)

                after_effect_cancel = managed.submit_run(
                    ctx,
                    "phase058-process-pipeline",
                    idempotency_key=f"phase058-cancel-after-effects-{scope}",
                    request=RunRequest(materialization=MaterializationPolicy.DURABLE),
                )
                after_effect_dispatch = await dispatcher.tick(limit=1)
                assert len(after_effect_dispatch) == 1
                assert (
                    after_effect_dispatch[0]["submission_id"]
                    == after_effect_cancel.submission_id
                )
                after_effect_marker = tmp_path / f"phase058-after-effect-{scope}"
                after_effect_release = (
                    tmp_path / f"phase058-release-after-effect-{scope}"
                )
                cancel_observed_marker = tmp_path / f"phase058-cancel-observed-{scope}"
                finish_trace_path = tmp_path / f"phase058-cancel-finish-{scope}.json"
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_HOLD_AFTER_ADAPTER_SUBMISSION",
                    after_effect_cancel.submission_id,
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_HOLD_AFTER_ADAPTER_MARKER",
                    str(after_effect_marker),
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_HOLD_AFTER_ADAPTER_RELEASE",
                    str(after_effect_release),
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_HOLD_AFTER_ADAPTER_CANCEL_OBSERVED",
                    str(cancel_observed_marker),
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_TRACE_ATTEMPT_SUBMISSION",
                    after_effect_cancel.submission_id,
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_TRACE_ATTEMPT_PATH",
                    str(finish_trace_path),
                )
                after_effect_worker = asyncio.create_task(
                    ProcessWorker(
                        work_pool_name=spec.work_pool_name,
                        name=f"phase058-after-effect-worker-{scope[:8]}",
                    ).start(run_once=True, printer=lambda *_args, **_kwargs: None)
                )
                after_effect_worker_error: BaseException | None = None
                try:
                    await asyncio.wait_for(
                        asyncio.to_thread(_wait_for_marker, after_effect_marker),
                        timeout=65,
                    )
                    running_attempts = backend.durable_work.list_attempts(
                        ctx, after_effect_cancel.submission_id
                    )
                    assert len(running_attempts) == 1
                    assert running_attempts[0].status == "running"
                    durable_success_report = managed.get_run_report(
                        ctx, str(after_effect_cancel.resource_id)
                    )
                    assert durable_success_report["status"] == "succeeded"
                    pending_publication = (
                        backend.durable_work.get_latest_result_publication(
                            ctx, after_effect_cancel.submission_id
                        )
                    )
                    assert pending_publication is not None
                    assert pending_publication.published_at is None
                    effect_rows_before_cancel = effect_ledger_count()
                    assert effect_rows_before_cancel >= 1
                    effect_race_engine = create_engine(url, pool_pre_ping=True)
                    try:
                        with effect_race_engine.connect() as connection:
                            effect_race_rows = connection.execute(
                                text(
                                    f'SELECT id, payload FROM public."{cancelled_table}"'
                                )
                            ).all()
                            effect_race_ledger = connection.execute(
                                text(
                                    f'SELECT row_count FROM public."{cancelled_effects}"'
                                )
                            ).all()
                        assert effect_race_rows == [(row_id, payload)]
                        assert effect_race_ledger == [(1,)]
                    finally:
                        effect_race_engine.dispose()

                    cancel_receipt = managed.cancel_run(
                        ctx, str(after_effect_cancel.resource_id)
                    )
                    assert cancel_receipt["status"] == "cancel_requested"
                    await asyncio.wait_for(
                        asyncio.to_thread(_wait_for_marker, cancel_observed_marker),
                        timeout=10,
                    )
                    assert cancel_observed_marker.read_text(encoding="utf-8") == (
                        "observed"
                    )
                    assert (
                        backend.durable_work.get_submission(
                            ctx, after_effect_cancel.submission_id
                        ).status
                        == "cancel_requested"
                    )
                finally:
                    after_effect_release.touch(exist_ok=True)
                    try:
                        await asyncio.wait_for(after_effect_worker, timeout=60)
                    except BaseException as exc:
                        after_effect_worker_error = exc
                    for variable in (
                        "ETLANTIC_PHASE058_HOLD_AFTER_ADAPTER_SUBMISSION",
                        "ETLANTIC_PHASE058_HOLD_AFTER_ADAPTER_MARKER",
                        "ETLANTIC_PHASE058_HOLD_AFTER_ADAPTER_RELEASE",
                        "ETLANTIC_PHASE058_HOLD_AFTER_ADAPTER_CANCEL_OBSERVED",
                        "ETLANTIC_PHASE058_TRACE_ATTEMPT_SUBMISSION",
                        "ETLANTIC_PHASE058_TRACE_ATTEMPT_PATH",
                    ):
                        monkeypatch.delenv(variable, raising=False)
                assert after_effect_worker_error is None, repr(
                    after_effect_worker_error
                )
                finish_trace = json.loads(finish_trace_path.read_text(encoding="utf-8"))
                assert finish_trace == {
                    "cancel_event_set": True,
                    "outcome_status": "succeeded",
                }
                after_effect_record = backend.durable_work.get_submission(
                    ctx, after_effect_cancel.submission_id
                )
                assert after_effect_record.status == "completed"
                after_effect_attempts = backend.durable_work.list_attempts(
                    ctx, after_effect_cancel.submission_id
                )
                assert len(after_effect_attempts) == 1
                assert after_effect_attempts[0].status == "completed"
                after_effect_recorded = backend.durable_work.get_effect(
                    ctx, f"{after_effect_cancel.submission_id}:execution"
                )
                assert after_effect_recorded.status == "committed"
                assert effect_ledger_count() == effect_rows_before_cancel
                assert (
                    managed.get_run_report(ctx, str(after_effect_cancel.resource_id))[
                        "status"
                    ]
                    == "succeeded"
                )

                completed_reference = ManagedExecutionReference.from_submission(
                    after_effect_record
                ).to_dict()
                completed_observation = await asyncio.to_thread(
                    get_managed_run_status, completed_reference
                )
                assert completed_observation["status"] == "completed"
                assert (
                    completed_observation["remote_orchestration"]["status"]
                    == "Completed"
                )
                assert completed_observation["reconciliation"]["status"] == (
                    "consistent"
                )
                completed_flow_run_id = after_effect_dispatch[0]["prefect_flow_run_id"]
                assert isinstance(completed_flow_run_id, str)
                from prefect.states import Failed

                async with get_client() as client:
                    disagreement = await client.set_flow_run_state(
                        UUID(completed_flow_run_id),
                        Failed(message="phase 0.58 terminal disagreement fixture"),
                        force=True,
                    )
                    assert disagreement.status is not None
                remote_failed_observation = await asyncio.to_thread(
                    get_managed_run_status, completed_reference
                )
                assert remote_failed_observation["status"] == "completed"
                assert (
                    remote_failed_observation["remote_orchestration"]["status"]
                    == "Failed"
                )
                assert remote_failed_observation["reconciliation"]["status"] == (
                    "conflict"
                )
                assert (
                    backend.durable_work.get_submission(
                        ctx, after_effect_cancel.submission_id
                    ).status
                    == "completed"
                )
                assert (
                    backend.durable_work.list_attempts(
                        ctx, after_effect_cancel.submission_id
                    )[0].status
                    == "completed"
                )
                assert (
                    backend.durable_work.get_effect(
                        ctx, f"{after_effect_cancel.submission_id}:execution"
                    ).status
                    == "committed"
                )
                assert (
                    managed.get_run_report(ctx, str(after_effect_cancel.resource_id))[
                        "status"
                    ]
                    == "succeeded"
                )

                destination_table = commit_cancel_table
                destination_effects = commit_cancel_effects
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_DESTINATION_TABLE", destination_table
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_EFFECT_TABLE", destination_effects
                )
                commit_cancel = managed.submit_run(
                    ctx,
                    "phase058-process-pipeline",
                    idempotency_key=f"phase058-cancel-during-commit-{scope}",
                    request=RunRequest(materialization=MaterializationPolicy.DURABLE),
                )
                commit_cancel_dispatch = await dispatcher.tick(limit=1)
                assert len(commit_cancel_dispatch) == 1
                commit_marker = tmp_path / f"phase058-commit-marker-{scope}"
                commit_release = tmp_path / f"phase058-commit-release-{scope}"
                cancel_seen_marker = tmp_path / f"phase058-commit-cancel-seen-{scope}"
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_HOLD_BEFORE_CONNECTOR_COMMIT", "1"
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_COMMIT_HOLD_MARKER", str(commit_marker)
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_COMMIT_HOLD_RELEASE", str(commit_release)
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_OBSERVE_CANCEL_SUBMISSION",
                    commit_cancel.submission_id,
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_CANCEL_OBSERVED_MARKER",
                    str(cancel_seen_marker),
                )
                commit_cancel_worker = asyncio.create_task(
                    ProcessWorker(
                        work_pool_name=spec.work_pool_name,
                        name=f"phase058-commit-cancel-worker-{scope[:8]}",
                    ).start(run_once=True, printer=lambda *_args, **_kwargs: None)
                )
                commit_cancel_worker_error: BaseException | None = None
                try:
                    await asyncio.wait_for(
                        asyncio.to_thread(_wait_for_marker, commit_marker),
                        timeout=65,
                    )
                    held_attempts = backend.durable_work.list_attempts(
                        ctx, commit_cancel.submission_id
                    )
                    assert len(held_attempts) == 1
                    assert held_attempts[0].status == "running"
                    commit_engine = create_engine(url, pool_pre_ping=True)
                    try:
                        with commit_engine.connect() as connection:
                            assert (
                                connection.execute(
                                    text(
                                        f'SELECT id, payload FROM public."{commit_cancel_table}"'
                                    )
                                ).all()
                                == []
                            )
                            assert (
                                connection.execute(
                                    text(
                                        f'SELECT effect_id FROM public."{commit_cancel_effects}"'
                                    )
                                ).all()
                                == []
                            )
                    finally:
                        commit_engine.dispose()

                    commit_cancel_receipt = managed.cancel_run(
                        ctx, str(commit_cancel.resource_id)
                    )
                    assert commit_cancel_receipt["status"] == "cancel_requested"
                    await asyncio.wait_for(
                        asyncio.to_thread(_wait_for_marker, cancel_seen_marker),
                        timeout=10,
                    )
                    assert cancel_seen_marker.read_text(encoding="utf-8") == (
                        "observed"
                    )
                    commit_release.touch(exist_ok=True)
                    await asyncio.wait_for(commit_cancel_worker, timeout=60)
                except BaseException as exc:
                    commit_cancel_worker_error = exc
                finally:
                    commit_release.touch(exist_ok=True)
                    if not commit_cancel_worker.done():
                        try:
                            await asyncio.wait_for(commit_cancel_worker, timeout=60)
                        except BaseException as exc:
                            commit_cancel_worker_error = exc
                    for variable in (
                        "ETLANTIC_PHASE058_HOLD_BEFORE_CONNECTOR_COMMIT",
                        "ETLANTIC_PHASE058_COMMIT_HOLD_MARKER",
                        "ETLANTIC_PHASE058_COMMIT_HOLD_RELEASE",
                        "ETLANTIC_PHASE058_OBSERVE_CANCEL_SUBMISSION",
                        "ETLANTIC_PHASE058_CANCEL_OBSERVED_MARKER",
                    ):
                        monkeypatch.delenv(variable, raising=False)
                assert commit_cancel_worker_error is None, repr(
                    commit_cancel_worker_error
                )
                commit_cancel_record = backend.durable_work.get_submission(
                    ctx, commit_cancel.submission_id
                )
                assert commit_cancel_record.status == "cancelled"
                commit_cancel_attempts = backend.durable_work.list_attempts(
                    ctx, commit_cancel.submission_id
                )
                assert len(commit_cancel_attempts) == 1
                assert commit_cancel_attempts[0].status == "cancelled"
                commit_cancel_effect = backend.durable_work.get_effect(
                    ctx, f"{commit_cancel.submission_id}:execution"
                )
                assert commit_cancel_effect.status == "committed"
                commit_cancel_engine = create_engine(url, pool_pre_ping=True)
                try:
                    with commit_cancel_engine.connect() as connection:
                        assert connection.execute(
                            text(
                                f'SELECT id, payload FROM public."{commit_cancel_table}"'
                            )
                        ).all() == [(row_id, payload)]
                        assert connection.execute(
                            text(
                                f'SELECT row_count FROM public."{commit_cancel_effects}"'
                            )
                        ).all() == [(1,)]
                finally:
                    commit_cancel_engine.dispose()
                assert (
                    managed.get_run_report(ctx, str(commit_cancel.resource_id))[
                        "status"
                    ]
                    == "cancelled"
                )

                queued_revision_one = managed.submit_run(
                    ctx,
                    "phase058-process-pipeline",
                    idempotency_key=f"phase058-queued-revision-one-{scope}",
                    request=RunRequest(materialization=MaterializationPolicy.DURABLE),
                )
                spec_v2 = replace(
                    spec,
                    lockfile_sha256=hashlib.sha256(
                        f"phase058-revision-two-{scope}".encode()
                    ).hexdigest(),
                )
                preview_v2 = await registrar.preview(spec_v2)
                binding_v2 = await registrar.register(
                    spec_v2,
                    expected_fingerprint=preview_v2["spec"]["fingerprint"],
                )
                assert binding_v2.deployment_id != binding.deployment_id
                new_revision_dispatcher = PrefectDispatcher(
                    backend=backend,
                    context=ctx,
                    binding=binding_v2,
                    owner_id=f"dispatcher-v2-{scope}",
                )
                assert await new_revision_dispatcher.tick(limit=10) == []
                old_revision_dispatch = await dispatcher.tick(limit=1)
                assert len(old_revision_dispatch) == 1
                assert (
                    old_revision_dispatch[0]["submission_id"]
                    == queued_revision_one.submission_id
                )
                await ProcessWorker(
                    work_pool_name=spec.work_pool_name,
                    name=f"phase058-revision-one-worker-{scope[:8]}",
                ).start(run_once=True, printer=lambda *_args, **_kwargs: None)
                assert (
                    backend.durable_work.get_submission(
                        ctx, queued_revision_one.submission_id
                    ).status
                    == "completed"
                )
                assert (
                    managed.get_run_report(ctx, queued_revision_one.resource_id)[
                        "status"
                    ]
                    == "succeeded"
                )
                retained_dispatch = backend.durable_work.get_dispatch(
                    ctx, queued_revision_one.submission_id
                )
                assert retained_dispatch.execution_route == binding.execution_route
                async with get_client() as client:
                    retained_flow_run = await client.read_flow_run(
                        UUID(str(retained_dispatch.prefect_flow_run_id))
                    )
                assert retained_flow_run.deployment_id == binding.deployment_id

                contended = managed.submit_run(
                    ctx,
                    "phase058-process-pipeline",
                    idempotency_key=f"phase058-two-dispatchers-{scope}",
                    request=RunRequest(materialization=MaterializationPolicy.DURABLE),
                )
                from prefect.client import orchestration

                real_get_client = orchestration.get_client
                create_entered = asyncio.Event()
                allow_create = asyncio.Event()

                class _GatedClient:
                    def __init__(self) -> None:
                        self._manager = real_get_client()
                        self._client: Any = None

                    async def __aenter__(self) -> _GatedClient:
                        self._client = await self._manager.__aenter__()
                        return self

                    async def __aexit__(self, *args: Any) -> Any:
                        return await self._manager.__aexit__(*args)

                    def __getattr__(self, name: str) -> Any:
                        return getattr(self._client, name)

                    async def create_flow_run_from_deployment(
                        self, *args: Any, **kwargs: Any
                    ) -> Any:
                        create_entered.set()
                        await allow_create.wait()
                        return await self._client.create_flow_run_from_deployment(
                            *args, **kwargs
                        )

                def _get_gated_client(**_kwargs: Any) -> _GatedClient:
                    return _GatedClient()

                dispatcher_a = PrefectDispatcher(
                    backend=backend,
                    context=ctx,
                    binding=binding,
                    owner_id=f"dispatcher-race-a-{scope}",
                )
                dispatcher_b = PrefectDispatcher(
                    backend=backend,
                    context=ctx,
                    binding=binding,
                    owner_id=f"dispatcher-race-b-{scope}",
                )
                with monkeypatch.context() as patcher:
                    patcher.setattr(orchestration, "get_client", _get_gated_client)
                    first_dispatch_task = asyncio.create_task(
                        dispatcher_a.tick(limit=1)
                    )
                    try:
                        await asyncio.wait_for(create_entered.wait(), timeout=15)
                        second_dispatch_result = await dispatcher_b.tick(limit=1)
                        contended_dispatch = backend.durable_work.get_dispatch(
                            ctx, contended.submission_id
                        )
                        assert contended_dispatch.status == "leased"
                        assert contended_dispatch.dispatch_attempts == 1
                        assert second_dispatch_result == []
                    finally:
                        allow_create.set()
                    first_dispatch_result = await first_dispatch_task
                assert len(first_dispatch_result) == 1
                assert first_dispatch_result[0]["status"] == "dispatched"
                assert all(
                    item["submission_id"] == contended.submission_id
                    for item in second_dispatch_result
                )
                contended_dispatch = backend.durable_work.get_dispatch(
                    ctx, contended.submission_id
                )
                assert contended_dispatch.status == "dispatched"
                assert contended_dispatch.dispatch_attempts == 1
                assert contended_dispatch.prefect_flow_run_id is not None
                await ProcessWorker(
                    work_pool_name=spec.work_pool_name,
                    name=f"phase058-two-dispatchers-worker-{scope[:8]}",
                ).start(run_once=True, printer=lambda *_args, **_kwargs: None)
                assert (
                    backend.durable_work.get_submission(
                        ctx, contended.submission_id
                    ).status
                    == "completed"
                )
                assert (
                    len(
                        backend.durable_work.list_attempts(ctx, contended.submission_id)
                    )
                    == 1
                )

                duplicate = managed.submit_run(
                    ctx,
                    "phase058-process-pipeline",
                    idempotency_key=f"phase058-duplicate-workers-{scope}",
                    request=RunRequest(materialization=MaterializationPolicy.DURABLE),
                )
                duplicate_record = backend.durable_work.get_submission(
                    ctx, duplicate.submission_id
                )
                duplicate_dispatch = backend.durable_work.prepare_dispatch(
                    ctx, duplicate.submission_id
                )
                duplicate_claim = backend.durable_work.claim_dispatch(
                    ctx,
                    duplicate.submission_id,
                    owner_id=f"duplicate-dispatch-{scope}",
                    lease_seconds=300,
                )
                assert duplicate_claim is not None
                duplicate_reference = ManagedExecutionReference.from_submission(
                    duplicate_record
                ).to_dict()
                async with get_client() as client:
                    duplicate_runs = [
                        await client.create_flow_run_from_deployment(
                            binding.deployment_id,
                            parameters={"reference": duplicate_reference},
                            idempotency_key=f"duplicate-worker-{index}-{scope}",
                            name=f"etlantic-duplicate-{index}-{scope[:8]}",
                            tags=["etlantic-managed", "phase058-duplicate-worker"],
                        )
                        for index in (1, 2)
                    ]
                assert duplicate_runs[0].id != duplicate_runs[1].id
                await asyncio.gather(
                    ProcessWorker(
                        work_pool_name=spec.work_pool_name,
                        name=f"phase058-duplicate-worker-a-{scope[:8]}",
                    ).start(run_once=True, printer=lambda *_args, **_kwargs: None),
                    ProcessWorker(
                        work_pool_name=spec.work_pool_name,
                        name=f"phase058-duplicate-worker-b-{scope[:8]}",
                    ).start(run_once=True, printer=lambda *_args, **_kwargs: None),
                )
                duplicate_attempts = backend.durable_work.list_attempts(
                    ctx, duplicate.submission_id
                )
                assert len(duplicate_attempts) == 1
                assert duplicate_attempts[0].status == "completed"
                assert (
                    backend.durable_work.get_submission(
                        ctx, duplicate.submission_id
                    ).status
                    == "completed"
                )
                duplicate_report = managed.get_run_report(ctx, duplicate.resource_id)
                assert duplicate_report["status"] == "succeeded"
                linked_duplicate = backend.durable_work.link_dispatch(
                    ctx,
                    duplicate.submission_id,
                    owner_id=f"duplicate-dispatch-{scope}",
                    fencing_token=duplicate_claim.lease_fencing_token,
                    prefect_flow_run_id=str(duplicate_runs[0].id),
                )
                assert linked_duplicate.status == "dispatched"
                assert linked_duplicate.creation_key == duplicate_dispatch.creation_key
                async with get_client() as client:
                    duplicate_remote_runs = [
                        await client.read_flow_run(run.id) for run in duplicate_runs
                    ]
                assert all(
                    run.state is not None
                    and getattr(run.state.type, "value", run.state.type) == "COMPLETED"
                    for run in duplicate_remote_runs
                )

                crashed = managed.submit_run(
                    ctx,
                    "phase058-process-pipeline",
                    idempotency_key=f"phase058-crash-after-effect-{scope}",
                    request=RunRequest(materialization=MaterializationPolicy.DURABLE),
                )
                crash_dispatch = await dispatcher.tick(limit=1)
                assert len(crash_dispatch) == 1
                crash_flow_run_id = str(crash_dispatch[0]["prefect_flow_run_id"])

                effects_before_crash = effect_ledger_count()
                crash_marker = tmp_path / f"phase058-report-event-published-{scope}"
                crash_release = tmp_path / f"phase058-release-report-event-{scope}"
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_CRASH_AFTER_REPORT_EVENT_SUBMISSION",
                    crashed.submission_id,
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_CRASH_AFTER_REPORT_EVENT_MARKER",
                    str(crash_marker),
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_CRASH_AFTER_REPORT_EVENT_RELEASE",
                    str(crash_release),
                )
                crash_worker_task = asyncio.create_task(
                    ProcessWorker(
                        work_pool_name=spec.work_pool_name,
                        name=f"phase058-crash-worker-{scope[:8]}",
                    ).start(run_once=True, printer=lambda *_args, **_kwargs: None)
                )
                crash_worker_error: BaseException | None = None
                try:
                    await asyncio.wait_for(
                        asyncio.to_thread(_wait_for_marker, crash_marker), timeout=65
                    )
                    crash_attempts = backend.durable_work.list_attempts(
                        ctx, crashed.submission_id
                    )
                    assert len(crash_attempts) == 1
                    assert crash_attempts[0].status == "running"
                    crash_publication = (
                        backend.durable_work.get_latest_result_publication(
                            ctx, crashed.submission_id
                        )
                    )
                    assert crash_publication is not None
                    assert crash_publication.published_at is None
                    with pytest.raises(ControlPlaneError) as no_effect:
                        backend.durable_work.get_effect(
                            ctx, f"{crashed.submission_id}:execution"
                        )
                    assert no_effect.value.status == 404
                    assert effect_ledger_count() == effects_before_crash + 1
                    pre_recovery_events = [
                        event
                        for event in backend.events.list_after_cursor(
                            ctx, None, limit=1000
                        )
                        if dict(event.payload or {}).get("submission_id")
                        == crashed.submission_id
                        and event.kind in {"run.started", "run.completed"}
                    ]
                    assert [event.kind for event in pre_recovery_events].count(
                        "run.started"
                    ) == 1
                    assert [event.kind for event in pre_recovery_events].count(
                        "run.completed"
                    ) == 1
                    assert (
                        len(
                            {
                                dict(event.payload or {}).get("attempt_id")
                                for event in pre_recovery_events
                            }
                        )
                        == 1
                    )
                finally:
                    crash_release.touch(exist_ok=True)
                    try:
                        await asyncio.wait_for(crash_worker_task, timeout=60)
                    except BaseException as exc:
                        crash_worker_error = exc
                    for variable in (
                        "ETLANTIC_PHASE058_CRASH_AFTER_REPORT_EVENT_SUBMISSION",
                        "ETLANTIC_PHASE058_CRASH_AFTER_REPORT_EVENT_MARKER",
                        "ETLANTIC_PHASE058_CRASH_AFTER_REPORT_EVENT_RELEASE",
                    ):
                        monkeypatch.delenv(variable, raising=False)
                assert crash_worker_error is None, repr(crash_worker_error)
                async with get_client() as client:
                    crashed_remote = await client.read_flow_run(UUID(crash_flow_run_id))
                assert crashed_remote.state is not None
                assert getattr(
                    crashed_remote.state.type, "value", crashed_remote.state.type
                ) in {"CRASHED", "FAILED"}

                crashed_attempt = backend.durable_work.list_attempts(
                    ctx, crashed.submission_id
                )[0]
                backend.durable_work.release_lease(
                    ctx,
                    crashed.submission_id,
                    owner_id=crashed_attempt.owner_id,
                    fencing_token=crashed_attempt.fencing_token,
                )
                worker_backend_fixture = cast(
                    _InstalledWorkerBackendFixture,
                    importlib.import_module("phase058_worker_backend"),
                )

                recovery_backend, recovery_ctx = worker_backend_fixture.build_backend()
                try:
                    recovered = recovery_backend.execute_submission(
                        recovery_ctx,
                        crashed.submission_id,
                        owner_id=f"phase058-recovery-{scope}",
                        execution_route=binding.execution_route,
                    )
                    assert recovered["status"] == "completed"
                    assert recovered["executed"] is True
                    assert (
                        len(
                            recovery_backend.durable_work.list_attempts(
                                recovery_ctx, crashed.submission_id
                            )
                        )
                        == 2
                    )
                    recovered_attempts = recovery_backend.durable_work.list_attempts(
                        recovery_ctx, crashed.submission_id
                    )
                    assert [item.status for item in recovered_attempts] == [
                        "lost",
                        "completed",
                    ]
                    recovered_publication = (
                        recovery_backend.durable_work.get_latest_result_publication(
                            recovery_ctx, crashed.submission_id
                        )
                    )
                    assert recovered_publication is not None
                    assert recovered_publication.published_at is not None
                    assert (
                        recovery_backend.durable_work.get_effect(
                            recovery_ctx, f"{crashed.submission_id}:execution"
                        ).status
                        == "committed"
                    )
                    assert (
                        recovery_backend.managed_service.get_run_report(
                            recovery_ctx, str(crashed.resource_id)
                        )["status"]
                        == "succeeded"
                    )
                    recovered_events = [
                        event
                        for event in recovery_backend.events.list_after_cursor(
                            recovery_ctx, None, limit=1000
                        )
                        if dict(event.payload or {}).get("submission_id")
                        == crashed.submission_id
                        and event.kind in {"run.started", "run.completed"}
                    ]
                    assert [event.kind for event in recovered_events].count(
                        "run.started"
                    ) == 2
                    assert [event.kind for event in recovered_events].count(
                        "run.completed"
                    ) == 2
                    assert (
                        len(
                            {
                                dict(event.payload or {}).get("attempt_id")
                                for event in recovered_events
                            }
                        )
                        == 2
                    )
                    assert len({event.event_id for event in recovered_events}) == len(
                        recovered_events
                    )
                finally:
                    recovery_backend.close()
                    worker_backend_fixture.restore_test_execution_host_factory()
                assert effect_ledger_count() == effects_before_crash + 1

                # Crash independent dispatcher and worker processes while both
                # own durable work, then recover each boundary without replaying
                # the worker's already committed connector effect.
                source_kind = "postgresql"
                destination_table = postgres_postgres_table
                destination_effects = postgres_postgres_effects
                for key, value in {
                    "ETLANTIC_PHASE058_SOURCE_KIND": source_kind,
                    "ETLANTIC_PHASE058_DESTINATION_TABLE": destination_table,
                    "ETLANTIC_PHASE058_EFFECT_TABLE": destination_effects,
                }.items():
                    monkeypatch.setenv(key, value)
                concurrent_worker_crash = managed.submit_run(
                    ctx,
                    "phase058-process-pipeline",
                    idempotency_key=f"phase058-concurrent-role-crash-worker-{scope}",
                    request=RunRequest(materialization=MaterializationPolicy.DURABLE),
                )
                concurrent_worker_dispatch = await dispatcher.tick(limit=1)
                assert len(concurrent_worker_dispatch) == 1
                assert (
                    concurrent_worker_dispatch[0]["submission_id"]
                    == concurrent_worker_crash.submission_id
                )
                concurrent_effects_before = effect_ledger_count()
                concurrent_worker_marker = (
                    tmp_path / f"phase058-concurrent-worker-{scope}"
                )
                concurrent_worker_release = (
                    tmp_path / f"phase058-release-concurrent-worker-{scope}"
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_CRASH_AFTER_REPORT_EVENT_SUBMISSION",
                    concurrent_worker_crash.submission_id,
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_CRASH_AFTER_REPORT_EVENT_MARKER",
                    str(concurrent_worker_marker),
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_CRASH_AFTER_REPORT_EVENT_RELEASE",
                    str(concurrent_worker_release),
                )
                concurrent_worker_task = asyncio.create_task(
                    ProcessWorker(
                        work_pool_name=spec.work_pool_name,
                        name=f"phase058-concurrent-worker-{scope[:8]}",
                    ).start(run_once=True, printer=lambda *_args, **_kwargs: None)
                )
                concurrent_dispatch_crash = managed.submit_run(
                    ctx,
                    "phase058-process-pipeline",
                    idempotency_key=f"phase058-concurrent-role-crash-dispatch-{scope}",
                    request=RunRequest(materialization=MaterializationPolicy.DURABLE),
                )
                concurrent_dispatch_marker = (
                    tmp_path / f"phase058-concurrent-dispatch-{scope}"
                )
                concurrent_dispatch_release = (
                    tmp_path / f"phase058-release-concurrent-dispatch-{scope}"
                )
                concurrent_dispatch_env = os.environ.copy()
                concurrent_dispatch_env.update(
                    {
                        "ETLANTIC_PHASE058_DISPATCH_FAULT_STAGE": (
                            "before_remote_create"
                        ),
                        "ETLANTIC_PHASE058_DISPATCH_FAULT_MARKER": str(
                            concurrent_dispatch_marker
                        ),
                        "ETLANTIC_PHASE058_DISPATCH_FAULT_RELEASE": str(
                            concurrent_dispatch_release
                        ),
                        "ETLANTIC_PHASE058_DISPATCH_OWNER": (
                            f"dispatcher-concurrent-crash-{scope}"
                        ),
                    }
                )
                concurrent_dispatch_process = subprocess.Popen(
                    [sys.executable, "-c", dispatch_crash_code],
                    env=concurrent_dispatch_env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                concurrent_worker_error: BaseException | None = None
                concurrent_dispatch_error: BaseException | None = None
                try:
                    await asyncio.wait_for(
                        asyncio.to_thread(_wait_for_marker, concurrent_worker_marker),
                        timeout=65,
                    )
                    concurrent_dispatch_claim = backend.durable_work.get_dispatch(
                        ctx, concurrent_dispatch_crash.submission_id
                    )
                    assert concurrent_dispatch_claim.status == "leased"
                    assert concurrent_dispatch_claim.prefect_flow_run_id is None
                    assert concurrent_dispatch_claim.creation_key == (
                        concurrent_dispatch_marker.read_text(encoding="utf-8")
                    )
                    assert effect_ledger_count() == concurrent_effects_before + 1
                    concurrent_worker_attempts = backend.durable_work.list_attempts(
                        ctx, concurrent_worker_crash.submission_id
                    )
                    assert [item.status for item in concurrent_worker_attempts] == [
                        "running"
                    ]
                    concurrent_publication = (
                        backend.durable_work.get_latest_result_publication(
                            ctx, concurrent_worker_crash.submission_id
                        )
                    )
                    assert concurrent_publication is not None
                    assert concurrent_publication.published_at is None
                    await asyncio.wait_for(
                        asyncio.to_thread(_wait_for_marker, concurrent_dispatch_marker),
                        timeout=65,
                    )
                    concurrent_dispatch_claim = backend.durable_work.get_dispatch(
                        ctx, concurrent_dispatch_crash.submission_id
                    )
                    assert concurrent_dispatch_claim.status == "leased"
                    assert concurrent_dispatch_claim.prefect_flow_run_id is None
                finally:
                    concurrent_worker_release.touch(exist_ok=True)
                    concurrent_dispatch_release.touch(exist_ok=True)
                    try:
                        await asyncio.wait_for(concurrent_worker_task, timeout=60)
                    except BaseException as exc:
                        concurrent_worker_error = exc
                    try:
                        await asyncio.wait_for(
                            asyncio.to_thread(
                                concurrent_dispatch_process.communicate, timeout=60
                            ),
                            timeout=65,
                        )
                    except BaseException as exc:
                        concurrent_dispatch_error = exc
                    for variable in (
                        "ETLANTIC_PHASE058_CRASH_AFTER_REPORT_EVENT_SUBMISSION",
                        "ETLANTIC_PHASE058_CRASH_AFTER_REPORT_EVENT_MARKER",
                        "ETLANTIC_PHASE058_CRASH_AFTER_REPORT_EVENT_RELEASE",
                    ):
                        monkeypatch.delenv(variable, raising=False)
                assert concurrent_worker_error is None, repr(concurrent_worker_error)
                assert concurrent_dispatch_error is None, repr(
                    concurrent_dispatch_error
                )
                assert concurrent_dispatch_process.returncode == 74
                async with get_client() as client:
                    concurrent_worker_remote = await client.read_flow_run(
                        UUID(str(concurrent_worker_dispatch[0]["prefect_flow_run_id"]))
                    )
                assert concurrent_worker_remote.state is not None
                assert getattr(
                    concurrent_worker_remote.state.type,
                    "value",
                    concurrent_worker_remote.state.type,
                ) in {"CRASHED", "FAILED"}
                concurrent_worker_attempt = backend.durable_work.list_attempts(
                    ctx, concurrent_worker_crash.submission_id
                )[0]
                backend.durable_work.release_lease(
                    ctx,
                    concurrent_worker_crash.submission_id,
                    owner_id=concurrent_worker_attempt.owner_id,
                    fencing_token=concurrent_worker_attempt.fencing_token,
                )
                concurrent_recovery_backend, concurrent_recovery_ctx = (
                    worker_backend_fixture.build_backend()
                )
                try:
                    concurrent_recovered_worker = (
                        concurrent_recovery_backend.execute_submission(
                            concurrent_recovery_ctx,
                            concurrent_worker_crash.submission_id,
                            owner_id=f"phase058-concurrent-worker-recovery-{scope}",
                            execution_route=binding.execution_route,
                        )
                    )
                    assert concurrent_recovered_worker["status"] == "completed"
                    assert [
                        item.status
                        for item in concurrent_recovery_backend.durable_work.list_attempts(
                            concurrent_recovery_ctx,
                            concurrent_worker_crash.submission_id,
                        )
                    ] == ["lost", "completed"]
                    assert (
                        concurrent_recovery_backend.durable_work.get_effect(
                            concurrent_recovery_ctx,
                            f"{concurrent_worker_crash.submission_id}:execution",
                        ).status
                        == "committed"
                    )
                finally:
                    concurrent_recovery_backend.close()
                    worker_backend_fixture.restore_test_execution_host_factory()
                assert effect_ledger_count() == concurrent_effects_before + 1

                concurrent_dispatch_claim = backend.durable_work.get_dispatch(
                    ctx, concurrent_dispatch_crash.submission_id
                )
                assert concurrent_dispatch_claim.status == "leased"
                assert concurrent_dispatch_claim.prefect_flow_run_id is None
                assert concurrent_dispatch_claim.lease_expires_at is not None
                concurrent_dispatch_expiry = datetime.fromisoformat(
                    concurrent_dispatch_claim.lease_expires_at.replace("Z", "+00:00")
                )
                while concurrent_dispatch_expiry > datetime.now(UTC):
                    await asyncio.sleep(0.05)
                concurrent_recovery_dispatcher = PrefectDispatcher(
                    backend=backend,
                    context=ctx,
                    binding=binding,
                    owner_id=f"dispatcher-concurrent-recovery-{scope}",
                    lease_seconds=1,
                )
                concurrent_dispatch_receipts = (
                    await concurrent_recovery_dispatcher.tick(limit=1)
                )
                assert len(concurrent_dispatch_receipts) == 1
                assert (
                    concurrent_dispatch_receipts[0]["submission_id"]
                    == concurrent_dispatch_crash.submission_id
                )
                assert concurrent_dispatch_receipts[0]["status"] == "dispatched"
                recovered_concurrent_dispatch = backend.durable_work.get_dispatch(
                    ctx, concurrent_dispatch_crash.submission_id
                )
                assert recovered_concurrent_dispatch.creation_key == (
                    concurrent_dispatch_marker.read_text(encoding="utf-8")
                )
                await ProcessWorker(
                    work_pool_name=spec.work_pool_name,
                    name=f"phase058-concurrent-dispatch-recovery-worker-{scope[:8]}",
                ).start(run_once=True, printer=lambda *_args, **_kwargs: None)
                assert (
                    backend.durable_work.get_submission(
                        ctx, concurrent_dispatch_crash.submission_id
                    ).status
                    == "completed"
                )
                assert effect_ledger_count() == concurrent_effects_before + 2

                before_effect = managed.submit_run(
                    ctx,
                    "phase058-process-pipeline",
                    idempotency_key=f"phase058-crash-before-effect-{scope}",
                    request=RunRequest(materialization=MaterializationPolicy.DURABLE),
                )
                before_effect_dispatch = await dispatcher.tick(limit=1)
                assert len(before_effect_dispatch) == 1
                assert (
                    before_effect_dispatch[0]["submission_id"]
                    == before_effect.submission_id
                )
                effects_before_pre_effect_crash = effect_ledger_count()
                before_effect_marker = tmp_path / f"phase058-before-effect-{scope}"
                before_effect_release = (
                    tmp_path / f"phase058-release-before-effect-{scope}"
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_CRASH_BEFORE_ADAPTER_SUBMISSION",
                    before_effect.submission_id,
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_CRASH_BEFORE_ADAPTER_MARKER",
                    str(before_effect_marker),
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_CRASH_BEFORE_ADAPTER_RELEASE",
                    str(before_effect_release),
                )
                before_effect_worker_task = asyncio.create_task(
                    ProcessWorker(
                        work_pool_name=spec.work_pool_name,
                        name=f"phase058-before-effect-worker-{scope[:8]}",
                    ).start(run_once=True, printer=lambda *_args, **_kwargs: None)
                )
                before_effect_worker_error: BaseException | None = None
                try:
                    await asyncio.wait_for(
                        asyncio.to_thread(_wait_for_marker, before_effect_marker),
                        timeout=65,
                    )
                    before_effect_attempts = backend.durable_work.list_attempts(
                        ctx, before_effect.submission_id
                    )
                    assert len(before_effect_attempts) == 1
                    assert before_effect_attempts[0].status == "running"
                    before_effect_publication = (
                        backend.durable_work.get_latest_result_publication(
                            ctx, before_effect.submission_id
                        )
                    )
                    assert before_effect_publication is not None
                    assert before_effect_publication.published_at is None
                    with pytest.raises(ControlPlaneError) as no_pre_effect:
                        backend.durable_work.get_effect(
                            ctx, f"{before_effect.submission_id}:execution"
                        )
                    assert no_pre_effect.value.status == 404
                    assert effect_ledger_count() == effects_before_pre_effect_crash
                finally:
                    before_effect_release.touch(exist_ok=True)
                    try:
                        await asyncio.wait_for(before_effect_worker_task, timeout=60)
                    except BaseException as exc:
                        before_effect_worker_error = exc
                    for variable in (
                        "ETLANTIC_PHASE058_CRASH_BEFORE_ADAPTER_SUBMISSION",
                        "ETLANTIC_PHASE058_CRASH_BEFORE_ADAPTER_MARKER",
                        "ETLANTIC_PHASE058_CRASH_BEFORE_ADAPTER_RELEASE",
                    ):
                        monkeypatch.delenv(variable, raising=False)
                assert before_effect_worker_error is None, repr(
                    before_effect_worker_error
                )
                async with get_client() as client:
                    before_effect_remote = await client.read_flow_run(
                        UUID(str(before_effect_dispatch[0]["prefect_flow_run_id"]))
                    )
                assert before_effect_remote.state is not None
                assert getattr(
                    before_effect_remote.state.type,
                    "value",
                    before_effect_remote.state.type,
                ) in {"CRASHED", "FAILED"}

                before_effect_attempt = backend.durable_work.list_attempts(
                    ctx, before_effect.submission_id
                )[0]
                backend.durable_work.release_lease(
                    ctx,
                    before_effect.submission_id,
                    owner_id=before_effect_attempt.owner_id,
                    fencing_token=before_effect_attempt.fencing_token,
                )
                pre_effect_recovery_backend, pre_effect_recovery_ctx = (
                    worker_backend_fixture.build_backend()
                )
                try:
                    pre_effect_recovered = (
                        pre_effect_recovery_backend.execute_submission(
                            pre_effect_recovery_ctx,
                            before_effect.submission_id,
                            owner_id=f"phase058-pre-effect-recovery-{scope}",
                            execution_route=binding.execution_route,
                        )
                    )
                    assert pre_effect_recovered["status"] == "completed"
                    assert pre_effect_recovered["executed"] is True
                    pre_effect_attempts = (
                        pre_effect_recovery_backend.durable_work.list_attempts(
                            pre_effect_recovery_ctx, before_effect.submission_id
                        )
                    )
                    assert [item.status for item in pre_effect_attempts] == [
                        "lost",
                        "completed",
                    ]
                    assert (
                        pre_effect_recovery_backend.durable_work.get_effect(
                            pre_effect_recovery_ctx,
                            f"{before_effect.submission_id}:execution",
                        ).status
                        == "committed"
                    )
                    assert (
                        pre_effect_recovery_backend.managed_service.get_run_report(
                            pre_effect_recovery_ctx,
                            str(before_effect.resource_id),
                        )["status"]
                        == "succeeded"
                    )
                finally:
                    pre_effect_recovery_backend.close()
                    worker_backend_fixture.restore_test_execution_host_factory()
                assert effect_ledger_count() == effects_before_pre_effect_crash + 1

                destination_table = unsettled_table
                destination_effects = unsettled_effects
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_DESTINATION_TABLE", destination_table
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_EFFECT_TABLE", destination_effects
                )
                unsettled = managed.submit_run(
                    ctx,
                    "phase058-process-pipeline",
                    idempotency_key=f"phase058-crash-during-transaction-{scope}",
                    request=RunRequest(materialization=MaterializationPolicy.DURABLE),
                )
                unsettled_dispatch = await dispatcher.tick(limit=1)
                assert len(unsettled_dispatch) == 1
                assert unsettled_dispatch[0]["submission_id"] == unsettled.submission_id
                unsettled_marker = tmp_path / f"phase058-transaction-prepared-{scope}"
                unsettled_release = tmp_path / f"phase058-release-transaction-{scope}"
                monkeypatch.setenv("ETLANTIC_PHASE058_CRASH_AFTER_PREPARE", "1")
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_CRASH_AFTER_PREPARE_MARKER",
                    str(unsettled_marker),
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_CRASH_AFTER_PREPARE_RELEASE",
                    str(unsettled_release),
                )
                unsettled_worker_task = asyncio.create_task(
                    ProcessWorker(
                        work_pool_name=spec.work_pool_name,
                        name=f"phase058-unsettled-worker-{scope[:8]}",
                    ).start(run_once=True, printer=lambda *_args, **_kwargs: None)
                )
                unsettled_worker_error: BaseException | None = None
                try:
                    await asyncio.wait_for(
                        asyncio.to_thread(_wait_for_marker, unsettled_marker),
                        timeout=65,
                    )
                    unsettled_attempts = backend.durable_work.list_attempts(
                        ctx, unsettled.submission_id
                    )
                    assert len(unsettled_attempts) == 1
                    assert unsettled_attempts[0].status == "running"
                    unsettled_publication = (
                        backend.durable_work.get_latest_result_publication(
                            ctx, unsettled.submission_id
                        )
                    )
                    assert unsettled_publication is not None
                    assert unsettled_publication.published_at is None
                    with pytest.raises(ControlPlaneError) as no_commit_receipt:
                        backend.durable_work.get_effect(
                            ctx, f"{unsettled.submission_id}:execution"
                        )
                    assert no_commit_receipt.value.status == 404
                    unsettled_engine = create_engine(url, pool_pre_ping=True)
                    try:
                        with unsettled_engine.connect() as connection:
                            uncommitted_rows = connection.execute(
                                text(
                                    f'SELECT id, payload FROM public."{unsettled_table}"'
                                )
                            ).all()
                            uncommitted_effects = connection.execute(
                                text(
                                    f'SELECT effect_id FROM public."{unsettled_effects}"'
                                )
                            ).all()
                        assert uncommitted_rows == []
                        assert uncommitted_effects == []
                    finally:
                        unsettled_engine.dispose()
                finally:
                    unsettled_release.touch(exist_ok=True)
                    try:
                        await asyncio.wait_for(unsettled_worker_task, timeout=60)
                    except BaseException as exc:
                        unsettled_worker_error = exc
                    for variable in (
                        "ETLANTIC_PHASE058_CRASH_AFTER_PREPARE",
                        "ETLANTIC_PHASE058_CRASH_AFTER_PREPARE_MARKER",
                        "ETLANTIC_PHASE058_CRASH_AFTER_PREPARE_RELEASE",
                    ):
                        monkeypatch.delenv(variable, raising=False)
                assert unsettled_worker_error is None, repr(unsettled_worker_error)
                unsettled_engine = create_engine(url, pool_pre_ping=True)
                try:
                    with unsettled_engine.connect() as connection:
                        rolled_back_rows = connection.execute(
                            text(f'SELECT id, payload FROM public."{unsettled_table}"')
                        ).all()
                        rolled_back_effects = connection.execute(
                            text(f'SELECT effect_id FROM public."{unsettled_effects}"')
                        ).all()
                    assert rolled_back_rows == []
                    assert rolled_back_effects == []
                finally:
                    unsettled_engine.dispose()
                unsettled_attempt = backend.durable_work.list_attempts(
                    ctx, unsettled.submission_id
                )[0]
                backend.durable_work.release_lease(
                    ctx,
                    unsettled.submission_id,
                    owner_id=unsettled_attempt.owner_id,
                    fencing_token=unsettled_attempt.fencing_token,
                )
                unsettled_recovery_backend, unsettled_recovery_ctx = (
                    worker_backend_fixture.build_backend()
                )
                try:
                    unsettled_recovered = unsettled_recovery_backend.execute_submission(
                        unsettled_recovery_ctx,
                        unsettled.submission_id,
                        owner_id=f"phase058-unsettled-recovery-{scope}",
                        execution_route=binding.execution_route,
                    )
                    assert unsettled_recovered["status"] == "completed"
                    assert unsettled_recovered["executed"] is True
                    unsettled_attempts = (
                        unsettled_recovery_backend.durable_work.list_attempts(
                            unsettled_recovery_ctx, unsettled.submission_id
                        )
                    )
                    assert [item.status for item in unsettled_attempts] == [
                        "lost",
                        "completed",
                    ]
                    assert (
                        unsettled_recovery_backend.durable_work.get_effect(
                            unsettled_recovery_ctx,
                            f"{unsettled.submission_id}:execution",
                        ).status
                        == "committed"
                    )
                    assert (
                        unsettled_recovery_backend.managed_service.get_run_report(
                            unsettled_recovery_ctx, str(unsettled.resource_id)
                        )["status"]
                        == "succeeded"
                    )
                finally:
                    unsettled_recovery_backend.close()
                    worker_backend_fixture.restore_test_execution_host_factory()
                unsettled_engine = create_engine(url, pool_pre_ping=True)
                try:
                    with unsettled_engine.connect() as connection:
                        recovered_rows = connection.execute(
                            text(f'SELECT id, payload FROM public."{unsettled_table}"')
                        ).all()
                        recovered_effects = connection.execute(
                            text(f'SELECT row_count FROM public."{unsettled_effects}"')
                        ).all()
                    assert recovered_rows == [(row_id, payload)]
                    assert recovered_effects == [(1,)]
                finally:
                    unsettled_engine.dispose()
                destination_table = partial_table
                destination_effects = partial_effects
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_DESTINATION_TABLE", destination_table
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_EFFECT_TABLE", destination_effects
                )
                partial = managed.submit_run(
                    ctx,
                    "phase058-process-pipeline",
                    idempotency_key=f"phase058-crash-during-partial-write-{scope}",
                    request=RunRequest(materialization=MaterializationPolicy.DURABLE),
                )
                partial_dispatch = await dispatcher.tick(limit=1)
                assert len(partial_dispatch) == 1
                assert partial_dispatch[0]["submission_id"] == partial.submission_id
                partial_marker = tmp_path / f"phase058-partial-delete-{scope}"
                partial_release = tmp_path / f"phase058-release-partial-delete-{scope}"
                monkeypatch.setenv("ETLANTIC_PHASE058_CRASH_AFTER_DELETE", "1")
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_CRASH_AFTER_DELETE_MARKER",
                    str(partial_marker),
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_CRASH_AFTER_DELETE_RELEASE",
                    str(partial_release),
                )
                partial_worker_task = asyncio.create_task(
                    ProcessWorker(
                        work_pool_name=spec.work_pool_name,
                        name=f"phase058-partial-write-worker-{scope[:8]}",
                    ).start(run_once=True, printer=lambda *_args, **_kwargs: None)
                )
                partial_worker_error: BaseException | None = None
                try:
                    await asyncio.wait_for(
                        asyncio.to_thread(_wait_for_marker, partial_marker),
                        timeout=65,
                    )
                    partial_engine = create_engine(url, pool_pre_ping=True)
                    try:
                        with partial_engine.connect() as connection:
                            rows_during_partial = connection.execute(
                                text(
                                    f'SELECT id, payload FROM public."{partial_table}"'
                                )
                            ).all()
                            effects_during_partial = connection.execute(
                                text(
                                    f'SELECT effect_id FROM public."{partial_effects}"'
                                )
                            ).all()
                        assert rows_during_partial == [
                            (f"stale-{row_id}", "pre-existing")
                        ]
                        assert effects_during_partial == []
                    finally:
                        partial_engine.dispose()
                finally:
                    partial_release.touch(exist_ok=True)
                    try:
                        await asyncio.wait_for(partial_worker_task, timeout=60)
                    except BaseException as exc:
                        partial_worker_error = exc
                    for variable in (
                        "ETLANTIC_PHASE058_CRASH_AFTER_DELETE",
                        "ETLANTIC_PHASE058_CRASH_AFTER_DELETE_MARKER",
                        "ETLANTIC_PHASE058_CRASH_AFTER_DELETE_RELEASE",
                    ):
                        monkeypatch.delenv(variable, raising=False)
                assert partial_worker_error is None, repr(partial_worker_error)
                partial_engine = create_engine(url, pool_pre_ping=True)
                try:
                    with partial_engine.connect() as connection:
                        rolled_back_partial_rows = connection.execute(
                            text(f'SELECT id, payload FROM public."{partial_table}"')
                        ).all()
                        rolled_back_partial_effects = connection.execute(
                            text(f'SELECT effect_id FROM public."{partial_effects}"')
                        ).all()
                    assert rolled_back_partial_rows == [
                        (f"stale-{row_id}", "pre-existing")
                    ]
                    assert rolled_back_partial_effects == []
                finally:
                    partial_engine.dispose()
                with pytest.raises(ControlPlaneError) as no_partial_effect:
                    backend.durable_work.get_effect(
                        ctx, f"{partial.submission_id}:execution"
                    )
                assert no_partial_effect.value.status == 404
                partial_attempt = backend.durable_work.list_attempts(
                    ctx, partial.submission_id
                )[0]
                backend.durable_work.release_lease(
                    ctx,
                    partial.submission_id,
                    owner_id=partial_attempt.owner_id,
                    fencing_token=partial_attempt.fencing_token,
                )
                partial_recovery_backend, partial_recovery_ctx = (
                    worker_backend_fixture.build_backend()
                )
                try:
                    partial_recovered = partial_recovery_backend.execute_submission(
                        partial_recovery_ctx,
                        partial.submission_id,
                        owner_id=f"phase058-partial-recovery-{scope}",
                        execution_route=binding.execution_route,
                    )
                    assert partial_recovered["status"] == "completed"
                    assert partial_recovered["executed"] is True
                    partial_attempts = (
                        partial_recovery_backend.durable_work.list_attempts(
                            partial_recovery_ctx, partial.submission_id
                        )
                    )
                    assert [attempt.status for attempt in partial_attempts] == [
                        "lost",
                        "completed",
                    ]
                    assert (
                        partial_recovery_backend.durable_work.get_effect(
                            partial_recovery_ctx,
                            f"{partial.submission_id}:execution",
                        ).status
                        == "committed"
                    )
                finally:
                    partial_recovery_backend.close()
                    worker_backend_fixture.restore_test_execution_host_factory()
                partial_engine = create_engine(url, pool_pre_ping=True)
                try:
                    with partial_engine.connect() as connection:
                        recovered_partial_rows = connection.execute(
                            text(f'SELECT id, payload FROM public."{partial_table}"')
                        ).all()
                        recovered_partial_effects = connection.execute(
                            text(f'SELECT row_count FROM public."{partial_effects}"')
                        ).all()
                    assert recovered_partial_rows == [(row_id, payload)]
                    assert recovered_partial_effects == [(1,)]
                finally:
                    partial_engine.dispose()
                destination_table = postgres_postgres_table
                destination_effects = postgres_postgres_effects
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_DESTINATION_TABLE", destination_table
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_EFFECT_TABLE", destination_effects
                )

                destination_table = policy_denied_table
                destination_effects = policy_denied_effects
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_DESTINATION_TABLE", destination_table
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_EFFECT_TABLE", destination_effects
                )
                revoked = managed.submit_run(
                    ctx,
                    "phase058-process-pipeline",
                    idempotency_key=f"phase058-policy-revoked-before-execution-{scope}",
                    request=RunRequest(materialization=MaterializationPolicy.DURABLE),
                )
                assert (
                    backend.durable_work.get_submission(
                        ctx, revoked.submission_id
                    ).policy_fingerprint
                    is not None
                )
                revoked_dispatch = await dispatcher.tick(limit=1)
                assert len(revoked_dispatch) == 1
                assert revoked_dispatch[0]["submission_id"] == revoked.submission_id
                monkeypatch.setenv("ETLANTIC_PHASE058_DENY_PRE_EXECUTION", "1")
                try:
                    await ProcessWorker(
                        work_pool_name=spec.work_pool_name,
                        name=f"phase058-policy-denied-worker-{scope[:8]}",
                    ).start(run_once=True, printer=lambda *_args, **_kwargs: None)
                finally:
                    monkeypatch.delenv(
                        "ETLANTIC_PHASE058_DENY_PRE_EXECUTION", raising=False
                    )
                revoked_record = backend.durable_work.get_submission(
                    ctx, revoked.submission_id
                )
                assert revoked_record.status == "failed"
                revoked_attempts = backend.durable_work.list_attempts(
                    ctx, revoked.submission_id
                )
                assert len(revoked_attempts) == 1
                assert revoked_attempts[0].status == "failed"
                with pytest.raises(ControlPlaneError) as no_revoked_effect:
                    backend.durable_work.get_effect(
                        ctx, f"{revoked.submission_id}:execution"
                    )
                assert no_revoked_effect.value.status == 404
                revoked_engine = create_engine(url, pool_pre_ping=True)
                try:
                    with revoked_engine.connect() as connection:
                        denied_rows = connection.execute(
                            text(
                                f'SELECT id, payload FROM public."{policy_denied_table}"'
                            )
                        ).all()
                        denied_effects = connection.execute(
                            text(
                                f'SELECT effect_id FROM public."{policy_denied_effects}"'
                            )
                        ).all()
                    assert denied_rows == []
                    assert denied_effects == []
                finally:
                    revoked_engine.dispose()

                authz_revoked = managed.submit_run(
                    ctx,
                    "phase058-process-pipeline",
                    idempotency_key=f"phase058-authz-revoked-before-execution-{scope}",
                    request=RunRequest(materialization=MaterializationPolicy.DURABLE),
                )
                assert (
                    backend.durable_work.get_submission(
                        ctx, authz_revoked.submission_id
                    ).policy_fingerprint
                    is not None
                )
                authz_revoked_dispatch = await dispatcher.tick(limit=1)
                assert len(authz_revoked_dispatch) == 1
                assert (
                    authz_revoked_dispatch[0]["submission_id"]
                    == authz_revoked.submission_id
                )
                monkeypatch.setenv("ETLANTIC_PHASE058_DENY_RUN_SUBMIT", "1")
                try:
                    await ProcessWorker(
                        work_pool_name=spec.work_pool_name,
                        name=f"phase058-authz-denied-worker-{scope[:8]}",
                    ).start(run_once=True, printer=lambda *_args, **_kwargs: None)
                finally:
                    monkeypatch.delenv(
                        "ETLANTIC_PHASE058_DENY_RUN_SUBMIT", raising=False
                    )
                authz_revoked_record = backend.durable_work.get_submission(
                    ctx, authz_revoked.submission_id
                )
                assert authz_revoked_record.status == "failed"
                authz_revoked_attempts = backend.durable_work.list_attempts(
                    ctx, authz_revoked.submission_id
                )
                assert len(authz_revoked_attempts) == 1
                assert authz_revoked_attempts[0].status == "failed"
                with pytest.raises(ControlPlaneError) as no_authz_revoked_effect:
                    backend.durable_work.get_effect(
                        ctx, f"{authz_revoked.submission_id}:execution"
                    )
                assert no_authz_revoked_effect.value.status == 404
                authz_revoked_engine = create_engine(url, pool_pre_ping=True)
                try:
                    with authz_revoked_engine.connect() as connection:
                        denied_rows = connection.execute(
                            text(
                                f'SELECT id, payload FROM public."{policy_denied_table}"'
                            )
                        ).all()
                        denied_effects = connection.execute(
                            text(
                                f'SELECT effect_id FROM public."{policy_denied_effects}"'
                            )
                        ).all()
                    assert denied_rows == []
                    assert denied_effects == []
                finally:
                    authz_revoked_engine.dispose()

                worker_authz_revoked = managed.submit_run(
                    ctx,
                    "phase058-process-pipeline",
                    idempotency_key=f"phase058-worker-identity-revoked-{scope}",
                    request=RunRequest(materialization=MaterializationPolicy.DURABLE),
                )
                worker_authz_dispatch = await dispatcher.tick(limit=1)
                assert len(worker_authz_dispatch) == 1
                assert (
                    worker_authz_dispatch[0]["submission_id"]
                    == worker_authz_revoked.submission_id
                )
                monkeypatch.setenv("ETLANTIC_PHASE058_DISTINCT_WORKER_IDENTITY", "1")
                monkeypatch.setenv("ETLANTIC_PHASE058_DENY_WORKER_EXECUTE", "1")
                try:
                    await ProcessWorker(
                        work_pool_name=spec.work_pool_name,
                        name=f"phase058-worker-identity-denied-{scope[:8]}",
                    ).start(run_once=True, printer=lambda *_args, **_kwargs: None)
                finally:
                    monkeypatch.delenv(
                        "ETLANTIC_PHASE058_DISTINCT_WORKER_IDENTITY", raising=False
                    )
                    monkeypatch.delenv(
                        "ETLANTIC_PHASE058_DENY_WORKER_EXECUTE", raising=False
                    )
                worker_authz_record = backend.durable_work.get_submission(
                    ctx, worker_authz_revoked.submission_id
                )
                assert worker_authz_record.status == "failed"
                worker_authz_attempts = backend.durable_work.list_attempts(
                    ctx, worker_authz_revoked.submission_id
                )
                assert len(worker_authz_attempts) == 1
                assert worker_authz_attempts[0].status == "failed"
                with pytest.raises(ControlPlaneError) as no_worker_authz_effect:
                    backend.durable_work.get_effect(
                        ctx, f"{worker_authz_revoked.submission_id}:execution"
                    )
                assert no_worker_authz_effect.value.status == 404
                worker_authz_engine = create_engine(url, pool_pre_ping=True)
                try:
                    with worker_authz_engine.connect() as connection:
                        denied_rows = connection.execute(
                            text(
                                f'SELECT id, payload FROM public."{policy_denied_table}"'
                            )
                        ).all()
                        denied_effects = connection.execute(
                            text(
                                f'SELECT effect_id FROM public."{policy_denied_effects}"'
                            )
                        ).all()
                    assert denied_rows == []
                    assert denied_effects == []
                finally:
                    worker_authz_engine.dispose()

                destination_table = approval_denied_table
                destination_effects = approval_denied_effects
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_DESTINATION_TABLE", destination_table
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_EFFECT_TABLE", destination_effects
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_REQUIRE_PRE_EXECUTION_APPROVAL", "1"
                )
                approval_policy = MemoryPolicyProvider()
                approval_policy.set_rule("pre_execution", "require_approval")
                managed.policy = approval_policy
                approval_store = SQLModelApprovalStore(
                    backend.engine, store_id=f"{store_id}:approvals"
                )
                managed.approvals = approval_store

                approval_revoked_before_dispatch = managed.submit_run(
                    ctx,
                    "phase058-process-pipeline",
                    idempotency_key=f"phase058-approval-revoked-before-dispatch-{scope}",
                    request=RunRequest(materialization=MaterializationPolicy.DURABLE),
                )
                approval_record = backend.durable_work.get_submission(
                    ctx, approval_revoked_before_dispatch.submission_id
                )
                assert approval_record.input_snapshot is not None
                approval_envelope = ExecutionEnvelope.from_json(
                    approval_record.input_snapshot
                )
                approval_decision = approval_policy.decide(
                    ctx,
                    hook="pre_execution",
                    plan_fingerprint=approval_envelope.effective_fingerprint,
                    revision_id=approval_envelope.revision_id,
                    resource=f"definition:{approval_envelope.definition_id}",
                )
                approval_request = approval_store.create(
                    ctx,
                    hook="pre_execution",
                    plan_fingerprint=approval_envelope.effective_fingerprint,
                    policy_fingerprint=approval_decision.policy_fingerprint,
                    revision_id=approval_envelope.revision_id,
                )
                reviewer = replace(
                    ctx,
                    principal=Principal(
                        subject=f"reviewer-{scope}",
                        issuer="phase058-tests",
                        kind="human",
                    ),
                )
                approval_store.decide(
                    reviewer,
                    approval_id=approval_request.approval_id,
                    approve=True,
                    plan_fingerprint=approval_envelope.effective_fingerprint,
                    policy_fingerprint=approval_decision.policy_fingerprint,
                )
                approval_store.revoke(
                    ctx,
                    approval_id=approval_request.approval_id,
                    reason="revoked after acceptance before dispatch",
                )
                approval_dispatch = await dispatcher.tick(limit=1)
                assert len(approval_dispatch) == 1
                assert (
                    approval_dispatch[0]["submission_id"]
                    == approval_revoked_before_dispatch.submission_id
                )
                await ProcessWorker(
                    work_pool_name=spec.work_pool_name,
                    name=f"phase058-approval-revoked-before-dispatch-{scope[:8]}",
                ).start(run_once=True, printer=lambda *_args, **_kwargs: None)
                revoked_before_dispatch_record = backend.durable_work.get_submission(
                    ctx, approval_revoked_before_dispatch.submission_id
                )
                assert revoked_before_dispatch_record.status == "failed"
                revoked_before_dispatch_attempts = backend.durable_work.list_attempts(
                    ctx, approval_revoked_before_dispatch.submission_id
                )
                assert len(revoked_before_dispatch_attempts) == 1
                assert revoked_before_dispatch_attempts[0].status == "failed"
                with pytest.raises(
                    ControlPlaneError
                ) as no_revoked_before_dispatch_effect:
                    backend.durable_work.get_effect(
                        ctx,
                        f"{approval_revoked_before_dispatch.submission_id}:execution",
                    )
                assert no_revoked_before_dispatch_effect.value.status == 404
                revoked_before_dispatch_engine = create_engine(url, pool_pre_ping=True)
                try:
                    with revoked_before_dispatch_engine.connect() as connection:
                        assert (
                            connection.execute(
                                text(
                                    f'SELECT id, payload FROM public."{approval_denied_table}"'
                                )
                            ).all()
                            == []
                        )
                        assert (
                            connection.execute(
                                text(
                                    f'SELECT effect_id FROM public."{approval_denied_effects}"'
                                )
                            ).all()
                            == []
                        )
                finally:
                    revoked_before_dispatch_engine.dispose()

                approval_revoked = managed.submit_run(
                    ctx,
                    "phase058-process-pipeline",
                    idempotency_key=f"phase058-approval-revoked-before-claim-{scope}",
                    request=RunRequest(materialization=MaterializationPolicy.DURABLE),
                )
                approval_record = backend.durable_work.get_submission(
                    ctx, approval_revoked.submission_id
                )
                assert approval_record.input_snapshot is not None
                approval_envelope = ExecutionEnvelope.from_json(
                    approval_record.input_snapshot
                )
                approval_decision = approval_policy.decide(
                    ctx,
                    hook="pre_execution",
                    plan_fingerprint=approval_envelope.effective_fingerprint,
                    revision_id=approval_envelope.revision_id,
                    resource=f"definition:{approval_envelope.definition_id}",
                )
                approval_request = approval_store.create(
                    ctx,
                    hook="pre_execution",
                    plan_fingerprint=approval_envelope.effective_fingerprint,
                    policy_fingerprint=approval_decision.policy_fingerprint,
                    revision_id=approval_envelope.revision_id,
                )
                reviewer = replace(
                    ctx,
                    principal=Principal(
                        subject=f"reviewer-{scope}",
                        issuer="phase058-tests",
                        kind="human",
                    ),
                )
                approval_store.decide(
                    reviewer,
                    approval_id=approval_request.approval_id,
                    approve=True,
                    plan_fingerprint=approval_envelope.effective_fingerprint,
                    policy_fingerprint=approval_decision.policy_fingerprint,
                )
                approval_dispatch = await dispatcher.tick(limit=1)
                assert len(approval_dispatch) == 1
                assert (
                    approval_dispatch[0]["submission_id"]
                    == approval_revoked.submission_id
                )
                approval_store.revoke(
                    ctx,
                    approval_id=approval_request.approval_id,
                    reason="revoked after dispatch before worker claim",
                )
                try:
                    await ProcessWorker(
                        work_pool_name=spec.work_pool_name,
                        name=f"phase058-approval-revoked-worker-{scope[:8]}",
                    ).start(run_once=True, printer=lambda *_args, **_kwargs: None)
                finally:
                    monkeypatch.delenv(
                        "ETLANTIC_PHASE058_REQUIRE_PRE_EXECUTION_APPROVAL",
                        raising=False,
                    )
                    managed.policy.set_rule("pre_execution", "allow")
                approval_record = backend.durable_work.get_submission(
                    ctx, approval_revoked.submission_id
                )
                assert approval_record.status == "failed"
                approval_attempts = backend.durable_work.list_attempts(
                    ctx, approval_revoked.submission_id
                )
                assert len(approval_attempts) == 1
                assert approval_attempts[0].status == "failed"
                with pytest.raises(ControlPlaneError) as no_approval_effect:
                    backend.durable_work.get_effect(
                        ctx, f"{approval_revoked.submission_id}:execution"
                    )
                assert no_approval_effect.value.status == 404
                approval_engine = create_engine(url, pool_pre_ping=True)
                try:
                    with approval_engine.connect() as connection:
                        denied_rows = connection.execute(
                            text(
                                f'SELECT id, payload FROM public."{approval_denied_table}"'
                            )
                        ).all()
                        denied_effects = connection.execute(
                            text(
                                f'SELECT effect_id FROM public."{approval_denied_effects}"'
                            )
                        ).all()
                    assert denied_rows == []
                    assert denied_effects == []
                finally:
                    approval_engine.dispose()

                # An approval that was valid when accepted and dispatched must
                # still be rechecked at worker claim. Advance only the worker
                # fixture's clock so this boundary is deterministic and fast.
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_REQUIRE_PRE_EXECUTION_APPROVAL", "1"
                )
                approval_policy.set_rule("pre_execution", "require_approval")
                expired_approval = managed.submit_run(
                    ctx,
                    "phase058-process-pipeline",
                    idempotency_key=f"phase058-approval-expired-before-claim-{scope}",
                    request=RunRequest(materialization=MaterializationPolicy.DURABLE),
                )
                expired_record = backend.durable_work.get_submission(
                    ctx, expired_approval.submission_id
                )
                assert expired_record.input_snapshot is not None
                expired_envelope = ExecutionEnvelope.from_json(
                    expired_record.input_snapshot
                )
                expired_decision = approval_policy.decide(
                    ctx,
                    hook="pre_execution",
                    plan_fingerprint=expired_envelope.effective_fingerprint,
                    revision_id=expired_envelope.revision_id,
                    resource=f"definition:{expired_envelope.definition_id}",
                )
                expired_at = datetime.now(UTC) + timedelta(minutes=5)
                expired_request = approval_store.create(
                    ctx,
                    hook="pre_execution",
                    plan_fingerprint=expired_envelope.effective_fingerprint,
                    policy_fingerprint=expired_decision.policy_fingerprint,
                    revision_id=expired_envelope.revision_id,
                    expires_at=expired_at,
                )
                approval_store.decide(
                    reviewer,
                    approval_id=expired_request.approval_id,
                    approve=True,
                    plan_fingerprint=expired_envelope.effective_fingerprint,
                    policy_fingerprint=expired_decision.policy_fingerprint,
                )
                expired_dispatch = await dispatcher.tick(limit=1)
                assert len(expired_dispatch) == 1
                assert (
                    expired_dispatch[0]["submission_id"]
                    == expired_approval.submission_id
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_APPROVAL_NOW",
                    (expired_at + timedelta(seconds=1)).isoformat(),
                )
                try:
                    await ProcessWorker(
                        work_pool_name=spec.work_pool_name,
                        name=f"phase058-approval-expired-worker-{scope[:8]}",
                    ).start(run_once=True, printer=lambda *_args, **_kwargs: None)
                finally:
                    monkeypatch.delenv("ETLANTIC_PHASE058_APPROVAL_NOW", raising=False)
                    monkeypatch.delenv(
                        "ETLANTIC_PHASE058_REQUIRE_PRE_EXECUTION_APPROVAL",
                        raising=False,
                    )
                    approval_policy.set_rule("pre_execution", "allow")
                expired_record = backend.durable_work.get_submission(
                    ctx, expired_approval.submission_id
                )
                assert expired_record.status == "failed"
                expired_attempts = backend.durable_work.list_attempts(
                    ctx, expired_approval.submission_id
                )
                assert len(expired_attempts) == 1
                assert expired_attempts[0].status == "failed"
                with pytest.raises(ControlPlaneError) as no_expired_approval_effect:
                    backend.durable_work.get_effect(
                        ctx, f"{expired_approval.submission_id}:execution"
                    )
                assert no_expired_approval_effect.value.status == 404
                expired_engine = create_engine(url, pool_pre_ping=True)
                try:
                    with expired_engine.connect() as connection:
                        assert (
                            connection.execute(
                                text(
                                    f'SELECT id, payload FROM public."{approval_denied_table}"'
                                )
                            ).all()
                            == []
                        )
                        assert (
                            connection.execute(
                                text(
                                    f'SELECT effect_id FROM public."{approval_denied_effects}"'
                                )
                            ).all()
                            == []
                        )
                finally:
                    expired_engine.dispose()

                destination_table = policy_denied_table
                destination_effects = policy_denied_effects
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_DESTINATION_TABLE", destination_table
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_EFFECT_TABLE", destination_effects
                )
                missing_policy = managed.submit_run(
                    ctx,
                    "phase058-process-pipeline",
                    idempotency_key=f"phase058-policy-provider-missing-{scope}",
                    request=RunRequest(materialization=MaterializationPolicy.DURABLE),
                )
                assert (
                    backend.durable_work.get_submission(
                        ctx, missing_policy.submission_id
                    ).policy_fingerprint
                    is not None
                )
                missing_policy_dispatch = await dispatcher.tick(limit=1)
                assert len(missing_policy_dispatch) == 1
                assert (
                    missing_policy_dispatch[0]["submission_id"]
                    == missing_policy.submission_id
                )
                monkeypatch.setenv("ETLANTIC_PHASE058_DISABLE_POLICY", "1")
                try:
                    await ProcessWorker(
                        work_pool_name=spec.work_pool_name,
                        name=f"phase058-policy-missing-worker-{scope[:8]}",
                    ).start(run_once=True, printer=lambda *_args, **_kwargs: None)
                finally:
                    monkeypatch.delenv(
                        "ETLANTIC_PHASE058_DISABLE_POLICY", raising=False
                    )
                missing_policy_record = backend.durable_work.get_submission(
                    ctx, missing_policy.submission_id
                )
                assert missing_policy_record.status == "failed"
                missing_policy_attempts = backend.durable_work.list_attempts(
                    ctx, missing_policy.submission_id
                )
                assert len(missing_policy_attempts) == 1
                assert missing_policy_attempts[0].status == "failed"
                with pytest.raises(ControlPlaneError) as no_missing_policy_effect:
                    backend.durable_work.get_effect(
                        ctx, f"{missing_policy.submission_id}:execution"
                    )
                assert no_missing_policy_effect.value.status == 404
                missing_policy_engine = create_engine(url, pool_pre_ping=True)
                try:
                    with missing_policy_engine.connect() as connection:
                        denied_rows = connection.execute(
                            text(
                                f'SELECT id, payload FROM public."{policy_denied_table}"'
                            )
                        ).all()
                        denied_effects = connection.execute(
                            text(
                                f'SELECT effect_id FROM public."{policy_denied_effects}"'
                            )
                        ).all()
                    assert denied_rows == []
                    assert denied_effects == []
                finally:
                    missing_policy_engine.dispose()

                destination_table = postgres_postgres_table
                destination_effects = postgres_postgres_effects
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_DESTINATION_TABLE", destination_table
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_EFFECT_TABLE", destination_effects
                )

                source_kind = "csv"
                destination_table = nontransactional_table
                destination_effects = nontransactional_effects
                for key, value in {
                    "ETLANTIC_PHASE058_SOURCE_KIND": source_kind,
                    "ETLANTIC_PHASE058_DESTINATION_TABLE": destination_table,
                    "ETLANTIC_PHASE058_EFFECT_TABLE": destination_effects,
                }.items():
                    monkeypatch.setenv(key, value)
                partial_effect_submission = managed.submit_run(
                    ctx,
                    "phase058-process-pipeline",
                    idempotency_key=f"phase058-nontransactional-partial-effect-{scope}",
                    request=RunRequest(materialization=MaterializationPolicy.DURABLE),
                )
                partial_effect_dispatch = await dispatcher.tick(limit=1)
                assert len(partial_effect_dispatch) == 1
                assert (
                    partial_effect_dispatch[0]["submission_id"]
                    == partial_effect_submission.submission_id
                )
                partial_effect_flow_run_id = str(
                    partial_effect_dispatch[0]["prefect_flow_run_id"]
                )
                partial_effect_marker = (
                    tmp_path / f"phase058-nontransactional-partial-{scope}"
                )
                partial_effect_release = (
                    tmp_path / f"phase058-release-nontransactional-{scope}"
                )
                for key, value in {
                    "ETLANTIC_PHASE058_PARTIAL_EFFECT_TABLE": nontransactional_table,
                    "ETLANTIC_PHASE058_PARTIAL_EFFECT_MARKER": str(
                        partial_effect_marker
                    ),
                    "ETLANTIC_PHASE058_PARTIAL_EFFECT_RELEASE": str(
                        partial_effect_release
                    ),
                }.items():
                    monkeypatch.setenv(key, value)
                partial_effect_worker_task = asyncio.create_task(
                    ProcessWorker(
                        work_pool_name=spec.work_pool_name,
                        name=f"phase058-nontx-worker-{scope[:8]}",
                    ).start(run_once=True, printer=lambda *_args, **_kwargs: None)
                )
                partial_effect_worker_error: BaseException | None = None
                try:
                    await asyncio.wait_for(
                        asyncio.to_thread(_wait_for_marker, partial_effect_marker),
                        timeout=65,
                    )
                    partial_effect_attempts = backend.durable_work.list_attempts(
                        ctx, partial_effect_submission.submission_id
                    )
                    assert len(partial_effect_attempts) == 1
                    assert partial_effect_attempts[0].status == "running"
                    with pytest.raises(ControlPlaneError) as no_partial_effect_receipt:
                        backend.durable_work.get_effect(
                            ctx,
                            f"{partial_effect_submission.submission_id}:execution",
                        )
                    assert no_partial_effect_receipt.value.status == 404
                    partial_effect_engine = create_engine(url, pool_pre_ping=True)
                    try:
                        with partial_effect_engine.connect() as connection:
                            partial_effect_rows = connection.execute(
                                text(
                                    f'SELECT id, payload FROM public."{nontransactional_table}"'
                                )
                            ).all()
                            partial_effect_ledger = connection.execute(
                                text(
                                    f'SELECT effect_id FROM public."{nontransactional_effects}"'
                                )
                            ).all()
                        assert partial_effect_rows == [(row_id, payload)]
                        assert partial_effect_ledger == []
                    finally:
                        partial_effect_engine.dispose()
                finally:
                    partial_effect_release.touch(exist_ok=True)
                    try:
                        await asyncio.wait_for(partial_effect_worker_task, timeout=60)
                    except BaseException as exc:
                        partial_effect_worker_error = exc
                    for variable in (
                        "ETLANTIC_PHASE058_PARTIAL_EFFECT_TABLE",
                        "ETLANTIC_PHASE058_PARTIAL_EFFECT_MARKER",
                        "ETLANTIC_PHASE058_PARTIAL_EFFECT_RELEASE",
                    ):
                        monkeypatch.delenv(variable, raising=False)
                assert partial_effect_worker_error is None, repr(
                    partial_effect_worker_error
                )
                async with get_client() as client:
                    partial_effect_remote = await client.read_flow_run(
                        UUID(partial_effect_flow_run_id)
                    )
                assert partial_effect_remote.state is not None
                assert getattr(
                    partial_effect_remote.state.type,
                    "value",
                    partial_effect_remote.state.type,
                ) in {"CRASHED", "FAILED"}
                partial_effect_attempt = backend.durable_work.list_attempts(
                    ctx, partial_effect_submission.submission_id
                )[0]
                backend.durable_work.release_lease(
                    ctx,
                    partial_effect_submission.submission_id,
                    owner_id=partial_effect_attempt.owner_id,
                    fencing_token=partial_effect_attempt.fencing_token,
                )
                partial_effect_recovery_backend, partial_effect_recovery_ctx = (
                    worker_backend_fixture.build_backend()
                )
                try:
                    partial_effect_recovery = (
                        partial_effect_recovery_backend.execute_submission(
                            partial_effect_recovery_ctx,
                            partial_effect_submission.submission_id,
                            owner_id=f"phase058-nontx-recovery-{scope}",
                            execution_route=binding.execution_route,
                        )
                    )
                    assert partial_effect_recovery["status"] == "failed"
                    assert partial_effect_recovery["executed"] is True
                    partial_effect_attempts = (
                        partial_effect_recovery_backend.durable_work.list_attempts(
                            partial_effect_recovery_ctx,
                            partial_effect_submission.submission_id,
                        )
                    )
                    assert [item.status for item in partial_effect_attempts] == [
                        "lost",
                        "lost",
                    ]
                    assert (
                        partial_effect_recovery_backend.durable_work.get_effect(
                            partial_effect_recovery_ctx,
                            f"{partial_effect_submission.submission_id}:execution",
                        ).status
                        == "unknown"
                    )
                finally:
                    partial_effect_recovery_backend.close()
                    worker_backend_fixture.restore_test_execution_host_factory()
                partial_effect_verify_engine = create_engine(url, pool_pre_ping=True)
                try:
                    with partial_effect_verify_engine.connect() as connection:
                        retained_partial_rows = connection.execute(
                            text(
                                f'SELECT id, payload FROM public."{nontransactional_table}"'
                            )
                        ).all()
                        still_empty_effect_ledger = connection.execute(
                            text(
                                f'SELECT effect_id FROM public."{nontransactional_effects}"'
                            )
                        ).all()
                    assert retained_partial_rows == [(row_id, payload)]
                    assert still_empty_effect_ledger == []
                finally:
                    partial_effect_verify_engine.dispose()

                source_kind = "postgresql"
                destination_table = postgres_postgres_table
                destination_effects = postgres_postgres_effects
                for key, value in {
                    "ETLANTIC_PHASE058_SOURCE_KIND": source_kind,
                    "ETLANTIC_PHASE058_DESTINATION_TABLE": destination_table,
                    "ETLANTIC_PHASE058_EFFECT_TABLE": destination_effects,
                }.items():
                    monkeypatch.setenv(key, value)

                uncertain = managed.submit_run(
                    ctx,
                    "phase058-process-pipeline",
                    idempotency_key=f"phase058-crash-after-connector-commit-{scope}",
                    request=RunRequest(materialization=MaterializationPolicy.DURABLE),
                )
                uncertain_dispatch = await dispatcher.tick(limit=1)
                assert len(uncertain_dispatch) == 1
                assert uncertain_dispatch[0]["submission_id"] == uncertain.submission_id
                uncertain_flow_run_id = str(
                    uncertain_dispatch[0]["prefect_flow_run_id"]
                )
                effects_before_uncertain_commit = effect_ledger_count()
                commit_marker = tmp_path / f"phase058-connector-committed-{scope}"
                commit_release = tmp_path / f"phase058-release-connector-{scope}"
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_CRASH_AFTER_CONNECTOR_COMMIT", "1"
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_CRASH_AFTER_CONNECTOR_COMMIT_MARKER",
                    str(commit_marker),
                )
                monkeypatch.setenv(
                    "ETLANTIC_PHASE058_CRASH_AFTER_CONNECTOR_COMMIT_RELEASE",
                    str(commit_release),
                )
                commit_worker_task = asyncio.create_task(
                    ProcessWorker(
                        work_pool_name=spec.work_pool_name,
                        name=f"phase058-uncertain-worker-{scope[:8]}",
                    ).start(run_once=True, printer=lambda *_args, **_kwargs: None)
                )
                commit_worker_error: BaseException | None = None
                try:
                    await asyncio.wait_for(
                        asyncio.to_thread(_wait_for_marker, commit_marker), timeout=65
                    )
                    commit_attempts = backend.durable_work.list_attempts(
                        ctx, uncertain.submission_id
                    )
                    assert len(commit_attempts) == 1
                    assert commit_attempts[0].status == "running"
                    with pytest.raises(ControlPlaneError) as no_commit_receipt:
                        backend.durable_work.get_effect(
                            ctx, f"{uncertain.submission_id}:execution"
                        )
                    assert no_commit_receipt.value.status == 404
                    assert effect_ledger_count() == effects_before_uncertain_commit + 1
                finally:
                    commit_release.touch(exist_ok=True)
                    try:
                        await asyncio.wait_for(commit_worker_task, timeout=60)
                    except BaseException as exc:
                        commit_worker_error = exc
                    for variable in (
                        "ETLANTIC_PHASE058_CRASH_AFTER_CONNECTOR_COMMIT",
                        "ETLANTIC_PHASE058_CRASH_AFTER_CONNECTOR_COMMIT_MARKER",
                        "ETLANTIC_PHASE058_CRASH_AFTER_CONNECTOR_COMMIT_RELEASE",
                    ):
                        monkeypatch.delenv(variable, raising=False)
                assert commit_worker_error is None, repr(commit_worker_error)
                async with get_client() as client:
                    uncertain_remote = await client.read_flow_run(
                        UUID(uncertain_flow_run_id)
                    )
                assert uncertain_remote.state is not None
                assert getattr(
                    uncertain_remote.state.type, "value", uncertain_remote.state.type
                ) in {"CRASHED", "FAILED"}
                uncertain_attempt = backend.durable_work.list_attempts(
                    ctx, uncertain.submission_id
                )[0]
                backend.durable_work.release_lease(
                    ctx,
                    uncertain.submission_id,
                    owner_id=uncertain_attempt.owner_id,
                    fencing_token=uncertain_attempt.fencing_token,
                )
                uncertain_recovery_backend, uncertain_recovery_ctx = (
                    worker_backend_fixture.build_backend()
                )
                try:
                    unresolved = uncertain_recovery_backend.execute_submission(
                        uncertain_recovery_ctx,
                        uncertain.submission_id,
                        owner_id=f"phase058-uncertain-recovery-{scope}",
                        execution_route=binding.execution_route,
                    )
                    assert unresolved["status"] == "failed"
                    assert unresolved["executed"] is True
                    uncertain_attempts = (
                        uncertain_recovery_backend.durable_work.list_attempts(
                            uncertain_recovery_ctx, uncertain.submission_id
                        )
                    )
                    assert [item.status for item in uncertain_attempts] == [
                        "lost",
                        "lost",
                    ]
                    assert (
                        uncertain_recovery_backend.durable_work.get_effect(
                            uncertain_recovery_ctx,
                            f"{uncertain.submission_id}:execution",
                        ).status
                        == "unknown"
                    )
                finally:
                    uncertain_recovery_backend.close()
                    worker_backend_fixture.restore_test_execution_host_factory()
                assert effect_ledger_count() == effects_before_uncertain_commit + 1

                with temporary_settings({PREFECT_API_URL: prefect_api_url}):
                    asyncio.run(scenario())
    finally:
        if backend is not None:
            backend.close()
        cleanup_engine = create_engine(url, pool_pre_ping=True)
        try:
            with cleanup_engine.begin() as connection:
                connection.execute(
                    text(
                        "DELETE FROM cp_input_resource_leases "
                        "WHERE tenant_id = :tenant AND workspace_id = :workspace"
                    ),
                    {
                        "tenant": ctx.tenant.tenant_id,
                        "workspace": ctx.workspace.workspace_id,
                    },
                )
                connection.execute(
                    text(
                        "DELETE FROM cp_input_uploads "
                        "WHERE tenant_id = :tenant AND workspace_id = :workspace"
                    ),
                    {
                        "tenant": ctx.tenant.tenant_id,
                        "workspace": ctx.workspace.workspace_id,
                    },
                )
                for table in (
                    "cp_event_idempotency",
                    "cp_events",
                    "cp_submissions",
                    "cp_definitions",
                    "cp_run_reports",
                    "cp_registry_aliases",
                    "cp_registry_promotions",
                    "cp_registry_revisions",
                    "cp_registry_environments",
                    "cp_registry_logical",
                    "cp_registry_workspaces",
                ):
                    connection.execute(
                        text(
                            f"DELETE FROM {table} "
                            "WHERE tenant_id = :tenant AND workspace_id = :workspace"
                        ),
                        {
                            "tenant": ctx.tenant.tenant_id,
                            "workspace": ctx.workspace.workspace_id,
                        },
                    )
                connection.execute(
                    text("DELETE FROM cp_registry_tenants WHERE tenant_id = :tenant"),
                    {"tenant": ctx.tenant.tenant_id},
                )
                for table in (
                    "cp_durable_submission_entity",
                    "cp_durable_outbox_entity",
                    "cp_durable_snapshot",
                    "cp_cp4_governance_snapshot",
                ):
                    connection.execute(
                        text(f"DELETE FROM {table} WHERE store_id = :store_id"),
                        {"store_id": store_id},
                    )
                for table in (
                    csv_postgres_table,
                    csv_postgres_effects,
                    postgres_postgres_table,
                    postgres_postgres_effects,
                    scheduled_table,
                    scheduled_effects,
                    unsettled_table,
                    unsettled_effects,
                    partial_table,
                    partial_effects,
                    policy_denied_table,
                    policy_denied_effects,
                    artifact_crash_table,
                    artifact_crash_effects,
                    outage_table,
                    outage_effects,
                    mid_outage_table,
                    mid_outage_effects,
                    nontransactional_table,
                    nontransactional_effects,
                ):
                    connection.execute(text(f'DROP TABLE IF EXISTS public."{table}"'))
                quoted_role = cleanup_engine.dialect.identifier_preparer.quote(
                    rotated_credential_role
                )
                connection.exec_driver_sql(f"DROP OWNED BY {quoted_role}")
                connection.exec_driver_sql(f"DROP ROLE IF EXISTS {quoted_role}")
        finally:
            cleanup_engine.dispose()
