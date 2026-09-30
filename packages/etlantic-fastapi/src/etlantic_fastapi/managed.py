"""Standard SQLModel-backed managed application constructors."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from importlib import import_module
from typing import TYPE_CHECKING, Any, cast

from etlantic.control_plane.models import ControlPlaneContext
from etlantic.control_plane.protocols import Authorizer, IdempotentEventStore
from etlantic.control_plane.registry_definitions import RegistryDefinitionRepository
from etlantic.profile import Profile, resolve_profile
from etlantic.registry import PlanningContext
from etlantic.runtime.action_execution_host import ActionHandler
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


def _empty_engine_options() -> dict[str, Any]:
    return {}


def _empty_action_handlers() -> dict[str, ActionHandler]:
    return {}


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
    action_handlers: Mapping[str, ActionHandler] = field(
        default_factory=_empty_action_handlers, repr=False
    )

    def __post_init__(self) -> None:
        if not self.database_url.strip():
            raise ValueError("database_url must be a non-empty SQLAlchemy URL")
        if not self.store_id.strip():
            raise ValueError("store_id must be non-empty")
        if (
            type(self.event_retention_max_events_per_scope) is not int
            or self.event_retention_max_events_per_scope < 1
        ):
            raise ValueError(
                "event_retention_max_events_per_scope must be a positive integer"
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
            or self.action_job_lease_seconds
            <= self.action_job_max_deadline_seconds
        ):
            raise ValueError(
                "action_job_lease_seconds must exceed the maximum action deadline"
            )
        supported_actions = {
            "connector.test",
            "connector.catalog",
            "connector.schema.inspect",
            "connector.preflight",
        }
        unsupported_actions = set(self.action_handlers) - supported_actions
        if unsupported_actions:
            raise ValueError(
                "action_handlers contains unsupported action(s): "
                + ", ".join(sorted(unsupported_actions))
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
    execution_profile: Profile | None = field(default=None, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)

    def close(self) -> None:
        """Dispose idle database connections without deleting accepted work."""
        if self._closed:
            return
        self.engine.dispose()
        self._closed = True

    def create_execution_host(
        self, *, owner_id: str = "managed-worker", ttl_seconds: int = 30
    ) -> Any:
        """Create the standard worker using this backend's durable result store."""
        if self._closed:
            raise RuntimeError("Managed backend is closed")
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
                event_publisher=publish_event,
                profile=self.execution_profile,
                input_resource_store=self.input_resources,
            ),
        )

    def create_action_execution_host(
        self, *, worker_id: str = "action-worker-1"
    ) -> ActionExecutionHost:
        """Create the separate worker for test/catalog/schema/preflight jobs."""
        if self._closed:
            raise RuntimeError("Managed backend is closed")
        durable = self.api.durable_work
        if durable is None:
            raise RuntimeError("Managed backend has no durable work store")
        from etlantic.runtime.action_execution_host import ActionExecutionHost

        return ActionExecutionHost(
            durable,
            handlers=self.action_handlers,
            authorizer=self.api.authorizer,
            profile=self.execution_profile,
            worker_id=worker_id,
            lease_seconds=self.action_job_lease_seconds,
        )


def create_managed_backend(
    config: ManagedBackendConfig,
    *,
    authorizer: Authorizer,
    context_factory: ContextFactory,
    principal_dependency: PrincipalDependency | None = None,
    planning_context_factory: (Callable[[Any, Any], PlanningContext] | None) = None,
) -> ManagedBackend:
    """Construct shared headless services over the migrated SQLModel stores.

    Install the optional ``etlantic-fastapi[managed]`` extra. The function
    creates one engine shared by definition, submission, event and durable-work
    stores, and disposes it if any later initialization step fails.
    """
    try:
        from sqlalchemy import create_engine, inspect
    except ImportError as exc:
        raise RuntimeError(
            "The managed SQL backend requires etlantic-fastapi[managed]"
        ) from exc

    engine: Engine | None = None
    try:
        engine_options: dict[str, Any] = dict(config.engine_options)
        engine_options.setdefault("pool_pre_ping", True)
        engine = create_engine(config.database_url, **engine_options)

        migrations = cast(Any, import_module("etlantic_sqlmodel.migrations"))
        if not inspect(engine).has_table("etlantic_sqlmodel_schema_version"):
            raise RuntimeError(
                "The SQLModel schema is not migrated; apply the versioned "
                "etlantic_sqlmodel migrations before starting the backend"
            )
        schema_version = migrations.current_version(engine)
        latest_version = migrations.VERSIONS[-1]
        if schema_version != latest_version:
            raise RuntimeError(
                f"SQLModel schema version {schema_version!r} does not match "
                f"required version {latest_version!r}"
            )

        stores = cast(Any, import_module("etlantic_sqlmodel.control_plane"))
        registry = stores.SqlModelRegistryProvider(engine)
        report_store_provider = stores.SqlModelRunReportStoreProvider(engine)
        input_resources = stores.SqlModelInputResourceStore(
            engine, max_upload_bytes=config.max_input_upload_bytes
        )
        execution_profile = resolve_profile(config.profile, allow_adhoc_profile=False)
        api = ETLanticAPI(
            authorizer=authorizer,
            definitions=RegistryDefinitionRepository(registry),
            submissions=stores.SQLModelSubmissionStore(engine),
            events=stores.SqlModelEventStore(
                engine,
                max_events_per_scope=config.event_retention_max_events_per_scope,
            ),
            registry=registry,
            context_factory=context_factory,
            principal_dependency=principal_dependency or principal_from_header,
            profile=execution_profile,
            durable_work=stores.SQLModelDurableWorkStore(
                engine, store_id=config.store_id
            ),
            input_resources=input_resources,
            input_upload_ttl_seconds=config.input_upload_ttl_seconds,
            input_resource_retention_seconds=config.input_resource_retention_seconds,
            planning_context_factory=planning_context_factory,
            title=config.title,
        )
        if config.version is not None:
            api.version = config.version
        api.enable_managed_execution()
        if api.managed_service is not None:
            api.managed_service.report_store_factory = report_store_provider.for_context
            api.managed_service.action_job_max_deadline_seconds = (
                config.action_job_max_deadline_seconds
            )
        return ManagedBackend(
            api=api,
            engine=engine,
            report_store_factory=report_store_provider.for_context,
            input_resources=input_resources,
            action_handlers=dict(config.action_handlers),
            action_job_lease_seconds=config.action_job_lease_seconds,
            execution_profile=execution_profile,
        )
    except BaseException:
        if engine is not None:
            engine.dispose()
        raise


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
    "create_managed_app",
    "create_managed_backend",
]
