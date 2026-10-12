"""Isolated installed-entry-point fixture for the live Prefect worker test."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from threading import Event, Thread
from typing import Any, cast

from etlantic import Profile
from etlantic.control_plane import (
    ControlPlaneContext,
    EnvironmentRef,
    MemoryAuthorizer,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic.control_plane.managed_backend import ManagedBackend
from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.registry import BindingDescriptor, PlanningContext
from etlantic.runtime.managed_execution import ManagedExecutionAdapter
from etlantic.secrets import SecretRef
from etlantic.secrets.provider import SecretResolutionContext
from etlantic_sqlmodel.managed import SQLModelBackendConfig, create_managed_backend

_ORIGINAL_CREATE_EXECUTION_HOST = ManagedBackend.create_execution_host


class _CrashAfterConnectorCommit:
    """Exit after the provider commits but before its receipt reaches ETLantic."""

    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)

    async def commit(self, session: Any, *, context: Any) -> Any:
        receipt = await self._delegate.commit(session, context=context)
        if os.environ.get("ETLANTIC_PHASE058_CRASH_AFTER_CONNECTOR_COMMIT") != "1":
            return receipt
        marker = os.environ.get("ETLANTIC_PHASE058_CRASH_AFTER_CONNECTOR_COMMIT_MARKER")
        release = os.environ.get(
            "ETLANTIC_PHASE058_CRASH_AFTER_CONNECTOR_COMMIT_RELEASE"
        )
        if not marker or not release:
            raise RuntimeError("phase 0.58 connector crash gate is incomplete")
        Path(marker).write_text(str(os.getpid()), encoding="utf-8")
        deadline = time.monotonic() + 60
        while not Path(release).exists():
            if time.monotonic() >= deadline:
                raise TimeoutError("phase 0.58 connector crash gate was not released")
            await asyncio.sleep(0.02)
        os._exit(74)


class _CrashAfterPrepare:
    """Exit while PostgreSQL still holds an uncommitted sink transaction."""

    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)

    async def prepare(self, session: Any, *, context: Any) -> None:
        await self._delegate.prepare(session, context=context)
        if os.environ.get("ETLANTIC_PHASE058_CRASH_AFTER_PREPARE") != "1":
            return
        marker = os.environ.get("ETLANTIC_PHASE058_CRASH_AFTER_PREPARE_MARKER")
        release = os.environ.get("ETLANTIC_PHASE058_CRASH_AFTER_PREPARE_RELEASE")
        if not marker or not release:
            raise RuntimeError(
                "phase 0.58 prepared-transaction crash gate is incomplete"
            )
        Path(marker).write_text(str(os.getpid()), encoding="utf-8")
        deadline = time.monotonic() + 60
        while not Path(release).exists():
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    "phase 0.58 prepared-transaction gate was not released"
                )
            await asyncio.sleep(0.02)
        os._exit(77)


class _HoldBeforeConnectorCommit:
    """Pause a prepared PostgreSQL transaction at its commit boundary."""

    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)

    async def commit(self, session: Any, *, context: Any) -> Any:
        if os.environ.get("ETLANTIC_PHASE058_HOLD_BEFORE_CONNECTOR_COMMIT") == "1":
            marker = os.environ.get("ETLANTIC_PHASE058_COMMIT_HOLD_MARKER")
            release = os.environ.get("ETLANTIC_PHASE058_COMMIT_HOLD_RELEASE")
            if not marker or not release:
                raise RuntimeError("phase 0.58 commit hold gate is incomplete")
            Path(marker).write_text(str(os.getpid()), encoding="utf-8")
            deadline = time.monotonic() + 60
            while not Path(release).exists():
                if time.monotonic() >= deadline:
                    raise TimeoutError("phase 0.58 commit hold gate expired")
                await asyncio.sleep(0.02)
        return await self._delegate.commit(session, context=context)


class _HoldDuringSourceStaging:
    """Pause after a source batch is staged and observe managed cancellation."""

    def __init__(self, delegate: Any, runtime: PipelineRuntime) -> None:
        self._delegate = delegate
        self._runtime = runtime

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)

    async def read_batches(self, **kwargs: Any) -> Any:
        held = False
        async for batch in self._delegate.read_batches(**kwargs):
            if (
                not held
                and os.environ.get("ETLANTIC_PHASE058_HOLD_DURING_SOURCE_STAGING")
                == "1"
            ):
                marker = os.environ.get("ETLANTIC_PHASE058_SOURCE_STAGING_MARKER")
                release = os.environ.get("ETLANTIC_PHASE058_SOURCE_STAGING_RELEASE")
                cancel_observed = os.environ.get(
                    "ETLANTIC_PHASE058_SOURCE_STAGING_CANCEL_OBSERVED"
                )
                if not marker or not release or not cancel_observed:
                    raise RuntimeError(
                        "phase 0.58 source-staging hold gate is incomplete"
                    )
                held = True
                Path(marker).write_text(str(os.getpid()), encoding="utf-8")
                deadline = time.monotonic() + 60
                cancel_event = self._runtime.external_cancel_event
                while not Path(release).exists():
                    if (
                        cancel_event is not None
                        and cancel_event.is_set()
                        and not Path(cancel_observed).exists()
                    ):
                        Path(cancel_observed).write_text("observed", encoding="utf-8")
                    if time.monotonic() >= deadline:
                        raise TimeoutError(
                            "phase 0.58 source-staging hold gate expired"
                        )
                    await asyncio.sleep(0.02)
            yield batch


class _CrashAfterNonTransactionalPartialWrite:
    """Commit one row outside the connector transaction, then terminate."""

    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)

    async def write_batch(self, session: Any, batch: Any, *, context: Any) -> None:
        await self._delegate.write_batch(session, batch, context=context)
        table = os.environ.get("ETLANTIC_PHASE058_PARTIAL_EFFECT_TABLE")
        marker = os.environ.get("ETLANTIC_PHASE058_PARTIAL_EFFECT_MARKER")
        release = os.environ.get("ETLANTIC_PHASE058_PARTIAL_EFFECT_RELEASE")
        if not table or not marker or not release:
            return
        if not table.replace("_", "").isalnum():
            raise ValueError("phase 0.58 partial-effect table is invalid")
        from sqlalchemy import create_engine, text

        values: list[Any] = (
            list(cast(Sequence[Any], batch))
            if isinstance(batch, (list, tuple))
            else [batch]
        )
        if not values or not isinstance(values[0], Mapping):
            raise TypeError("phase 0.58 partial-effect fixture expected one record")
        row = cast(Mapping[str, Any], values[0])
        engine = create_engine(
            os.environ["ETLANTIC_PHASE058_POSTGRES_URL"],
            pool_pre_ping=True,
            hide_parameters=True,
        )
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        f'INSERT INTO public."{table}" (id, payload) '
                        "VALUES (:id, :payload)"
                    ),
                    {"id": row["id"], "payload": row["payload"]},
                )
        finally:
            engine.dispose()
        Path(marker).write_text(str(os.getpid()), encoding="utf-8")
        deadline = time.monotonic() + 60
        while not Path(release).exists():
            if time.monotonic() >= deadline:
                raise TimeoutError("phase 0.58 partial-effect gate expired")
            time.sleep(0.02)
        os._exit(94)


def _runtime() -> PipelineRuntime:
    from etlantic.connectors.local_files import LocalFilesSourceConnector
    from etlantic_sql.live_postgresql import (
        LivePostgresSinkConnector,
        LivePostgresSourceConnector,
    )

    runtime = PipelineRuntime()
    local_files: Any = LocalFilesSourceConnector()
    if os.environ.get("ETLANTIC_PHASE058_HOLD_DURING_SOURCE_STAGING") == "1":
        local_files = _HoldDuringSourceStaging(local_files, runtime)
    runtime.register_source_connector("local-files", local_files)
    runtime.register_source_connector("postgresql", LivePostgresSourceConnector())
    sink: Any = LivePostgresSinkConnector()
    if os.environ.get("ETLANTIC_PHASE058_CRASH_AFTER_DELETE") == "1":
        from sqlalchemy import event
        from sqlalchemy.engine import Engine

        target_table = os.environ["ETLANTIC_PHASE058_DESTINATION_TABLE"]
        marker = os.environ.get("ETLANTIC_PHASE058_CRASH_AFTER_DELETE_MARKER")
        release = os.environ.get("ETLANTIC_PHASE058_CRASH_AFTER_DELETE_RELEASE")
        if not marker or not release:
            raise RuntimeError("phase 0.58 mid-write crash gate is incomplete")

        def crash_after_delete(
            _connection: Any,
            _cursor: Any,
            statement: str,
            _parameters: Any,
            _context: Any,
            _executemany: bool,
        ) -> None:
            if not statement.lstrip().lower().startswith("delete from"):
                return
            if target_table.lower() not in statement.lower():
                return
            Path(marker).write_text(str(os.getpid()), encoding="utf-8")
            deadline = time.monotonic() + 60
            while not Path(release).exists():
                if time.monotonic() >= deadline:
                    raise TimeoutError("phase 0.58 mid-write gate was not released")
                time.sleep(0.02)
            os._exit(78)

        event.listen(Engine, "after_cursor_execute", crash_after_delete)
    if os.environ.get("ETLANTIC_PHASE058_CRASH_AFTER_CONNECTOR_COMMIT") == "1":
        sink = _CrashAfterConnectorCommit(sink)
    if os.environ.get("ETLANTIC_PHASE058_CRASH_AFTER_PREPARE") == "1":
        sink = _CrashAfterPrepare(sink)
    if os.environ.get("ETLANTIC_PHASE058_HOLD_BEFORE_CONNECTOR_COMMIT") == "1":
        sink = _HoldBeforeConnectorCommit(sink)
    if os.environ.get("ETLANTIC_PHASE058_PARTIAL_EFFECT_TABLE"):
        sink = _CrashAfterNonTransactionalPartialWrite(sink)
    runtime.register_sink_connector("postgresql", sink)
    return runtime


class _WorkerSecretAuthorizer:
    async def authorize_late_binding(
        self, reference: SecretRef, context: SecretResolutionContext
    ) -> bool:
        return (
            context.trusted_scope is not None
            and reference.name == "ETLANTIC_PHASE058_POSTGRES_URL"
        )


class _CrashAfterAdapter:
    """Hold a worker after the sink and durable report, before host finalization."""

    def __init__(self, delegate: ManagedExecutionAdapter) -> None:
        self._delegate = delegate

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        report = self._delegate(*args, **kwargs)
        target_submission = os.environ.get(
            "ETLANTIC_PHASE058_CRASH_AFTER_ADAPTER_SUBMISSION"
        )
        submission = kwargs.get("submission")
        submission_id = getattr(submission, "submission_id", None)
        marker = os.environ.get("ETLANTIC_PHASE058_CRASH_AFTER_ADAPTER_MARKER")
        release = os.environ.get("ETLANTIC_PHASE058_CRASH_AFTER_ADAPTER_RELEASE")
        if (
            isinstance(target_submission, str)
            and target_submission == submission_id
            and isinstance(marker, str)
            and marker
            and isinstance(release, str)
            and release
        ):
            Path(marker).write_text(str(os.getpid()), encoding="utf-8")
            deadline = time.monotonic() + 60
            while not Path(release).exists():
                if time.monotonic() >= deadline:
                    raise TimeoutError("phase 0.58 crash gate was not released")
                time.sleep(0.02)
            os._exit(73)
        return report


class _HoldAfterAdapter:
    """Pause after ETL effects/report publication but before host finalization."""

    def __init__(self, delegate: ManagedExecutionAdapter) -> None:
        self._delegate = delegate

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        report = self._delegate(*args, **kwargs)
        target_submission = os.environ.get(
            "ETLANTIC_PHASE058_HOLD_AFTER_ADAPTER_SUBMISSION"
        )
        submission = kwargs.get("submission")
        submission_id = getattr(submission, "submission_id", None)
        marker = os.environ.get("ETLANTIC_PHASE058_HOLD_AFTER_ADAPTER_MARKER")
        release = os.environ.get("ETLANTIC_PHASE058_HOLD_AFTER_ADAPTER_RELEASE")
        cancel_observed = os.environ.get(
            "ETLANTIC_PHASE058_HOLD_AFTER_ADAPTER_CANCEL_OBSERVED"
        )
        if (
            isinstance(target_submission, str)
            and target_submission == submission_id
            and isinstance(marker, str)
            and marker
            and isinstance(release, str)
            and release
        ):
            Path(marker).write_text(str(os.getpid()), encoding="utf-8")
            deadline = time.monotonic() + 60
            while not Path(release).exists():
                cancel_event = kwargs.get("cancel_event")
                is_set = getattr(cancel_event, "is_set", None)
                if (
                    isinstance(cancel_observed, str)
                    and cancel_observed
                    and callable(is_set)
                    and is_set()
                ):
                    Path(cancel_observed).write_text("observed", encoding="utf-8")
                if time.monotonic() >= deadline:
                    raise TimeoutError("phase 0.58 post-effect hold gate expired")
                time.sleep(0.02)
        return report


class _HoldAndFailFirstReportPut:
    """Pause and fail one report-store write after the connector has committed."""

    def __init__(
        self,
        delegate: Any,
        *,
        run_id: str,
        marker: str,
        release: str,
    ) -> None:
        self._delegate = delegate
        self._run_id = run_id
        self._marker = Path(marker)
        self._release = Path(release)
        self._failed = False

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)

    def put(self, report: Any) -> None:
        status = getattr(report.status, "value", report.status)
        if (
            report.run_id == self._run_id
            and status in {"succeeded", "failed", "cancelled"}
            and not self._failed
        ):
            self._failed = True
            self._marker.write_text(str(os.getpid()), encoding="utf-8")
            deadline = time.monotonic() + 60
            while not self._release.exists():
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        "phase 0.58 report-publication gate was not released"
                    )
                time.sleep(0.02)
            raise OSError("phase 0.58 injected report-store outage")
        self._delegate.put(report)


class _ObserveCancelDuringAdapter:
    """Observe the host's cancel event while a sink is paused before commit."""

    def __init__(self, delegate: ManagedExecutionAdapter) -> None:
        self._delegate = delegate

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        target = os.environ.get("ETLANTIC_PHASE058_OBSERVE_CANCEL_SUBMISSION")
        submission = kwargs.get("submission")
        if getattr(submission, "submission_id", None) != target:
            return self._delegate(*args, **kwargs)
        marker = os.environ.get("ETLANTIC_PHASE058_CANCEL_OBSERVED_MARKER")
        cancel_event = kwargs.get("cancel_event")
        is_set = getattr(cancel_event, "is_set", None)
        if not marker or not callable(is_set):
            raise RuntimeError("phase 0.58 cancellation observation is incomplete")

        stop = Event()

        def observe() -> None:
            while not stop.wait(0.01):
                if is_set():
                    Path(marker).write_text("observed", encoding="utf-8")
                    return

        observer = Thread(
            target=observe,
            name="phase058-cancel-observer",
            daemon=True,
        )
        observer.start()
        try:
            return self._delegate(*args, **kwargs)
        finally:
            stop.set()
            observer.join(timeout=1)


