"""Standard SQLModel-backed managed application constructors."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from importlib import import_module
from typing import TYPE_CHECKING, Any, cast

from etlantic.control_plane.protocols import Authorizer
from etlantic.control_plane.registry_definitions import RegistryDefinitionRepository
from etlantic.registry import PlanningContext
from etlantic_fastapi.api import ETLanticAPI, create_app
from etlantic_fastapi.auth import (
    ContextFactory,
    PrincipalDependency,
    principal_from_header,
)
from fastapi import FastAPI

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


def _empty_engine_options() -> dict[str, Any]:
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

    def __post_init__(self) -> None:
        if not self.database_url.strip():
            raise ValueError("database_url must be a non-empty SQLAlchemy URL")
        if not self.store_id.strip():
            raise ValueError("store_id must be non-empty")


@dataclass(slots=True)
class ManagedBackend:
    """Headless services and their explicitly owned shared SQL engine."""

    api: ETLanticAPI = field(repr=False)
    engine: Engine = field(repr=False)
    _closed: bool = field(default=False, init=False, repr=False)

    def close(self) -> None:
        """Dispose idle database connections without deleting accepted work."""
        if self._closed:
            return
        self.engine.dispose()
        self._closed = True


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
        api = ETLanticAPI(
            authorizer=authorizer,
            definitions=RegistryDefinitionRepository(registry),
            submissions=stores.SQLModelSubmissionStore(engine),
            events=stores.SqlModelEventStore(engine),
            registry=registry,
            context_factory=context_factory,
            principal_dependency=principal_dependency or principal_from_header,
            profile=config.profile,
            durable_work=stores.SQLModelDurableWorkStore(
                engine, store_id=config.store_id
            ),
            planning_context_factory=planning_context_factory,
            title=config.title,
        )
        if config.version is not None:
            api.version = config.version
        api.enable_managed_execution()
        return ManagedBackend(api=api, engine=engine)
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
