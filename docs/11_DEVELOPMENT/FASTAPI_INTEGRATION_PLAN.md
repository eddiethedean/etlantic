# FastAPI Integration Plan

> **Status: graduated control-plane FastAPI host in ETLantic 0.43 (CP-GA);
> first-class planned control-plane integration delivered for Supported
> profiles.** CP1–CP4 remain foundations (**CPn alone ≠ GA**). Production
> multi-tenant is Available for `isolated-deployment` / `dedicated-schema`;
> `shared-service` remains Experimental; community **non-SLA**.
>
> **Current 0.46 boundary:** Optional `etlantic-fastapi` exposes `ETLanticAPI`
> (control-plane host) plus thin `create_reference_app` (authoring demo only).
> Phase 0.47 **plans** separately supervised scheduler and execution-host service
> roles behind this gateway ([ADR-023](adr/ADR-023-SCHEDULER-SERVICE-AND-FEDERATION.md),
> [IMPLEMENTATION_PLAN_0_47](IMPLEMENTATION_PLAN_0_47.md)); it does not run
> either role in an ASGI worker, and those routes are **not Available**.
> Continuous directory watchers are not in core. Reliability stubs remain
> `experimental: true` unless a history store is injected.
>
> **Authority:** The
> [optional-packages reference](../10_REFERENCE/OPTIONAL_PACKAGES.md) defines
> the shipped adapter. This plan and the
> [control-plane plan](MULTI_TENANT_CONTROL_PLANE_PLAN.md) own graduation
> evidence. See [EXIT_GATE_0_43](EXIT_GATE_0_43.md) and the
> [Planning Hub](PLAN_INDEX.md).
>
> **Review trigger:** Update when the shipped adapter gains durable service
> scope or any CP1–CP-GA gate changes state.

ETLantic's FastAPI integration exposes typed pipeline operations through an
ordinary FastAPI application without making HTTP part of pipeline semantics.

ETLantic 0.24 first establishes the authoring-complete `PipelineDefinition`,
canonical `etlantic.pipeline/1` JSON, component catalog, immutable edit
operations, OpenAPI-compatible service models, and a thin reference adapter.
See [Programmatic Authoring in 0.24](PROGRAMMATIC_AUTHORING_0_24.md).

This plan builds the control API portion of the
[Multi-Tenant Control Plane Plan](MULTI_TENANT_CONTROL_PLANE_PLAN.md). It adds
durable registry, submission, event, persistence, authorization, and deployment
integration; it does not redefine the canonical pipeline document.

The integration belongs in a separate `etlantic-fastapi` package. ETLantic
core remains usable without FastAPI, Starlette, an ASGI server, or an HTTP
deployment.

## Product Goals

The integration should let applications:

- expose pipeline discovery, validation, planning, submission, status,
  cancellation, reports, artifacts, and lineage as typed HTTP operations;
- expose delivery-objective evaluation/history/acknowledgement, authorized
  notification-route administration, governed erasure request/plan/approval/
  execution/status/reconciliation, and payload-free dynamic/DLQ/schema-registry
  evidence as typed operations when their capability phases are installed;
- reuse ETLantic and Pydantic models as request and response schemas;
- generate an OpenAPI 3.1 description and client SDKs;
- stream run events through Server-Sent Events (SSE) and optionally WebSockets;
- map FastAPI lifespan, middleware, dependencies, security, callbacks, and
  webhooks onto explicit ETLantic integration boundaries;
- carry an immutable, server-derived tenant/workspace/environment context
  through every authorized operation;
- expose deny-by-default authorization, quota, idempotency, concurrency, and
  non-enumeration behavior consistently;
- embed selected ETLantic routers into an existing FastAPI application;
- deploy a standalone control API when desired.

It should not:

- execute heavy pipelines in FastAPI `BackgroundTasks`;
- treat the API worker process as a durable scheduler;
- expose arbitrary Python imports or unrestricted plugin installation;
- return secret values, live backend objects, or unbounded data artifacts;
- make HTTP routes the source of truth for pipeline definitions.

An optional `etlantic-sqlmodel` integration may provide typed reference
implementations for registry, run, report, event, observation, objective,
notification-delivery, erasure, approval, and state stores. FastAPI and SQLModel
remain adapters around ETLantic's public provider protocols.

## Package Boundary

```text
etlantic
    typed models, plans, run requests, reports, events
        ▲
        │
etlantic-fastapi
    routers, auth adapters, OpenAPI, streaming, request context
        ▲
        │
FastAPI / Starlette / ASGI server
```

Candidate installation:

```bash
pip install etlantic-fastapi
```

## Application Factory

```python
from fastapi import FastAPI
from etlantic_fastapi import ETLanticAPI

app = FastAPI()

pipelines = ETLanticAPI(
    registry=registry,
    run_store=run_store,
    submitter=submitter,
    policy=policy,
)

app.include_router(pipelines.router, prefix="/pipelines")
```

A standalone factory may be provided:

```python
app = pipelines.create_app(
    title="Customer Data Platform",
    version="1.0",
)
```

## Initial HTTP Surface

| Operation | Purpose |
|---|---|
| `GET /catalog` | Discover authorized authoring components and capabilities |
| `GET /pipelines` | List visible pipeline definitions |
| `POST /pipelines` | Create a canonical pipeline definition |
| `GET /pipelines/{pipeline_id}` | Retrieve metadata and the authorized definition |
| `PATCH /pipelines/{pipeline_id}` | Apply versioned immutable edit commands |
| `POST /pipelines/{pipeline_id}/validate` | Validate a pipeline and profile |
| `POST /pipelines/{pipeline_id}/plans` | Produce a secret-free `PipelinePlan` |
| `POST /pipelines/{pipeline_id}/runs` | Submit a durable `RunRequest` |
| `GET /runs/{run_id}` | Read normalized status |
| `POST /runs/{run_id}/cancel` | Request cancellation |
| `GET /runs/{run_id}/report` | Retrieve `PipelineRunReport` |
| `GET /runs/{run_id}/events` | Stream lifecycle events with SSE |
| `GET /runs/{run_id}/artifacts` | List authorized artifact metadata |
| `GET /pipelines/{pipeline_id}/lineage` | Retrieve logical lineage |

The default API returns metadata and references, not arbitrary dataset contents.
Artifact download or preview requires a separate bounded, authorized policy.
Definition mutations require optimistic concurrency tokens, and submission
operations require caller-scoped idempotency keys.

Ordinary tenant routes are workspace-scoped. Tenant membership is derived from
the authenticated principal and trusted server-side configuration; a tenant ID
in a path, header, or body never grants authority. Cross-tenant administration
uses separate routes, credentials, policy actions, and audit events.

## FastAPI Mechanism Mapping

### Lifespan

FastAPI lifespan should initialize and close integration-wide components:

- registry snapshots;
- run and report stores;
- submission clients;
- event-bus connections;
- policy and identity adapters;
- observability exporters.

Pipeline runtime lifespan remains owned by ETLantic. The API lifespan manages
the control-plane adapter, not every individual run.

When SQLModel persistence is selected, lifespan may create engines and session
factories and verify migration state. It must not create or migrate production
tables automatically.

### Dependencies

FastAPI dependencies should supply request-scoped control-plane concerns:

- authenticated principal;
- tenant and workspace;
- authorization policy;
- correlation and idempotency keys;
- registry view;
- run-store client;
- rate-limit decision.

ETLantic Resource Providers remain runtime dependencies for pipeline work.
FastAPI's dependency graph must not become the pipeline resource graph.

An optional SQLModel dependency may yield a request-scoped control-plane
session. That session is available only to API repositories and must not be
passed to transformations, providers used by pipeline code, or remote workers.