class _CrashAfterReportEventPublish:
    """Exit after a report event is durable but before host finalization."""

    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)

    def append_once(
        self,
        ctx: ControlPlaneContext,
        *,
        event_key: str,
        kind: str,
        payload: Any,
    ) -> Any:
        result = self._delegate.append_once(
            ctx, event_key=event_key, kind=kind, payload=payload
        )
        target_submission = os.environ.get(
            "ETLANTIC_PHASE058_CRASH_AFTER_REPORT_EVENT_SUBMISSION"
        )
        marker = os.environ.get("ETLANTIC_PHASE058_CRASH_AFTER_REPORT_EVENT_MARKER")
        release = os.environ.get("ETLANTIC_PHASE058_CRASH_AFTER_REPORT_EVENT_RELEASE")
        if (
            kind != "run.completed"
            or not isinstance(target_submission, str)
            or payload.get("submission_id") != target_submission
            or not isinstance(marker, str)
            or not marker
            or not isinstance(release, str)
            or not release
        ):
            return result
        Path(marker).write_text(str(os.getpid()), encoding="utf-8")
        deadline = time.monotonic() + 60
        while not Path(release).exists():
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    "phase 0.58 report-event crash gate was not released"
                )
            time.sleep(0.02)
        os._exit(79)


class _CrashBeforeAdapter:
    """Exit after durable claim but before the adapter can start effects."""

    def __init__(self, delegate: ManagedExecutionAdapter) -> None:
        self._delegate = delegate

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        target_submission = os.environ.get(
            "ETLANTIC_PHASE058_CRASH_BEFORE_ADAPTER_SUBMISSION"
        )
        submission = kwargs.get("submission")
        submission_id = getattr(submission, "submission_id", None)
        marker = os.environ.get("ETLANTIC_PHASE058_CRASH_BEFORE_ADAPTER_MARKER")
        release = os.environ.get("ETLANTIC_PHASE058_CRASH_BEFORE_ADAPTER_RELEASE")
        if (
            isinstance(target_submission, str)
            and target_submission == submission_id
            and isinstance(marker, str)
            and marker
            and isinstance(release, str)
            and release
        ):
            Path(marker).write_text(str(os.getpid()), encoding="utf-8")
            deadline = time.monotonic() + 60
            while not Path(release).exists():
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        "phase 0.58 pre-effect crash gate was not released"
                    )
                time.sleep(0.02)
            os._exit(72)
        return self._delegate(*args, **kwargs)


