"""Transport-independent SQLModel backend composition."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, cast

from etlantic.control_plane import ManagedBackend
from etlantic.control_plane.action_jobs import (
    MAX_PREVIEW_RESULT_TTL_SECONDS,
    MIN_PREVIEW_RESULT_TTL_SECONDS,
)
from etlantic.control_plane.event_retention import (
    DEFAULT_EVENT_IDEMPOTENCY_RETENTION_SECONDS,
)
from etlantic.control_plane.protocols import Authorizer
from etlantic.control_plane.registry_protocols import RegistryProvider
from etlantic.profile import resolve_profile
from etlantic.registry import PlanningContext
from etlantic.service import ManagedApplicationService
from etlantic_sqlmodel.schema import inspect_schema

ActionHandler = Callable[[Any, Mapping[str, Any]], Awaitable[Mapping[str, Any]]]


def _empty_engine_options() -> dict[str, Any]:
    return {}


def _empty_action_handlers() -> dict[str, ActionHandler]:
    return {}


def _is_nonempty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


@dataclass(frozen=True, slots=True)
class SQLModelBackendConfig:
    """SQLModel deployment settings; database URLs never appear in repr."""

    database_url: str | None = field(default=None, repr=False)
    store_id: str = "default"
    profile: Any = field(default="development", repr=False)
    engine_options: Mapping[str, Any] = field(
        default_factory=_empty_engine_options, repr=False
    )
    event_retention_max_events_per_scope: int = 100_000
    event_idempotency_retention_seconds: int = (
        DEFAULT_EVENT_IDEMPOTENCY_RETENTION_SECONDS
    )
    max_input_upload_bytes: int = 64 * 1024 * 1024
    input_upload_ttl_seconds: int = 60 * 60
    input_resource_retention_seconds: int = 90 * 24 * 60 * 60
    action_job_max_deadline_seconds: int = 300
    action_job_lease_seconds: int = 330
    preview_result_ttl_seconds: int = 60 * 60
    run_artifact_retention_seconds: int | None = None
    run_artifact_cleanup_batch_size: int = 100
    schedule_clock: Any = field(default=None, repr=False)
    artifact_root: str | None = field(default=None, repr=False)
    action_handlers: Mapping[str, ActionHandler] = field(
        default_factory=_empty_action_handlers, repr=False
    )
    policy: Any = field(default=None, repr=False)
    approvals: Any = field(default=None, repr=False)
    quotas: Any = field(default=None, repr=False)
    audit: Any = field(default=None, repr=False)
    attestations: Any = field(default=None, repr=False)
    require_attestations: bool = False
    schedule_parameter_resolver: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.database_url is not None and not _is_nonempty_text(self.database_url):
            raise ValueError("database_url must be a non-empty SQLAlchemy URL")
        if not _is_nonempty_text(self.store_id):
            raise ValueError("store_id must be non-empty")
        for name in (
            "event_retention_max_events_per_scope",
            "event_idempotency_retention_seconds",
            "max_input_upload_bytes",
            "input_upload_ttl_seconds",
            "input_resource_retention_seconds",
        ):
            value = getattr(self, name)
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
            raise ValueError("action_job_lease_seconds must exceed the action deadline")
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
            raise ValueError("run_artifact_retention_seconds must be positive or None")
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


def create_managed_backend(
    config: SQLModelBackendConfig,
    *,
    authorizer: Authorizer,
    planning_context_factory: Callable[[Any, Any], PlanningContext] | None = None,
    engine: Any = None,
) -> ManagedBackend:
    """Construct an authorized headless service graph over one migrated engine.

    This function does not import FastAPI and does not derive caller identity.
    Callers pass an authenticated, server-derived ControlPlaneContext to each
    service command and worker tick.
    """
    try:
        from sqlalchemy import create_engine
    except ImportError as exc:
        raise RuntimeError("The SQLModel backend requires sqlalchemy") from exc

    owns_engine = engine is None
    try:
        if owns_engine:
            if config.database_url is None:
                raise ValueError(
                    "database_url is required when no SQLAlchemy engine is supplied"
                )
            engine_options = dict(config.engine_options)
            engine_options.setdefault("pool_pre_ping", True)
            engine = create_engine(config.database_url, **engine_options)
        elif config.database_url is not None:
            raise ValueError(
                "pass either database_url in config or an injected engine, not both"
            )

        inspection = inspect_schema(engine)
        if not inspection.compatible:
            raise RuntimeError(
                "SQLModel schema is not ready for managed execution "
                f"({inspection.reason_code}); apply or repair the explicit "
                "etlantic_sqlmodel migrations before starting the backend"
            )

        from etlantic.control_plane.registry_definitions import (
            RegistryDefinitionRepository,
        )
        from etlantic_sqlmodel.control_plane import (
            SQLModelDurableWorkStore,
            SqlModelEventStore,
            SqlModelInputResourceStore,
            SqlModelRegistryProvider,
            SqlModelRunReportStoreProvider,
            SQLModelScheduleStore,
            SQLModelSubmissionStore,
        )

        registry = SqlModelRegistryProvider(engine)
        report_provider = SqlModelRunReportStoreProvider(engine)
        input_resources = SqlModelInputResourceStore(
            engine, max_upload_bytes=config.max_input_upload_bytes
        )
        profile = resolve_profile(config.profile, allow_adhoc_profile=False)
        definitions = RegistryDefinitionRepository(cast(RegistryProvider, registry))
        submissions = SQLModelSubmissionStore(engine)
        events = SqlModelEventStore(
            engine,
            max_events_per_scope=config.event_retention_max_events_per_scope,
            idempotency_retention_seconds=(config.event_idempotency_retention_seconds),
        )
        durable = SQLModelDurableWorkStore(engine, store_id=config.store_id)
        schedules = SQLModelScheduleStore(engine, store_id=config.store_id)
        managed_service = ManagedApplicationService(
            authorizer=authorizer,
            definitions=definitions,
            submissions=submissions,
            durable_work=durable,
            events=events,
            profile=profile,
            policy=config.policy,
            approvals=config.approvals,
            quotas=config.quotas,
            audit=config.audit,
            attestations=config.attestations,
            require_attestations=config.require_attestations,
            planning_context_factory=planning_context_factory,
            input_resources=input_resources,
            input_resource_retention_seconds=config.input_resource_retention_seconds,
            run_artifact_retention_seconds=config.run_artifact_retention_seconds,
            action_job_max_deadline_seconds=config.action_job_max_deadline_seconds,
            artifact_root=config.artifact_root,
            schedule_parameter_resolver=config.schedule_parameter_resolver,
        )
        managed_service.report_store_factory = report_provider.for_context
        report_provider_scope = report_provider.retention_scope_key
        return ManagedBackend(
            authorizer=authorizer,
            engine=engine,
            managed_service=managed_service,
            registry=registry,
            definitions=definitions,
            submissions=submissions,
            events=events,
            durable_work=durable,
            schedule_store=schedules,
            input_resources=input_resources,
            report_store_factory=report_provider.for_context,
            report_store_scope_key=report_provider_scope,
            execution_profile=profile,
            artifact_root=config.artifact_root,
            action_handlers=dict(config.action_handlers),
            action_job_lease_seconds=config.action_job_lease_seconds,
            preview_result_ttl_seconds=config.preview_result_ttl_seconds,
            run_artifact_retention_seconds=config.run_artifact_retention_seconds,
            run_artifact_cleanup_batch_size=config.run_artifact_cleanup_batch_size,
            schedule_clock=config.schedule_clock,
            event_idempotency_retention_seconds=(
                config.event_idempotency_retention_seconds
            ),
            owns_engine=owns_engine,
        )
    except BaseException:
        if owns_engine and engine is not None:
            engine.dispose()
        raise


__all__ = [
    "ActionHandler",
    "SQLModelBackendConfig",
    "create_managed_backend",
]
