# FastAPI Integration Plan

Pipelantic's FastAPI integration exposes typed pipeline operations through an
ordinary FastAPI application without making HTTP part of pipeline semantics.

The integration belongs in a separate `pipelantic-fastapi` package. Pipelantic
core remains usable without FastAPI, Starlette, an ASGI server, or an HTTP
deployment.

## Product Goals

The integration should let applications:

- expose pipeline discovery, validation, planning, submission, status,
  cancellation, reports, artifacts, and lineage as typed HTTP operations;
- reuse Pipelantic and Pydantic models as request and response schemas;
- generate an OpenAPI 3.1 description and client SDKs;
- stream run events through Server-Sent Events (SSE) and optionally WebSockets;
- map FastAPI lifespan, middleware, dependencies, security, callbacks, and
  webhooks onto explicit Pipelantic integration boundaries;
- embed selected Pipelantic routers into an existing FastAPI application;
- deploy a standalone control API when desired.

It should not:

- execute heavy pipelines in FastAPI `BackgroundTasks`;
- treat the API worker process as a durable scheduler;
- expose arbitrary Python imports or unrestricted plugin installation;
- return secret values, live backend objects, or unbounded data artifacts;
- make HTTP routes the source of truth for pipeline definitions.

## Package Boundary

```text
pipelantic
    typed models, plans, run requests, reports, events
        ▲
        │
pipelantic-fastapi
    routers, auth adapters, OpenAPI, streaming, request context
        ▲
        │
FastAPI / Starlette / ASGI server
```

Candidate installation:

```bash
pip install pipelantic-fastapi
```

## Application Factory

```python
from fastapi import FastAPI
from pipelantic_fastapi import PipelanticAPI

app = FastAPI()

pipelines = PipelanticAPI(
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
| `GET /pipelines` | List visible pipeline descriptors |
| `GET /pipelines/{pipeline_id}` | Inspect metadata, ports, contracts, and capabilities |
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

## FastAPI Mechanism Mapping

### Lifespan

FastAPI lifespan should initialize and close integration-wide components:

- registry snapshots;
- run and report stores;
- submission clients;
- event-bus connections;
- policy and identity adapters;
- observability exporters.

Pipeline runtime lifespan remains owned by Pipelantic. The API lifespan manages
the control-plane adapter, not every individual run.

### Dependencies

FastAPI dependencies should supply request-scoped control-plane concerns:

- authenticated principal;
- tenant and workspace;
- authorization policy;
- correlation and idempotency keys;
- registry view;
- run-store client;
- rate-limit decision.

Pipelantic Resource Providers remain runtime dependencies for pipeline work.
FastAPI's dependency graph must not become the pipeline resource graph.

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

Pipelantic middleware continues to wrap planning and execution operations. The
two middleware systems may exchange context but have different scopes.

### OpenAPI Callbacks and Webhooks

Pipelantic outbound event declarations can generate OpenAPI callbacks or
webhook descriptions for:

- run completed;
- run failed;
- approval requested;
- validation gate rejected;
- artifact published.

The OpenAPI document describes payloads and destinations; Pipelantic's outbound
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

## OpenAPI and Client Generation

Pipelantic should produce stable operation identifiers and reusable schemas so
OpenAPI client generators create understandable methods.

OpenAPI extensions may link:

- pipeline, contract, plan, and report schema versions;
- supported run intents;
- idempotency behavior;
- authorization scopes;
- event-stream and callback schemas.

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

Never allow a caller to select an arbitrary plugin, secret provider, import
path, filesystem path, or network destination merely because it appears in a
request body.

## Idempotency and Concurrency

Run submission should support an idempotency key scoped to the caller,
workspace, pipeline, and normalized request. Duplicate submissions return the
existing run when policy permits.

Optimistic concurrency tokens should protect mutable operations such as
cancellation, approval, annotations, and promotion.

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
- idempotent submission;
- cancellation races;
- SSE resume and disconnect behavior;
- multiple worker simulations;
- request size, rate, and timeout limits;
- absence of secrets from errors and schemas;
- compatibility between API and `PipelineRunReport` schema versions.

## Dependency Strategy

`pipelantic-fastapi` should depend on:

- `fastapi`;
- Pipelantic core;
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

> FastAPI exposes Pipelantic's typed control plane. It does not become the
> pipeline runtime, scheduler, or source of pipeline semantics.