def _context() -> ControlPlaneContext:
    tenant_id = os.environ["ETLANTIC_PHASE058_TENANT"]
    principal_subject = os.environ["ETLANTIC_PHASE058_PRINCIPAL"]
    principal_kind = "human"
    if os.environ.get("ETLANTIC_PHASE058_DISTINCT_WORKER_IDENTITY") == "1":
        principal_subject = f"worker-{principal_subject}"
        principal_kind = "service"
    return ControlPlaneContext(
        principal=Principal(
            subject=principal_subject,
            issuer="phase058-tests",
            kind=principal_kind,
        ),
        tenant=TenantRef(tenant_id=tenant_id),
        workspace=WorkspaceRef(
            tenant_id=tenant_id,
            workspace_id=os.environ["ETLANTIC_PHASE058_WORKSPACE"],
        ),
        environment=EnvironmentRef(name="test"),
        security_domain=SecurityDomain(
            domain_id=os.environ["ETLANTIC_PHASE058_SECURITY_DOMAIN"]
        ),
    )


def build_backend() -> tuple[ManagedBackend, ControlPlaneContext]:
    """Reconstruct the trusted SQL backend from worker-process configuration."""
    approval_now = os.environ.get("ETLANTIC_PHASE058_APPROVAL_NOW")
    if approval_now:
        from etlantic.control_plane import approval_memory

        frozen_approval_now = datetime.fromisoformat(approval_now)
        if frozen_approval_now.tzinfo is None:
            raise ValueError("phase 0.58 approval clock must include a timezone")
        approval_memory._now = lambda: frozen_approval_now

    profile = Profile(
        name="phase058-process-worker",
        security_mode="development",
        plugin_allowlist={"etlantic": None},
    )
    ctx = _context()
    authorizer = MemoryAuthorizer()
    for action in (
        "definition.write",
        "definition.read",
        "definition.validate",
        "definition.plan",
        "run.execute",
        "run.submit",
        "run.read",
        "run.report",
        "run.cancel",
        "input.read",
    ):
        if (
            action == "run.submit"
            and os.environ.get("ETLANTIC_PHASE058_DENY_RUN_SUBMIT") == "1"
        ) or (
            action == "run.execute"
            and os.environ.get("ETLANTIC_PHASE058_DENY_WORKER_EXECUTE") == "1"
        ):
            continue
        authorizer.grant(ctx, action)
    policy = None
    policy_disabled = os.environ.get("ETLANTIC_PHASE058_DISABLE_POLICY") == "1"
    if not policy_disabled and (
        os.environ.get("ETLANTIC_PHASE058_ENABLE_POLICY") == "1"
        or os.environ.get("ETLANTIC_PHASE058_DENY_PRE_EXECUTION") == "1"
        or os.environ.get("ETLANTIC_PHASE058_REQUIRE_PRE_EXECUTION_APPROVAL") == "1"
    ):
        from etlantic.control_plane.policy_memory import MemoryPolicyProvider

        policy = MemoryPolicyProvider()
        if os.environ.get("ETLANTIC_PHASE058_DENY_PRE_EXECUTION") == "1":
            policy.set_rule("pre_execution", "deny")
        if os.environ.get("ETLANTIC_PHASE058_REQUIRE_PRE_EXECUTION_APPROVAL") == "1":
            policy.set_rule("pre_execution", "require_approval")

    def planning_context_factory(
        _context: ControlPlaneContext, effective_profile: Profile
    ) -> PlanningContext:
        planning = PlanningContext.create(profile=effective_profile)
        source_kind = os.environ["ETLANTIC_PHASE058_SOURCE_KIND"]
        if source_kind == "csv":
            source = BindingDescriptor(
                binding="source",
                provider="local-files",
                kind="source",
                config={
                    "input_resource": json.loads(
                        os.environ["ETLANTIC_PHASE058_INPUT_REFERENCE"]
                    )
                },
            )
        elif source_kind == "postgresql":
            source = BindingDescriptor(
                binding="source",
                provider="postgresql",
                kind="source",
                location=os.environ["ETLANTIC_PHASE058_SOURCE_TABLE"],
                secret_ref=SecretRef(
                    provider="env",
                    name="ETLANTIC_PHASE058_POSTGRES_URL",
                    key="value",
                ),
                config={"schema": "public", "mode": "snapshot"},
            )
        else:
            raise ValueError("unsupported phase 0.58 test source kind")
        planning.registry.register_binding(source)
        planning.registry.register_binding(
            BindingDescriptor(
                binding="output",
                provider="postgresql",
                kind="sink",
                location=os.environ["ETLANTIC_PHASE058_DESTINATION_TABLE"],
                secret_ref=SecretRef(
                    provider="env",
                    name="ETLANTIC_PHASE058_POSTGRES_URL",
                    key="value",
                ),
                config={
                    "schema": "public",
                    "mode": "replace",
                    "effect_table": (
                        "public." + os.environ["ETLANTIC_PHASE058_EFFECT_TABLE"]
                    ),
                },
            )
        )
        return planning

    backend = create_managed_backend(
        SQLModelBackendConfig(
            database_url=os.environ["ETLANTIC_PHASE058_DATABASE_URL"],
            store_id=os.environ["ETLANTIC_PHASE058_STORE_ID"],
            profile=profile,
            artifact_root=os.environ["ETLANTIC_PHASE058_ARTIFACT_ROOT"],
            execution_route=os.environ["ETLANTIC_PREFECT_ROUTE_ID"],
            policy=policy,
        ),
        authorizer=authorizer,
        planning_context_factory=planning_context_factory,
    )
    if policy is not None and (
        os.environ.get("ETLANTIC_PHASE058_REQUIRE_PRE_EXECUTION_APPROVAL") == "1"
    ):
        from etlantic_sqlmodel.control_plane import SQLModelApprovalStore

        backend.managed_service.approvals = SQLModelApprovalStore(
            backend.engine,
            store_id=f"{os.environ['ETLANTIC_PHASE058_STORE_ID']}:approvals",
        )
    if os.environ.get("ETLANTIC_PHASE058_CRASH_AFTER_REPORT_EVENT_SUBMISSION"):
        backend.events = _CrashAfterReportEventPublish(backend.events)

    def create_execution_host(
        self: ManagedBackend, *, owner_id: str = "managed-worker", ttl_seconds: int = 30
    ) -> Any:
        host = _ORIGINAL_CREATE_EXECUTION_HOST(
            self, owner_id=owner_id, ttl_seconds=ttl_seconds
        )
        crash_publication_run_id = os.environ.get(
            "ETLANTIC_PHASE058_CRASH_AFTER_RESULT_PUBLICATION_RUN_ID"
        )
        crash_publication_marker = os.environ.get(
            "ETLANTIC_PHASE058_CRASH_AFTER_RESULT_PUBLICATION_MARKER"
        )
        crash_publication_release = os.environ.get(
            "ETLANTIC_PHASE058_CRASH_AFTER_RESULT_PUBLICATION_RELEASE"
        )
        if (
            crash_publication_run_id
            and crash_publication_marker
            and crash_publication_release
        ):
            original_result_publisher = host._result_publisher

            def crash_after_result_publication(
                context: ControlPlaneContext,
                *,
                submission_id: str,
                attempt_id: str,
                owner_id: str,
                fencing_token: int,
            ) -> Callable[[Any], Any]:
                publish = original_result_publisher(
                    context,
                    submission_id=submission_id,
                    attempt_id=attempt_id,
                    owner_id=owner_id,
                    fencing_token=fencing_token,
                )

                def publish_then_crash(report: Any) -> Any:
                    record = publish(report)
                    if getattr(report, "run_id", None) == crash_publication_run_id:
                        Path(crash_publication_marker).write_text(
                            str(os.getpid()), encoding="utf-8"
                        )
                        deadline = time.monotonic() + 60
                        while not Path(crash_publication_release).exists():
                            if time.monotonic() >= deadline:
                                raise TimeoutError(
                                    "phase 0.58 result-publication crash gate expired"
                                )
                            time.sleep(0.02)
                        os._exit(91)
                    return record

                return publish_then_crash

            host._result_publisher = crash_after_result_publication
        artifact_crash_run_id = os.environ.get(
            "ETLANTIC_PHASE058_CRASH_DURING_ARTIFACT_WRITE_RUN_ID"
        )
        artifact_crash_marker = os.environ.get(
            "ETLANTIC_PHASE058_CRASH_DURING_ARTIFACT_WRITE_MARKER"
        )
        artifact_crash_release = os.environ.get(
            "ETLANTIC_PHASE058_CRASH_DURING_ARTIFACT_WRITE_RELEASE"
        )
        if artifact_crash_run_id and artifact_crash_marker and artifact_crash_release:
            from etlantic.io_policy import resolve_under_policy
            from etlantic.runtime import artifacts as artifact_module

            original_artifact_writer = artifact_module.write_json_safe

            def crash_during_artifact_write(
                path: str | Path,
                data: Any,
                policy: Any,
                *,
                run_id: str = "io",
            ) -> Any:
                if artifact_crash_run_id not in run_id:
                    return original_artifact_writer(path, data, policy, run_id=run_id)
                resolved, _events = resolve_under_policy(path, policy, run_id=run_id)
                resolved.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                descriptor, temporary = tempfile.mkstemp(
                    prefix=f".{resolved.name}.",
                    suffix=".tmp",
                    dir=str(resolved.parent),
                )
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(b'[{"partial":')
                    handle.flush()
                    os.fsync(handle.fileno())
                Path(artifact_crash_marker).write_text(
                    json.dumps(
                        {
                            "pid": os.getpid(),
                            "target": str(resolved),
                            "temporary": temporary,
                        },
                        sort_keys=True,
                    ),
                    encoding="utf-8",
                )
                deadline = time.monotonic() + 60
                while not Path(artifact_crash_release).exists():
                    if time.monotonic() >= deadline:
                        raise TimeoutError(
                            "phase 0.58 artifact-write crash gate expired"
                        )
                    time.sleep(0.02)
                os._exit(92)

            artifact_module.write_json_safe = crash_during_artifact_write
        trace_submission = os.environ.get("ETLANTIC_PHASE058_TRACE_ATTEMPT_SUBMISSION")
        trace_path = os.environ.get("ETLANTIC_PHASE058_TRACE_ATTEMPT_PATH")
        if trace_submission and trace_path:
            original_run_attempt = host._run_attempt

            def trace_run_attempt(ctx: Any, **kwargs: Any) -> Any:
                result = original_run_attempt(ctx, **kwargs)
                outcome, _error, _lease_lost, cancel_event = result
                submission = kwargs.get("submission")
                submission_id = getattr(submission, "submission_id", None)
                if submission_id == trace_submission:
                    outcome_status = getattr(
                        getattr(outcome, "status", None), "value", None
                    )
                    Path(trace_path).write_text(
                        json.dumps(
                            {
                                "cancel_event_set": cancel_event.is_set(),
                                "outcome_status": outcome_status,
                            },
                            sort_keys=True,
                        ),
                        encoding="utf-8",
                    )
                return result

            host._run_attempt = trace_run_attempt
        adapter = cast(ManagedExecutionAdapter, host.runner)
        adapter.runtime_factory = _runtime
        adapter.secret_alias_authorizer = _WorkerSecretAuthorizer()
        target_run_id = os.environ.get("ETLANTIC_PHASE058_REPORT_STORE_FAULT_RUN_ID")
        marker = os.environ.get("ETLANTIC_PHASE058_REPORT_STORE_FAULT_MARKER")
        release = os.environ.get("ETLANTIC_PHASE058_REPORT_STORE_FAULT_RELEASE")
        if target_run_id and marker and release:
            from etlantic.runtime.managed_execution import managed_report_store

            base_factory: Callable[[ControlPlaneContext], Any] = (
                adapter.report_store_factory
                or (
                    lambda context: managed_report_store(
                        context, report_root=adapter.report_root
                    )
                )
            )

            def faulted_report_store_factory(context: ControlPlaneContext) -> Any:
                return _HoldAndFailFirstReportPut(
                    base_factory(context),
                    run_id=target_run_id,
                    marker=marker,
                    release=release,
                )

            adapter.report_store_factory = faulted_report_store_factory
        if os.environ.get("ETLANTIC_PHASE058_OBSERVE_CANCEL_SUBMISSION"):
            host.runner = _ObserveCancelDuringAdapter(adapter)
        if os.environ.get("ETLANTIC_PHASE058_HOLD_AFTER_ADAPTER_SUBMISSION"):
            host.runner = _HoldAfterAdapter(adapter)
        elif os.environ.get("ETLANTIC_PHASE058_CRASH_AFTER_ADAPTER_SUBMISSION"):
            host.runner = _CrashAfterAdapter(adapter)
        if os.environ.get("ETLANTIC_PHASE058_CRASH_BEFORE_ADAPTER_SUBMISSION"):
            host.runner = _CrashBeforeAdapter(adapter)
        return host

    # The fixture's provider assembly is worker-side configuration, just as a
    # deployed application would install its connector factory with the backend.
    ManagedBackend.create_execution_host = create_execution_host  # type: ignore[method-assign]
    return backend, ctx


def restore_test_execution_host_factory() -> None:
    """Restore the process-wide test hook after parent-process recovery tests."""
    type.__setattr__(
        ManagedBackend, "create_execution_host", _ORIGINAL_CREATE_EXECUTION_HOST
    )
