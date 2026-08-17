"""ETLanticAPI — injectable control-plane FastAPI composition root."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from etlantic.control_plane import (
    ApprovalStore,
    AttestationStore,
    AuditEvidenceStore,
    Authorizer,
    DefinitionRepository,
    DurableWorkStore,
    ErasureStore,
    EventStore,
    HistoryStore,
    ObjectiveStore,
    PolicyProvider,
    QuotaProvider,
    RegistryDefinitionRepository,
    RegistryProvider,
    SubmissionStore,
)
from etlantic_fastapi._version import __version__
from etlantic_fastapi.auth import (
    ContextFactory,
    PrincipalDependency,
    principal_from_header,
    static_context_factory,
)
from etlantic_fastapi.deps import make_context_dependency
from etlantic_fastapi.errors import install_exception_handlers
from etlantic_fastapi.routes import build_control_plane_router
from fastapi import APIRouter, FastAPI


@dataclass
class ETLanticAPI:
    """Control-plane API holding injected stores and auth adapters.

    Heavy pipeline work is never scheduled via FastAPI BackgroundTasks.
    Submission acceptance is a durable store commit only; optional pollers
    may observe accepted jobs without executing them in-request.

    Optional ``registry`` enables ``/v1/registry`` admin routes (CP2). Use
    :meth:`with_registry_definitions` or ``definitions_backend="registry"`` so
    ``/v1/definitions*`` read/write through registry revisions without changing
    route paths or operationIds.

    Optional ``durable_work`` enables ``/v1/durable/*`` host routes (CP3) and
    dual-writes durable accept on submit when fingerprints are present.
    """

    authorizer: Authorizer
    definitions: DefinitionRepository
    submissions: SubmissionStore
    events: EventStore
    context_factory: ContextFactory
    principal_dependency: PrincipalDependency = field(default=principal_from_header)
    # Validate/plan profile (default development for CP1 Experimental preview).
    profile: Any = "development"
    # Optional CP2 history store; when set, schema/reliability routes read it.
    history_store: HistoryStore | None = None
    # Seeded schema observation ids; empty → ack always 404 after authz.
    # Used when history_store is not injected (CP1 stub compatibility).
    known_observation_ids: set[str] = field(default_factory=set)
    # Optional CP2 registry provider for /v1/registry admin routes.
    registry: RegistryProvider | None = None
    # Optional CP3 durable work store for /v1/durable/* host routes.
    durable_work: DurableWorkStore | None = None
    # Optional 0.47 schedule store for /v1/schedules* (501 without it).
    schedule_store: Any = None
    # Optional CP4 governance providers.
    policy: PolicyProvider | None = None
    approvals: ApprovalStore | None = None
    quotas: QuotaProvider | None = None
    erasure: ErasureStore | None = None
    audit: AuditEvidenceStore | None = None
    attestations: AttestationStore | None = None
    objectives: ObjectiveStore | None = None
    title: str = "ETLantic Control Plane"
    version: str = __version__
    _router: APIRouter | None = field(default=None, init=False, repr=False)
    _context_dependency: Callable[..., Any] | None = field(
        default=None, init=False, repr=False
    )

    @classmethod
    def with_registry_definitions(
        cls,
        *,
        authorizer: Authorizer,
        registry: RegistryProvider,
        submissions: SubmissionStore,
        events: EventStore,
        context_factory: ContextFactory,
        principal_dependency: PrincipalDependency | None = None,
        **kwargs: Any,
    ) -> ETLanticAPI:
        """Build an API whose ``/v1/definitions*`` use registry-backed storage."""
        return cls(
            authorizer=authorizer,
            definitions=RegistryDefinitionRepository(registry),
            submissions=submissions,
            events=events,
            context_factory=context_factory,
            principal_dependency=principal_dependency or principal_from_header,
            registry=registry,
            **kwargs,
        )

    @property
    def context_dependency(self) -> Callable[..., Any]:
        if self._context_dependency is None:
            self._context_dependency = make_context_dependency(self)
        return self._context_dependency

    @property
    def router(self) -> APIRouter:
        if self._router is None:
            self._router = build_control_plane_router(self)
        return self._router

    def stores_ready(self) -> bool:
        return all(
            x is not None
            for x in (
                self.authorizer,
                self.definitions,
                self.submissions,
                self.events,
                self.context_factory,
            )
        )


def include_router(
    app: FastAPI,
    api: ETLanticAPI,
    *,
    prefix: str = "",
) -> None:
    """Embed the control-plane router without owning host lifecycle.

    Does **not** install lifespan hooks, middleware, or exception handlers.
    Host applications should register Problem Details handlers and lifespan
    themselves when desired.
    """
    app.state.etlantic_api = api
    app.include_router(api.router, prefix=prefix)


def create_app(
    api: ETLanticAPI | None = None,
    *,
    authorizer: Authorizer | None = None,
    definitions: DefinitionRepository | None = None,
    submissions: SubmissionStore | None = None,
    events: EventStore | None = None,
    context_factory: ContextFactory | None = None,
    principal_dependency: PrincipalDependency | None = None,
    registry: RegistryProvider | None = None,
    durable_work: DurableWorkStore | None = None,
    schedule_store: Any = None,
    policy: PolicyProvider | None = None,
    approvals: ApprovalStore | None = None,
    quotas: QuotaProvider | None = None,
    erasure: ErasureStore | None = None,
    audit: AuditEvidenceStore | None = None,
    attestations: AttestationStore | None = None,
    objectives: ObjectiveStore | None = None,
    definitions_backend: str | None = None,
    title: str | None = None,
    version: str | None = None,
    install_handlers: bool = True,
    with_lifespan: bool = True,
) -> FastAPI:
    """Standalone control-plane app factory.

    Optional lifespan wires injected stores onto ``app.state`` and verifies
    readiness. It does not start BackgroundTasks or execute pipelines.

    ``definitions_backend="registry"`` requires ``registry`` and wraps it as
    :class:`RegistryDefinitionRepository` for stable ``/v1/definitions*``
    routes. Default keeps an injected ``definitions`` store (callers must pass
    one when not using the registry backend).
    """
    if api is None:
        if authorizer is None or submissions is None or events is None:
            raise TypeError(
                "create_app requires an ETLanticAPI instance or all of "
                "authorizer, submissions, and events "
                "(plus definitions, or registry with definitions_backend='registry')"
            )
        if definitions is None:
            if definitions_backend == "registry":
                if registry is None:
                    raise TypeError(
                        "definitions_backend='registry' requires a registry provider"
                    )
                definitions = RegistryDefinitionRepository(registry)
            else:
                # Preserve prior required-args behavior for non-registry hosts.
                raise TypeError(
                    "create_app requires an ETLanticAPI instance or all of "
                    "authorizer, definitions, submissions, and events"
                )
        elif definitions_backend == "registry":
            if registry is None:
                raise TypeError(
                    "definitions_backend='registry' requires a registry provider"
                )
            definitions = RegistryDefinitionRepository(registry)
        api = ETLanticAPI(
            authorizer=authorizer,
            definitions=definitions,
            submissions=submissions,
            events=events,
            context_factory=context_factory
            or static_context_factory(tenant_id="default", workspace_id="default"),
            principal_dependency=principal_dependency or principal_from_header,
            registry=registry,
            durable_work=durable_work,
            schedule_store=schedule_store,
            policy=policy,
            approvals=approvals,
            quotas=quotas,
            erasure=erasure,
            audit=audit,
            attestations=attestations,
            objectives=objectives,
            title=title or "ETLantic Control Plane",
            version=version or __version__,
        )
    else:
        if title is not None:
            api.title = title
        if version is not None:
            api.version = version
        if principal_dependency is not None:
            api.principal_dependency = principal_dependency
        if context_factory is not None:
            api.context_factory = context_factory
        if registry is not None:
            api.registry = registry
        if durable_work is not None:
            api.durable_work = durable_work
        if schedule_store is not None:
            api.schedule_store = schedule_store
        if policy is not None:
            api.policy = policy
        if approvals is not None:
            api.approvals = approvals
        if quotas is not None:
            api.quotas = quotas
        if erasure is not None:
            api.erasure = erasure
        if audit is not None:
            api.audit = audit
        if attestations is not None:
            api.attestations = attestations
        if objectives is not None:
            api.objectives = objectives
        if definitions_backend == "registry":
            if api.registry is None:
                raise TypeError(
                    "definitions_backend='registry' requires a registry provider"
                )
            api.definitions = RegistryDefinitionRepository(api.registry)

    lifespan = None
    if with_lifespan:

        @asynccontextmanager
        async def _lifespan(app: FastAPI):
            app.state.etlantic_api = api
            app.state.authorizer = api.authorizer
            app.state.definitions = api.definitions
            app.state.submissions = api.submissions
            app.state.events = api.events
            app.state.registry = api.registry
            app.state.durable_work = api.durable_work
            app.state.schedule_store = getattr(api, "schedule_store", None)
            app.state.policy = api.policy
            app.state.approvals = api.approvals
            app.state.quotas = api.quotas
            app.state.erasure = api.erasure
            app.state.audit = api.audit
            app.state.attestations = api.attestations
            app.state.objectives = api.objectives
            # Ready signal only — no BackgroundTasks worker started here.
            app.state.control_plane_ready = api.stores_ready()
            yield
            app.state.control_plane_ready = False

        lifespan = _lifespan

    app = FastAPI(title=api.title, version=api.version, lifespan=lifespan)
    app.state.etlantic_api = api
    if install_handlers:
        install_exception_handlers(app)
    include_router(app, api)
    return app


__all__ = ["ETLanticAPI", "create_app", "include_router"]