Dependency overrides are valuable for tests and should be documented in the
integration conformance suite.

### Middleware

FastAPI or Starlette middleware should cover HTTP concerns:

- correlation identifiers;
- authentication context propagation;
- request timing;
- access logging;
- trusted hosts and proxy headers;
- CORS where explicitly required;
- request size and timeout limits;
- rate limiting through an approved integration;
- security headers.

ETLantic middleware continues to wrap planning and execution operations. The
two middleware systems may exchange context but have different scopes.

### OpenAPI Callbacks and Webhooks

ETLantic outbound event declarations can generate OpenAPI callbacks or
webhook descriptions for:

- run completed;
- run failed;
- approval requested;
- validation gate rejected;
- artifact published.

The OpenAPI document describes payloads and destinations; ETLantic's outbound
event provider performs delivery under network and secret policy.

## Run Submission

`POST /runs` should return `202 Accepted` after a durable submitter accepts the
request:

```json
{
  "run_id": "run_01J...",
  "status": "accepted",
  "status_url": "/runs/run_01J...",
  "events_url": "/runs/run_01J.../events"
}
```

Small local demonstrations may use an in-process submitter. Production
deployments must use a durable queue, orchestrator, or remote runtime adapter.
FastAPI `BackgroundTasks` is not a durable execution mechanism and should be
limited to small response-follow-up work.

## Event Streaming

SSE should be the first streaming interface because run events primarily flow
from server to client and SSE works naturally with HTTP infrastructure.

WebSockets may be added for interactive control, bidirectional debugging, or
notebook-style sessions. WebSocket authorization must be revalidated for
long-lived connections, and slow clients must not block runtime event
production.

Every stream needs:

- bounded buffers;
- resumable event identifiers;
- heartbeat and disconnect handling;
- authorization-aware filtering;
- terminal-event semantics;
- value and secret redaction.

The stream cursor and every emitted event are tenant-scoped. Authorization is
revalidated on resume and after relevant membership or policy changes.

## OpenAPI and Client Generation

ETLantic should produce stable operation identifiers and reusable schemas so
OpenAPI client generators create understandable methods.

OpenAPI extensions may link:

- pipeline, contract, plan, and report schema versions;
- supported run intents;
- idempotency behavior;
- authorization scopes;
- event-stream and callback schemas.
- delivery-objective, breach/recovery, notification-delivery, erasure,
  dynamic-control, dead-letter, redrive, and schema-registry evidence schemas.

Generated clients are delivery artifacts, not hand-maintained source. FastAPI
documents OpenAPI-based generation for multiple languages, including typed
TypeScript clients.

## Authentication and Authorization

The integration should support adapters for:

- OAuth2/OIDC bearer tokens;
- service-to-service workload identity;
- API gateway identity headers only from trusted proxies;
- application-defined FastAPI dependencies.

Authorization decisions should include:

- principal;
- tenant/workspace;
- pipeline and profile;
- run intent and selection;
- parameter and binding overrides;
- artifact access;
- cancellation and approval actions.
- objective acknowledgement/route administration and every erasure planning,
  approval, execution, retry, reconciliation, and closure action.

Authorization is performed before resource lookup, pagination, serialization,
or cursor creation. List and search endpoints must not reveal unauthorized
counts, identifiers, timing distinctions, or cursor positions.

Never allow a caller to select an arbitrary plugin, secret provider, import
path, filesystem path, or network destination merely because it appears in a
request body.

## Idempotency and Concurrency

Run submission should support an idempotency key scoped to the caller,
workspace, pipeline, and normalized request. Duplicate submissions return the
existing run when policy permits.

Optimistic concurrency tokens should protect mutable operations such as
cancellation, objective acknowledgement, notification-route changes, erasure
approval/retry/closure, approval, annotations, and promotion.

## Multi-Worker Deployment

FastAPI applications may run multiple processes or replicas. Therefore:

