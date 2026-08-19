# Control plane (CP1)

> **Status: Available in ETLantic 0.48.0 (incubation).** Embeddable HTTP control
> plane via `etlantic-fastapi`. CP1 is **not** production multi-tenant isolation
> (reserved for **0.43**).

## What CP1 is / is not

| CP1 is | CP1 is not |
|---|---|
| Embeddable FastAPI routes with injected stores | A hosted SaaS or multi-tenant GA product |
| Authz before lookup, opaque 404 across tenants | Path/header tenant strings as authority |
| Durable `202` accept + scoped idempotency | In-request pipeline execution |
| Resumable SSE with fail-closed `410` | Unbounded long-poll or silent cursor skip |
| Composition root for host authn | Bundled IdP / OAuth client |

`ControlPlaneContext` is **server-derived** after authentication and membership
mapping. See [ADR-016](../11_DEVELOPMENT/adr/ADR-016-CONTROL-PLANE-IDENTITY.md).

## Install

```bash
python -m pip install 'etlantic-fastapi==0.48.0'
# or: python -m pip install 'etlantic[fastapi]==0.48.0'
```

Pin the same minor as core (`etlantic==0.48.0`). Package README:
[`packages/etlantic-fastapi`](https://github.com/eddiethedean/etlantic/tree/main/packages/etlantic-fastapi).

## Embed: `include_router` vs `create_app`

```python
from etlantic.control_plane import (
    MemoryAuthorizer,
    MemoryDefinitionRepository,
    MemoryEventStore,
    MemorySubmissionStore,
)
from etlantic_fastapi import (
    ETLanticAPI,
    create_app,
    include_router,
    membership_context_factory,
    principal_from_header,
)

api = ETLanticAPI(
    authorizer=MemoryAuthorizer(),
    definitions=MemoryDefinitionRepository(),
    submissions=MemorySubmissionStore(),
    events=MemoryEventStore(),
    context_factory=membership_context_factory(
        {"alice": ("tenant-a", "ws-1", "development", "default")}
    ),
    principal_dependency=principal_from_header,
)

# Standalone — installs Problem Details handlers + optional lifespan
app = create_app(api)

# Or embed into a host app (host must register Problem Details handlers):
# from fastapi import FastAPI
# host = FastAPI()
# include_router(host, api)
```

Use durable SQLModel-backed stores (`etlantic-sqlmodel`) when you need
process-restart survival; memory stores are for local evaluation only.

## Durable work (CP3)

Inject an optional `DurableWorkStore` for accept/outbox, leases/fencing, and
host recovery routes. Memory is for local evaluation; use
`SQLModelDurableWorkStore` (`etlantic-sqlmodel`, migration `002_durable_cp3`)
when you need process-restart survival.

```python
from etlantic.control_plane import MemoryDurableWorkStore

api = ETLanticAPI(
    authorizer=MemoryAuthorizer(),
    definitions=MemoryDefinitionRepository(),
    submissions=MemorySubmissionStore(),
    events=MemoryEventStore(),
    durable_work=MemoryDurableWorkStore(),
    context_factory=membership_context_factory(
        {"alice": ("tenant-a", "ws-1", "development", "default")}
    ),
    principal_dependency=principal_from_header,
)
```

CP1 submit paths stay stable. With `durable_work` present, submit dual-writes a
durable accept (plan/revision fingerprints only). Host ops use `/v1/durable/*`
(authz before lookup). See [Durable work](DURABLE_WORK.md) and
[ADR-018](../11_DEVELOPMENT/adr/ADR-018-DURABLE-SUBMISSION-AND-STATE.md).
**CP3 ≠ production multi-tenant** (**0.43**).

## Authz before lookup (non-enumeration)

Authorization runs **before** existence checks. Cross-tenant or unknown
resources map to opaque **404**; in-scope action deny maps to **403**. Clients
must not infer existence from status codes or list counts across tenants.

## Durable submit (`202`) and idempotency

`POST /v1/definitions/{id}/runs` returns **202** only after durable acceptance
in the injected submission store. Do **not** schedule heavy pipeline work with
FastAPI `BackgroundTasks`. Optional worker pollers observe accepted jobs outside
the request.

Send `Idempotency-Key`. The effective store key is server-scoped:

```text
(tenant_id, workspace_id, principal_subject, operation, idempotency_key)
```

Same scoped key + same request fingerprint → original accept receipt. Same key
+ different fingerprint → conflict.

## SSE resume / `410`

`GET /v1/runs/{run_id}/events` streams `etlantic.control_plane.event/1`
envelopes. Resume with `cursor` query or `Last-Event-ID` (query wins). Unknown
or expired cursors fail closed with **HTTP 410** (`PMCP410`,
`extensions.hint = omit_cursor_or_last_event_id`). Reconnect **without** a
cursor to replay from the start. Default `follow=false`; `follow=true` has a
hard poll/time cap.

## Health vs ready

| Endpoint | Role | Failure |
|---|---|---|
| `GET /health` | Liveness (process up) | Always **200** |
| `GET /ready` | Readiness (injected stores present) | **503** `status=not_ready` |

## Landing-zone watch submitter

Continuous directory watching is a **submitter outside core**, not an Extract
kind. See [Landing zone](LANDING_ZONE.md) and
`examples/landing_zone_watch_submitter.py`.

## Non-CP reference surface

`create_reference_app` is a **synchronous** `AuthoringService` demo only. It is
not the control plane. Prefer this page and
[Application integration](../08_VISUALIZATION/APPLICATION_INTEGRATION.md) for the
dual-surface split; API symbols:
[etlantic-fastapi reference](../10_REFERENCE/api_optional/etlantic_fastapi.md).

## Related

- [Control plane API (CP1–CP3)](../10_REFERENCE/CONTROL_PLANE_API.md) — models, PMCP errors, `/v1/durable/*`
- [Durable work (CP3)](DURABLE_WORK.md)
- [ADR-016: Control-plane identity](../11_DEVELOPMENT/adr/ADR-016-CONTROL-PLANE-IDENTITY.md)
- [ADR-018: Durable submission and state](../11_DEVELOPMENT/adr/ADR-018-DURABLE-SUBMISSION-AND-STATE.md)
- [Deployment](DEPLOYMENT.md)
- [etlantic-fastapi package README](https://github.com/eddiethedean/etlantic/blob/main/packages/etlantic-fastapi/README.md)
