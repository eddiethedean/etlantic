"""Transport-independent SQLModel backend composition."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, cast

from etlantic.control_plane import ManagedBackend
from etlantic.control_plane.managed_config import (
    MANAGED_BACKEND_DEFAULTS,
    empty_managed_mapping,
    validate_managed_backend_settings,
)
from etlantic.control_plane.protocols import Authorizer
from etlantic.control_plane.registry_protocols import RegistryProvider
from etlantic.profile import resolve_profile
from etlantic.registry import PlanningContext
from etlantic.service import ManagedApplicationService
from etlantic_sqlmodel.schema import inspect_schema

ActionHandler = Callable[[Any, Mapping[str, Any]], Awaitable[Mapping[str, Any]]]


@dataclass(frozen=True, slots=True)
class SQLModelBackendConfig:
    """SQLModel deployment settings; database URLs never appear in repr."""

    database_url: str | None = field(
        default=MANAGED_BACKEND_DEFAULTS["database_url"], repr=False
    )
    store_id: str = MANAGED_BACKEND_DEFAULTS["store_id"]
    profile: Any = field(default=MANAGED_BACKEND_DEFAULTS["profile"], repr=False)
    engine_options: Mapping[str, Any] = field(
        default_factory=empty_managed_mapping, repr=False
    )
    event_retention_max_events_per_scope: int = MANAGED_BACKEND_DEFAULTS[
        "event_retention_max_events_per_scope"
    ]
    event_idempotency_retention_seconds: int = MANAGED_BACKEND_DEFAULTS[
        "event_idempotency_retention_seconds"
    ]
    max_input_upload_bytes: int = MANAGED_BACKEND_DEFAULTS["max_input_upload_bytes"]
    input_upload_ttl_seconds: int = MANAGED_BACKEND_DEFAULTS["input_upload_ttl_seconds"]
    input_resource_retention_seconds: int = MANAGED_BACKEND_DEFAULTS[
        "input_resource_retention_seconds"
    ]
    action_job_max_deadline_seconds: int = MANAGED_BACKEND_DEFAULTS[
        "action_job_max_deadline_seconds"
    ]
    action_job_lease_seconds: int = MANAGED_BACKEND_DEFAULTS["action_job_lease_seconds"]
    preview_result_ttl_seconds: int = MANAGED_BACKEND_DEFAULTS[
        "preview_result_ttl_seconds"
    ]
    run_artifact_retention_seconds: int | None = MANAGED_BACKEND_DEFAULTS[
        "run_artifact_retention_seconds"
    ]
    run_artifact_cleanup_batch_size: int = MANAGED_BACKEND_DEFAULTS[
        "run_artifact_cleanup_batch_size"
    ]
    schedule_clock: Any = field(
        default=MANAGED_BACKEND_DEFAULTS["schedule_clock"], repr=False
    )
    artifact_root: str | None = field(
        default=MANAGED_BACKEND_DEFAULTS["artifact_root"], repr=False
    )
    action_handlers: Mapping[str, ActionHandler] = field(
        default_factory=empty_managed_mapping, repr=False
    )
    policy: Any = field(default=MANAGED_BACKEND_DEFAULTS["policy"], repr=False)
    approvals: Any = field(default=MANAGED_BACKEND_DEFAULTS["approvals"], repr=False)
    quotas: Any = field(default=MANAGED_BACKEND_DEFAULTS["quotas"], repr=False)
    audit: Any = field(default=MANAGED_BACKEND_DEFAULTS["audit"], repr=False)
    attestations: Any = field(
        default=MANAGED_BACKEND_DEFAULTS["attestations"], repr=False
    )
    require_attestations: bool = MANAGED_BACKEND_DEFAULTS["require_attestations"]
    execution_route: str = MANAGED_BACKEND_DEFAULTS["execution_route"]
    schedule_parameter_resolver: Any = field(
        default=MANAGED_BACKEND_DEFAULTS["schedule_parameter_resolver"], repr=False
    )

    def __post_init__(self) -> None:
        validate_managed_backend_settings(self)


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
            execution_route=config.execution_route,
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
            input_upload_ttl_seconds=config.input_upload_ttl_seconds,
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