- registry and run state cannot rely on process-local globals;
- submission must be durable before returning success;
- event streams need a shared broker or resumable store;
- rate limits and idempotency require shared state;
- one worker cannot assume it will receive later requests for the same run.

## Testing

The integration suite should cover:

- FastAPI dependency overrides;
- lifespan startup and failure;
- OpenAPI schema and stable operation IDs;
- authentication and tenant isolation;
- two-tenant and two-workspace matrices for every operation;
- non-enumerating list, lookup, search, cursor, and event-stream behavior;
- idempotent submission;
- cancellation races;
- deadline clock/calendar/restart and notification deduplication/routing races;
- erasure authorization, legal-hold, idempotency, partial-provider,
  reconciliation, and false-completion cases;
- dynamic-child pagination/non-enumeration and payload-free DLQ/redrive/
  schema-registry evidence responses;
- SSE resume and disconnect behavior;
- multiple worker simulations;
- request size, rate, and timeout limits;
- absence of secrets from errors and schemas;
- compatibility between API and `PipelineRunReport` schema versions.

## Graduation Boundary

The shipped thin adapter remains a reference integration. A production
control-API claim is allowed only when the integrated CP-GA gate in the
[Multi-Tenant Control Plane Plan](MULTI_TENANT_CONTROL_PLANE_PLAN.md) passes,
including:

- SDK, CLI, and HTTP semantic parity for every supported operation;
- deny-by-default authorization and non-enumerating tenant isolation;
- durable submission, idempotency, event resume, cancellation, and recovery
  across process and worker failure;
- bounded requests, streams, queries, diagnostics, plans, reports, and
  artifacts with no resolved secrets or source rows;
- compatible OpenAPI and wire-schema evolution with generated-client tests;
- deployment, migration, backup, restore, rollback, and incident runbooks.
- delivery-objective and erasure action parity with durable, scoped,
  non-enumerating, redacted audit evidence.

An application factory, generated OpenAPI document, or passing single-process
test suite is not sufficient for graduation.

## Dependency Strategy

`etlantic-fastapi` should depend on:

- `fastapi`;
- ETLantic core;
- optional `uvicorn` only for standalone serving extras;
- optional SSE, authentication, and rate-limit packages selected after focused
  evaluation.

The package should use FastAPI and Starlette public interfaces and avoid
depending on their internals.

## Primary References

- [FastAPI features and OpenAPI](https://fastapi.tiangolo.com/features/)
- [FastAPI lifespan events](https://fastapi.tiangolo.com/advanced/events/)
- [FastAPI middleware](https://fastapi.tiangolo.com/tutorial/middleware/)
- [FastAPI dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [FastAPI OpenAPI callbacks](https://fastapi.tiangolo.com/advanced/openapi-callbacks/)
- [FastAPI webhooks](https://fastapi.tiangolo.com/advanced/openapi-webhooks/)
- [FastAPI client generation](https://fastapi.tiangolo.com/advanced/generate-clients/)
- [FastAPI background-task caveat](https://fastapi.tiangolo.com/tutorial/background-tasks/#caveat)
- [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/)

## Key Principle

> FastAPI exposes ETLantic's typed control plane. It does not become the
> pipeline runtime, scheduler, tenant-isolation boundary for Python execution,
> or source of pipeline semantics.

The optional 0.47 scheduler/runner service preserves this principle: FastAPI is
the control surface, while dedicated scheduler and execution-host processes own
timer evaluation and pipeline execution against shared durable providers. That
split is frozen in [ADR-023](adr/ADR-023-SCHEDULER-SERVICE-AND-FEDERATION.md)
and is **not shipped**. Frozen HTTP names (when implemented later):
`/v1/definitions/{definition_id}/schedules`, `/v1/schedules/{schedule_id}`
(plus pause/resume/preview/trigger/firings), `/v1/scheduler/health`, and
`/v1/workers/health`.
