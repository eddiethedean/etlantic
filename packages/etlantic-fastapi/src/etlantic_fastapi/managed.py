"""Standard SQLModel-backed managed application constructors."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from etlantic.control_plane.action_jobs import (
    MAX_PREVIEW_RESULT_TTL_SECONDS,
    MIN_PREVIEW_RESULT_TTL_SECONDS,
)
from etlantic.control_plane.event_retention import (
    DEFAULT_EVENT_IDEMPOTENCY_RETENTION_SECONDS,
)
from etlantic.control_plane.models import ControlPlaneContext
from etlantic.control_plane.protocols import Authorizer, IdempotentEventStore
from etlantic.profile import Profile
from etlantic.registry import PlanningContext
from etlantic.reports.retention import ArtifactRetentionResult
from etlantic_fastapi.api import ETLanticAPI, create_app
from etlantic_fastapi.auth import (
    ContextFactory,
    PrincipalDependency,
    principal_from_header,
)
from fastapi import FastAPI

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

    from etlantic.runtime.action_execution_host import ActionExecutionHost

ActionHandler = Callable[
    [ControlPlaneContext, Mapping[str, Any]], Awaitable[Mapping[str, Any]]
]


def _empty_engine_options() -> dict[str, Any]:
    return {}


def _empty_action_handlers() -> dict[str, ActionHandler]:
    return {}


def _is_nonempty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


_CORE_CONFIGURATION_FIELDS = (
    "report_store_factory",
    "report_store_scope_key",
    "input_resources",
    "artifact_root",
    "action_handlers",
    "action_job_lease_seconds",
    "preview_result_ttl_seconds",
    "run_artifact_retention_seconds",
    "run_artifact_cleanup_batch_size",
    "execution_profile",
)


def _configuration_snapshot(backend: ManagedBackend) -> dict[str, Any]:
    values = {name: getattr(backend, name) for name in _CORE_CONFIGURATION_FIELDS}
    values["action_handlers"] = dict(backend.action_handlers)
    return values


def _configuration_value_changed(name: str, current: Any, prior: Any) -> bool:
    if name == "action_handlers":
        return dict(current) != dict(prior)
    if type(current) in (str, int, float, bool, type(None)):
        return type(current) is not type(prior) or current != prior
    if name == "execution_profile":
        return current != prior
    return current is not prior


@dataclass(frozen=True, slots=True)
class ManagedBackendConfig:
    """Configuration for the standard relational managed backend.

    The URL and engine options are excluded from repr because they may contain
    authentication material. Schema migrations are an explicit deployment
    step; constructors reject missing or behind-version schemas.
    """

    database_url: str = field(repr=False)
    store_id: str = "default"
    profile: Any = field(default="development", repr=False)
    engine_options: Mapping[str, Any] = field(
        default_factory=_empty_engine_options, repr=False
    )
    title: str = "ETLantic Control Plane"
    version: str | None = None
    event_retention_max_events_per_scope: int = 100_000
    max_input_upload_bytes: int = 64 * 1024 * 1024
    input_upload_ttl_seconds: int = 60 * 60
    input_resource_retention_seconds: int = 90 * 24 * 60 * 60
    action_job_max_deadline_seconds: int = 300
    action_job_lease_seconds: int = 330
    preview_result_ttl_seconds: int = 60 * 60
    run_artifact_retention_seconds: int | None = None
    run_artifact_cleanup_batch_size: int = 100
    action_handlers: Mapping[str, ActionHandler] = field(
        default_factory=_empty_action_handlers, repr=False
    )
    artifact_root: str | None = field(default=None, repr=False)
    event_idempotency_retention_seconds: int = (
        DEFAULT_EVENT_IDEMPOTENCY_RETENTION_SECONDS
    )
    policy: Any = field(default=None, repr=False)
    approvals: Any = field(default=None, repr=False)
    quotas: Any = field(default=None, repr=False)
    audit: Any = field(default=None, repr=False)
    attestations: Any = field(default=None, repr=False)
    require_attestations: bool = False
    schedule_parameter_resolver: Any = field(default=None, repr=False)
    schedule_clock: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not _is_nonempty_text(self.database_url):
            raise ValueError("database_url must be a non-empty SQLAlchemy URL")
        if not _is_nonempty_text(self.store_id):
            raise ValueError("store_id must be non-empty")
        if (
            type(self.event_retention_max_events_per_scope) is not int
            or self.event_retention_max_events_per_scope < 1
        ):
            raise ValueError(
                "event_retention_max_events_per_scope must be a positive integer"
            )
        if (
            type(self.event_idempotency_retention_seconds) is not int
            or self.event_idempotency_retention_seconds < 1
        ):
            raise ValueError(
                "event_idempotency_retention_seconds must be a positive integer"
            )
        for name, value in (
            ("max_input_upload_bytes", self.max_input_upload_bytes),
            ("input_upload_ttl_seconds", self.input_upload_ttl_seconds),
            ("input_resource_retention_seconds", self.input_resource_retention_seconds),
        ):
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if (
            type(self.action_job_max_deadline_seconds) is not int
            or not 1 <= self.action_job_max_deadline_seconds <= 300
        ):
            raise ValueError(
                "action_job_max_deadline_seconds must be between 1 and 300"
            )
        if (
            type(self.action_job_lease_seconds) is not int
            or self.action_job_lease_seconds <= self.action_job_max_deadline_seconds
        ):
            raise ValueError(
                "action_job_lease_seconds must exceed the maximum action deadline"
            )
        if (
            type(self.preview_result_ttl_seconds) is not int
            or not MIN_PREVIEW_RESULT_TTL_SECONDS
            <= self.preview_result_ttl_seconds
            <= MAX_PREVIEW_RESULT_TTL_SECONDS
        ):
            raise ValueError(
                "preview_result_ttl_seconds must be between "
                f"{MIN_PREVIEW_RESULT_TTL_SECONDS} and "
                f"{MAX_PREVIEW_RESULT_TTL_SECONDS}"
            )
        if self.run_artifact_retention_seconds is not None and (
            type(self.run_artifact_retention_seconds) is not int
            or self.run_artifact_retention_seconds < 1
        ):
            raise ValueError(
                "run_artifact_retention_seconds must be a positive integer or None"
            )
        if (
            type(self.run_artifact_cleanup_batch_size) is not int
            or not 1 <= self.run_artifact_cleanup_batch_size <= 1000
        ):
            raise ValueError(
                "run_artifact_cleanup_batch_size must be between 1 and 1000"
            )
        supported_actions = {
            "connector.test",
            "connector.catalog",
            "connector.schema.inspect",
            "connector.preflight",
            "connector.preview",
            "connector.provision",
            "connector.provision.cleanup",
        }
        unsupported_actions = {
            action
            for action in cast(Mapping[object, ActionHandler], self.action_handlers)
            if not isinstance(action, str)
            or (
                action not in supported_actions
                and not (
                    action.startswith("connector.catalog.")
                    and action.removeprefix("connector.catalog.")
                    .replace("-", "")
                    .replace("_", "")
                    .isalnum()
                )
            )
        }
        if unsupported_actions:
            raise ValueError(
                "action_handlers contains unsupported action(s): "
                + ", ".join(sorted(map(str, unsupported_actions)))
            )
        for action, handler in self.action_handlers.items():
            if not callable(handler) or not (
                inspect.iscoroutinefunction(handler)
                or inspect.iscoroutinefunction(type(handler).__call__)
            ):
                raise TypeError(f"action handler {action!r} must be asynchronous")


@dataclass(slots=True)
class ManagedBackend:
    """Headless services and their explicitly owned shared SQL engine."""

    api: ETLanticAPI = field(repr=False)
    engine: Engine = field(repr=False)
    report_store_factory: Callable[[ControlPlaneContext], Any] = field(repr=False)
    input_resources: Any = field(repr=False)
    action_handlers: Mapping[str, ActionHandler] = field(
        default_factory=_empty_action_handlers, repr=False
    )
    action_job_lease_seconds: int = 330
    preview_result_ttl_seconds: int = 60 * 60
    run_artifact_retention_seconds: int | None = None
    run_artifact_cleanup_batch_size: int = 100
    execution_profile: Profile | None = field(default=None, repr=False)
    artifact_root: str | None = field(default=None, repr=False)
    report_store_scope_key: Callable[[ControlPlaneContext], object] | None = field(
        default=None, repr=False
    )
    _closed: bool = field(default=False, init=False, repr=False)
    core_backend: Any = field(default=None, repr=False)
    _core_configuration_snapshot: dict[str, Any] | None = field(
        default=None, init=False, repr=False
    )

    def __post_init__(self) -> None:
        if self.core_backend is not None:
            self._core_configuration_snapshot = _configuration_snapshot(self)

    @property
    def schedule_service(self) -> Any:
        """Expose the same command service used by schedule HTTP routes."""
        if self.core_backend is not None:
            return self.core_backend.schedule_service
        return self.api.get_schedule_service()

    def close(self) -> None:
        """Dispose idle database connections without deleting accepted work."""
        if self._closed:
            return
        if self.core_backend is not None:
            self.core_backend.close()
        else:
            self.engine.dispose()
        self._closed = True

    def _sync_core_configuration(self) -> None:
        """Apply only facade changes and refresh from the shared core handle."""
        if self.core_backend is None:
            return
        snapshot = self._core_configuration_snapshot
        if snapshot is None:
            snapshot = _configuration_snapshot(self)
        changes = {
            name: getattr(self, name)
            for name in _CORE_CONFIGURATION_FIELDS
            if _configuration_value_changed(name, getattr(self, name), snapshot[name])
        }
        current = self.core_backend.update_configuration(changes)
        for name in _CORE_CONFIGURATION_FIELDS:
            value = current[name]
            if name == "action_handlers":
                value = dict(value)
            setattr(self, name, value)
            if name == "execution_profile":
                self.api.profile = value
            elif name == "input_resources":
                self.api.input_resources = self.input_resources
            snapshot[name] = dict(value) if name == "action_handlers" else value
        self._core_configuration_snapshot = snapshot

    def create_execution_host(
        self, *, owner_id: str = "managed-worker", ttl_seconds: int = 30
    ) -> Any:
        """Create the standard worker using this backend's durable result store."""
        if self._closed:
            raise RuntimeError("Managed backend is closed")
        if self.core_backend is not None:
            self._sync_core_configuration()
            host = self.core_backend.create_execution_host(
                owner_id=owner_id, ttl_seconds=ttl_seconds
            )
            self.api.attach_runtime_role(f"run_worker:{owner_id}", host)
            return host
        durable = self.api.durable_work
        if durable is None:
            raise RuntimeError("Managed backend has no durable work store")
        from etlantic.runtime.execution_host import ExecutionHost
        from etlantic.runtime.managed_execution import ManagedExecutionAdapter

        event_store = cast(IdempotentEventStore, self.api.events)

        def publish_event(
            ctx: ControlPlaneContext,
            event_key: str,
            kind: str,
            payload: Mapping[str, Any],
        ) -> None:
            event_store.append_once(
                ctx, event_key=event_key, kind=kind, payload=payload
            )

        return ExecutionHost(
            durable,
            owner_id=owner_id,
            ttl_seconds=ttl_seconds,
            runner=ManagedExecutionAdapter(
                report_store_factory=self.report_store_factory,
                report_store_scope_key=self.report_store_scope_key,
                artifact_root=self.artifact_root,
                artifact_report_resolver=self.api.managed_service.resolve_artifact_report
                if self.api.managed_service is not None
                else None,
                event_publisher=publish_event,
                profile=self.execution_profile,
                input_resource_store=self.input_resources,
                run_artifact_retention_seconds=self.run_artifact_retention_seconds,
                artifact_cleanup_batch_size=self.run_artifact_cleanup_batch_size,
            ),
            quota_provider=self.api.quotas,
        )

    def cleanup_expired_run_artifacts(
        self,
        ctx: ControlPlaneContext,
        *,
        now: datetime | None = None,
        limit: int | None = None,
    ) -> ArtifactRetentionResult:
        """Run one bounded, operator-invoked durable artifact cleanup pass."""
        if self._closed:
            raise RuntimeError("Managed backend is closed")
        self._sync_core_configuration()
        if self.run_artifact_retention_seconds is None:
            return ArtifactRetentionResult(enabled=False)
        from etlantic.runtime.artifact_retention import cleanup_expired_run_artifacts

        service = self.api.managed_service
        return cleanup_expired_run_artifacts(
            ctx,
            report_store=self.report_store_factory(ctx),
            artifact_root=self.artifact_root,
            retention_seconds=self.run_artifact_retention_seconds,
            report_resolver=(
                lambda report: service.resolve_artifact_report(ctx, report)
            )
            if service is not None
            else None,
            report_store_factory=lambda: self.report_store_factory(ctx),
            limit=(self.run_artifact_cleanup_batch_size if limit is None else limit),
            now=now,
        )

    def create_action_execution_host(
        self, *, worker_id: str = "action-worker-1"
    ) -> ActionExecutionHost:
        """Create the separate worker for connector inspection/action jobs."""
        if self._closed:
            raise RuntimeError("Managed backend is closed")
        if self.core_backend is not None:
            self._sync_core_configuration()
            host = self.core_backend.create_action_execution_host(worker_id=worker_id)
            self.api.attach_runtime_role(f"action_worker:{worker_id}", host)
            return host
        durable = self.api.durable_work
        if durable is None:
            raise RuntimeError("Managed backend has no durable work store")
        from etlantic.runtime.action_execution_host import ActionExecutionHost

        handlers = dict(self.action_handlers)
        if self.api.managed_service is not None:
            handlers["run.prepare"] = self._run_preparation_action
        return ActionExecutionHost(
            durable,
            handlers=handlers,
            authorizer=self.api.authorizer,
            profile=self.execution_profile,
            worker_id=worker_id,
            lease_seconds=self.action_job_lease_seconds,
            preview_result_ttl_seconds=self.preview_result_ttl_seconds,
        )

    def create_scheduler(
        self,
        *,
        owner_id: str,
        ttl_seconds: int = 30,
        clock: Any = None,
        wake: Any = None,
    ) -> Any:
        """Create the standard scheduler over this backend's shared stores."""
        if self._closed:
            raise RuntimeError("Managed backend is closed")
        if self.core_backend is not None:
            self._sync_core_configuration()
            scheduler = self.core_backend.create_scheduler(
                owner_id=owner_id,
                ttl_seconds=ttl_seconds,
                clock=clock,
                wake=wake,
            )
        else:
            if self.api.schedule_store is None or self.api.managed_service is None:
                raise RuntimeError("Managed scheduler collaborators are not configured")
            from etlantic.runtime.scheduler_service import SchedulerService

            scheduler = SchedulerService(
                self.api.schedule_store,
                durable=self.api.durable_work,
                owner_id=owner_id,
                ttl_seconds=ttl_seconds,
                clock=clock,
                wake=wake,
                occurrence_service=self.api.managed_service,
                profile=self.execution_profile,
            )
        self.api.attach_runtime_role("scheduler", scheduler)
        return scheduler

    async def _run_preparation_action(
        self,
        ctx: ControlPlaneContext,
        request: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        service = self.api.managed_service
        if service is None:
            raise RuntimeError("Managed run preparation is not configured")
        operation_id = request.get("_operation_id")
        worker_id = request.get("_worker_id")
        fencing_token = request.get("_fencing_token")
        cancel_event = request.get("_cancel_event")
        is_cancelled = getattr(cancel_event, "is_set", None)
        if (
            not isinstance(operation_id, str)
            or not isinstance(worker_id, str)
            or type(fencing_token) is not int
            or not callable(is_cancelled)
        ):
            raise ValueError("invalid preparation worker context")
        return await asyncio.to_thread(
            service.execute_run_preparation,
            ctx,
            operation_id,
            worker_id=worker_id,
            fencing_token=fencing_token,
            request=request,
            is_cancelled=cast(Callable[[], bool], is_cancelled),
        )


def create_managed_backend(
    config: ManagedBackendConfig,
    *,
    authorizer: Authorizer,
    context_factory: ContextFactory,
    principal_dependency: PrincipalDependency | None = None,
    planning_context_factory: (Callable[[Any, Any], PlanningContext] | None) = None,
) -> ManagedBackend:
    """Build the legacy HTTP facade over the provider-owned core graph."""
    try:
        import etlantic_sqlmodel
    except ImportError as exc:
        raise RuntimeError(
            "The managed SQL backend requires etlantic-fastapi[managed]"
        ) from exc

    provider_config = etlantic_sqlmodel.SQLModelBackendConfig(
        database_url=config.database_url,
        store_id=config.store_id,
        profile=config.profile,
        engine_options=config.engine_options,
        event_retention_max_events_per_scope=(
            config.event_retention_max_events_per_scope
        ),
        event_idempotency_retention_seconds=(
            config.event_idempotency_retention_seconds
        ),
        max_input_upload_bytes=config.max_input_upload_bytes,
        input_upload_ttl_seconds=config.input_upload_ttl_seconds,
        input_resource_retention_seconds=config.input_resource_retention_seconds,
        action_job_max_deadline_seconds=config.action_job_max_deadline_seconds,
        action_job_lease_seconds=config.action_job_lease_seconds,
        preview_result_ttl_seconds=config.preview_result_ttl_seconds,
        run_artifact_retention_seconds=config.run_artifact_retention_seconds,
        run_artifact_cleanup_batch_size=config.run_artifact_cleanup_batch_size,
        artifact_root=config.artifact_root,
        action_handlers=config.action_handlers,
        policy=config.policy,
        approvals=config.approvals,
        quotas=config.quotas,
        audit=config.audit,
        attestations=config.attestations,
        require_attestations=config.require_attestations,
        schedule_parameter_resolver=config.schedule_parameter_resolver,
        schedule_clock=config.schedule_clock,
    )
    core_backend = etlantic_sqlmodel.create_managed_backend(
        provider_config,
        authorizer=authorizer,
        planning_context_factory=planning_context_factory,
    )
    try:
        return adapt_managed_backend(
            core_backend,
            context_factory=context_factory,
            principal_dependency=principal_dependency,
            input_upload_ttl_seconds=config.input_upload_ttl_seconds,
            title=config.title,
            version=config.version,
        )
    except BaseException:
        core_backend.close()
        raise


def adapt_managed_backend(
    core_backend: Any,
    *,
    context_factory: ContextFactory,
    principal_dependency: PrincipalDependency | None = None,
    input_upload_ttl_seconds: int = 60 * 60,
    title: str = "ETLantic Control Plane",
    version: str | None = None,
) -> ManagedBackend:
    """Adapt an existing core backend to the optional FastAPI transport.

    The adapter adds only HTTP identity/context derivation and representation;
    the supplied backend retains its engine ownership and shared service graph.
    """
    if getattr(core_backend, "_closed", False):
        raise RuntimeError("Managed backend is closed")
    if type(input_upload_ttl_seconds) is not int or input_upload_ttl_seconds < 1:
        raise ValueError("input_upload_ttl_seconds must be a positive integer")
    service = core_backend.managed_service
    api = ETLanticAPI(
        authorizer=core_backend.authorizer,
        definitions=core_backend.definitions,
        submissions=core_backend.submissions,
        events=core_backend.events,
        registry=core_backend.registry,
        context_factory=context_factory,
        principal_dependency=principal_dependency or principal_from_header,
        profile=core_backend.execution_profile,
        durable_work=core_backend.durable_work,
        input_resources=core_backend.input_resources,
        input_upload_ttl_seconds=input_upload_ttl_seconds,
        input_resource_retention_seconds=service.input_resource_retention_seconds,
        schedule_store=core_backend.schedule_store,
        policy=service.policy,
        approvals=service.approvals,
        quotas=service.quotas,
        audit=service.audit,
        attestations=service.attestations,
        managed_service=service,
        planning_context_factory=service.planning_context_factory,
        title=title,
    )
    api.bind_schedule_service(core_backend.schedule_service)
    if version is not None:
        api.version = version
    backend = ManagedBackend(
        api=api,
        engine=core_backend.engine,
        report_store_factory=core_backend.report_store_factory,
        input_resources=core_backend.input_resources,
        artifact_root=core_backend.artifact_root,
        report_store_scope_key=core_backend.report_store_scope_key,
        action_handlers=dict(core_backend.action_handlers),
        action_job_lease_seconds=core_backend.action_job_lease_seconds,
        preview_result_ttl_seconds=core_backend.preview_result_ttl_seconds,
        run_artifact_retention_seconds=core_backend.run_artifact_retention_seconds,
        run_artifact_cleanup_batch_size=core_backend.run_artifact_cleanup_batch_size,
        execution_profile=core_backend.execution_profile,
        core_backend=core_backend,
    )
    return backend


def create_managed_app(
    config: ManagedBackendConfig,
    *,
    authorizer: Authorizer,
    context_factory: ContextFactory,
    principal_dependency: PrincipalDependency | None = None,
    planning_context_factory: (Callable[[Any, Any], PlanningContext] | None) = None,
    install_handlers: bool = True,
) -> FastAPI:
    """Create a managed HTTP app and own its engine for the app lifespan.

    The same :class:`ManagedApplicationService` remains available through
    ``app.state.managed_backend.api.managed_service`` to headless callers. A
    shutdown or partial startup failure disposes only the shared connection
    pool; committed definitions and accepted work remain in the database.
    """
    backend = create_managed_backend(
        config,
        authorizer=authorizer,
        context_factory=context_factory,
        principal_dependency=principal_dependency,
        planning_context_factory=planning_context_factory,
    )
    try:
        app = create_app(
            backend.api,
            install_handlers=install_handlers,
            with_lifespan=True,
        )
        app.state.managed_backend = backend
        api_lifespan = app.router.lifespan_context

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            try:
                async with api_lifespan(app):
                    if not app.state.control_plane_ready:
                        raise RuntimeError("Managed backend stores are not ready")
                    yield
            finally:
                app.state.control_plane_ready = False
                backend.close()

        app.router.lifespan_context = lifespan
        return app
    except BaseException:
        backend.close()
        raise


__all__ = [
    "ManagedBackend",
    "ManagedBackendConfig",
    "adapt_managed_backend",
    "create_managed_app",
    "create_managed_backend",
]
