"""Transport-independent handle for the standard managed application graph."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from threading import RLock
from typing import Any, cast

from etlantic.control_plane.action_jobs import (
    MAX_PREVIEW_RESULT_TTL_SECONDS,
    MIN_PREVIEW_RESULT_TTL_SECONDS,
)
from etlantic.control_plane.authz import validate_control_plane_context
from etlantic.control_plane.event_retention import (
    DEFAULT_EVENT_IDEMPOTENCY_RETENTION_SECONDS,
)
from etlantic.control_plane.models import ControlPlaneContext
from etlantic.control_plane.protocols import Authorizer, IdempotentEventStore
from etlantic.profile import Profile
from etlantic.reports.retention import ArtifactRetentionResult

ActionHandler = Callable[
    [ControlPlaneContext, Mapping[str, Any]], Awaitable[Mapping[str, Any]]
]
_CONFIGURABLE_FIELDS = frozenset(
    {
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
    }
)


def _empty_action_handlers() -> dict[str, ActionHandler]:
    return {}


def _empty_roles() -> list[Any]:
    return []


def _is_nonempty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


@dataclass(slots=True)
class ManagedBackend:
    """Shared headless services, stores, runtime factories, and resource owner.

    The handle has no HTTP object or FastAPI dependency. Consumers supply a
    trusted ControlPlaneContext to each authorized service operation and role
    tick. The SQL provider owns construction of this graph.
    """

    authorizer: Authorizer = field(repr=False)
    engine: Any = field(repr=False)
    managed_service: Any = field(repr=False)
    registry: Any = field(repr=False)
    definitions: Any = field(repr=False)
    submissions: Any = field(repr=False)
    events: Any = field(repr=False)
    durable_work: Any = field(repr=False)
    schedule_store: Any = field(repr=False)
    input_resources: Any = field(repr=False)
    report_store_factory: Callable[[ControlPlaneContext], Any] = field(repr=False)
    report_store_scope_key: Callable[[ControlPlaneContext], object] | None = field(
        default=None, repr=False
    )
    execution_profile: Profile | None = field(default=None, repr=False)
    artifact_root: str | None = field(default=None, repr=False)
    action_handlers: Mapping[str, ActionHandler] = field(
        default_factory=_empty_action_handlers, repr=False
    )
    action_job_lease_seconds: int = 330
    preview_result_ttl_seconds: int = 60 * 60
    run_artifact_retention_seconds: int | None = None
    run_artifact_cleanup_batch_size: int = 100
    schedule_clock: Any = field(default=None, repr=False)
    event_idempotency_retention_seconds: int = (
        DEFAULT_EVENT_IDEMPOTENCY_RETENTION_SECONDS
    )
    owns_engine: bool = field(default=True, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)
    _roles: list[Any] = field(default_factory=_empty_roles, init=False, repr=False)
    _schedule_commands: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if (
            type(self.preview_result_ttl_seconds) is not int
            or not MIN_PREVIEW_RESULT_TTL_SECONDS
            <= self.preview_result_ttl_seconds
            <= MAX_PREVIEW_RESULT_TTL_SECONDS
        ):
            raise ValueError(
                "preview_result_ttl_seconds is outside its supported range"
            )
        if (
            type(self.action_job_lease_seconds) is not int
            or self.action_job_lease_seconds < 1
        ):
            raise ValueError("action_job_lease_seconds must be positive")
        if (
            type(self.run_artifact_cleanup_batch_size) is not int
            or not 1 <= self.run_artifact_cleanup_batch_size <= 1000
        ):
            raise ValueError(
                "run_artifact_cleanup_batch_size must be between 1 and 1000"
            )
        if self.run_artifact_retention_seconds is not None and (
            type(self.run_artifact_retention_seconds) is not int
            or self.run_artifact_retention_seconds < 1
        ):
            raise ValueError("run_artifact_retention_seconds must be positive or None")
        if (
            type(self.event_idempotency_retention_seconds) is not int
            or self.event_idempotency_retention_seconds < 1
        ):
            raise ValueError("event_idempotency_retention_seconds must be positive")

    @property
    def schedule_service(self) -> Any:
        """Return authorized schedule commands over this shared graph."""
        with self._lock:
            self._ensure_open()
            if self._schedule_commands is None:
                from etlantic.service import ScheduleApplicationService

                self._schedule_commands = ScheduleApplicationService(
                    authorizer=self.authorizer,
                    schedule_store=self.schedule_store,
                    managed_service=self.managed_service,
                    durable_work=self.durable_work,
                    clock=self.schedule_clock,
                )
            return self._schedule_commands

    def create_execution_host(
        self, *, owner_id: str = "managed-worker", ttl_seconds: int = 30
    ) -> Any:
        with self._lock:
            self._ensure_open()
            from etlantic.runtime.execution_host import ExecutionHost
            from etlantic.runtime.managed_execution import ManagedExecutionAdapter

            event_store = cast(IdempotentEventStore, self.events)

            def publish_event(
                ctx: ControlPlaneContext,
                event_key: str,
                kind: str,
                payload: Mapping[str, Any],
            ) -> None:
                event_store.append_once(
                    ctx, event_key=event_key, kind=kind, payload=payload
                )

            host = ExecutionHost(
                self.durable_work,
                owner_id=owner_id,
                ttl_seconds=ttl_seconds,
                runner=ManagedExecutionAdapter(
                    report_store_factory=self.report_store_factory,
                    report_store_scope_key=self.report_store_scope_key,
                    artifact_root=self.artifact_root,
                    artifact_report_resolver=self.managed_service.resolve_artifact_report,
                    event_publisher=publish_event,
                    profile=self.execution_profile,
                    input_resource_store=self.input_resources,
                    run_artifact_retention_seconds=self.run_artifact_retention_seconds,
                    artifact_cleanup_batch_size=self.run_artifact_cleanup_batch_size,
                ),
                quota_provider=getattr(self.managed_service, "quotas", None),
            )
            self._roles.append(host)
            return host

    def create_action_execution_host(
        self, *, worker_id: str = "action-worker-1"
    ) -> Any:
        with self._lock:
            self._ensure_open()
            from etlantic.runtime.action_execution_host import ActionExecutionHost

            handlers = dict(self.action_handlers)
            handlers["run.prepare"] = self._run_preparation_action
            host = ActionExecutionHost(
                self.durable_work,
                handlers=handlers,
                authorizer=self.authorizer,
                profile=self.execution_profile,
                worker_id=worker_id,
                lease_seconds=self.action_job_lease_seconds,
                preview_result_ttl_seconds=self.preview_result_ttl_seconds,
            )
            self._roles.append(host)
            return host

    def create_scheduler(
        self,
        *,
        owner_id: str,
        ttl_seconds: int = 30,
        clock: Any = None,
        wake: Any = None,
    ) -> Any:
        if not _is_nonempty_text(owner_id):
            raise ValueError("owner_id must be a non-empty unique role identity")
        with self._lock:
            self._ensure_open()
            from etlantic.runtime.scheduler_service import SchedulerService

            host = SchedulerService(
                self.schedule_store,
                durable=self.durable_work,
                clock=self.schedule_clock if clock is None else clock,
                owner_id=owner_id,
                ttl_seconds=ttl_seconds,
                wake=wake,
                occurrence_service=self.managed_service,
                profile=self.execution_profile,
            )
            self._roles.append(host)
            return host

    async def _run_preparation_action(
        self,
        ctx: ControlPlaneContext,
        request: Mapping[str, Any],
    ) -> Mapping[str, Any]:
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
            self.managed_service.execute_run_preparation,
            ctx,
            operation_id,
            worker_id=worker_id,
            fencing_token=fencing_token,
            request=request,
            is_cancelled=cast(Callable[[], bool], is_cancelled),
        )

    def cleanup_expired_run_artifacts(
        self,
        ctx: ControlPlaneContext,
        *,
        now: datetime | None = None,
        limit: int | None = None,
    ) -> ArtifactRetentionResult:
        self._ensure_open()
        validate_control_plane_context(ctx)
        if self.run_artifact_retention_seconds is None:
            return ArtifactRetentionResult(enabled=False)
        from etlantic.runtime.artifact_retention import cleanup_expired_run_artifacts

        return cleanup_expired_run_artifacts(
            ctx,
            report_store=self.report_store_factory(ctx),
            artifact_root=self.artifact_root,
            retention_seconds=self.run_artifact_retention_seconds,
            report_resolver=lambda report: self.managed_service.resolve_artifact_report(
                ctx, report
            ),
            report_store_factory=lambda: self.report_store_factory(ctx),
            limit=(self.run_artifact_cleanup_batch_size if limit is None else limit),
            now=now,
        )

    def update_configuration(self, changes: Mapping[str, Any]) -> dict[str, Any]:
        """Apply explicit transport-facade changes to the shared service graph."""
        unknown = set(changes) - _CONFIGURABLE_FIELDS
        if unknown:
            raise ValueError("unsupported managed backend configuration field")
        with self._lock:
            self._ensure_open()
            for name, value in changes.items():
                setattr(self, name, dict(value) if name == "action_handlers" else value)
            if "report_store_factory" in changes:
                self.managed_service.report_store_factory = self.report_store_factory
            if "input_resources" in changes:
                self.managed_service.input_resources = self.input_resources
            if "artifact_root" in changes:
                self.managed_service.artifact_root = self.artifact_root
            if "run_artifact_retention_seconds" in changes:
                self.managed_service.run_artifact_retention_seconds = (
                    self.run_artifact_retention_seconds
                )
            if "execution_profile" in changes:
                self.managed_service.profile = self.execution_profile
            return {
                name: (
                    dict(getattr(self, name))
                    if name == "action_handlers"
                    else getattr(self, name)
                )
                for name in _CONFIGURABLE_FIELDS
            }

    def close(self) -> None:
        """Drain roles before disposing the owned engine; repeated calls are safe."""
        with self._lock:
            if self._closed:
                return
            for role in self._roles:
                role.request_drain()
            active = [
                role
                for role in self._roles
                if role.status().in_flight > 0 or role.status().activity == "active"
            ]
            if active:
                raise RuntimeError(
                    "Managed backend roles are still active; join them and retry close"
                )
            if self.owns_engine:
                self.engine.dispose()
            self._closed = True

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Managed backend is closed")


__all__ = ["ActionHandler", "ManagedBackend"]
