# Control plane API (CP1–CP3)

> **Status: Available in ETLantic 0.41.0** (incubation). **CP1–CP3 ≠ production
> multi-tenant isolation** — that claim remains **0.43**.

Short hub for the provisional `etlantic.control_plane` surface and optional
FastAPI adapter. Prefer this over digging through implementation plans when
embedding CP1–CP3.

## Guide

| Topic | Where |
|---|---|
| Adopter how-to (embed FastAPI) | [Control plane (CP1)](../06_EXECUTION/CONTROL_PLANE.md) |
| Durable work (CP3) | [Durable work](../06_EXECUTION/DURABLE_WORK.md) |
| What shipped / non-claims | [What's new in 0.41](../01_GETTING_STARTED/WHATS_NEW_0_41.md) |
| Identity freeze | [ADR-016](../11_DEVELOPMENT/adr/ADR-016-CONTROL-PLANE-IDENTITY.md) |
| Durable submission / state | [ADR-018](../11_DEVELOPMENT/adr/ADR-018-DURABLE-SUBMISSION-AND-STATE.md) |
| Wire schema ids | [Wire schema ranges](WIRE_SCHEMA_RANGES.md) |
| FastAPI dual surface | [`etlantic-fastapi` README](https://github.com/eddiethedean/etlantic/blob/main/packages/etlantic-fastapi/README.md) · [Optional packages](OPTIONAL_PACKAGES.md) |
| Program sequencing | [Multi-tenant control plane plan](../11_DEVELOPMENT/MULTI_TENANT_CONTROL_PLANE_PLAN.md) |

## Core import (`etl.control_plane`)

```python
import etlantic as etl

# Models / protocols (provisional CP1–CP3)
from etlantic.control_plane import (
    ControlPlaneContext,
    Principal,
    MemoryAuthorizer,
    MemoryDefinitionRepository,
    MemorySubmissionStore,
    MemoryEventStore,
    MemoryDurableWorkStore,
)
```

Lazy namespace: `etl.control_plane` (same symbols). Core stays free of FastAPI /
SQLModel imports. Optional SQLModel reference stores live under
`etlantic_sqlmodel.control_plane`.

## HTTP embed (`etlantic-fastapi`)

| Surface | Entry | Role |
|---|---|---|
| **CP1** | `ETLanticAPI`, `include_router`, `create_app` | Authz’d durable-accept API + `GET /health` / `GET /ready` |
| **CP2** | optional registry injection | Tenant / workspace / revision routes |
| **CP3** | optional `durable_work=` | `/v1/durable/*` host routes + submit dual-write |
| **Non-CP** | `create_reference_app` | Thin sync authoring demo only |

Pin: `pip install 'etlantic-fastapi==0.41.0'` (match `etlantic==0.41.0`).

When `durable_work` is set, `POST /v1/definitions/{id}/runs` dual-writes into
`DurableWorkStore.accept` with the same `submission_id` as the CP1 receipt.
`POST /v1/runs/{id}/cancel` also cancels the correlated durable submission.
Shipped host routes under `/v1/durable/*` (authz first):

| Route | Purpose |
|---|---|
| `GET /v1/durable/outbox` | Pending outbox drain |
| `POST /v1/durable/outbox/{outbox_id}/published` | Mark outbox published |
| `POST /v1/durable/submissions/{id}/cancel` | Cancel accepted work |
| `POST …/leases` · `…/leases/heartbeat` · `…/leases/release` | Lease acquire / heartbeat / release |
| `POST …/attempts` · `POST /v1/durable/attempts/{id}/finish` | Attempt start / finish |
| `POST /v1/durable/checkpoints/{id}/cas` | Namespaced checkpoint CAS |
| `POST …/replay` | Replay from optional checkpoint |
| `POST /v1/durable/previews` | Create TTL preview workspace |

Effects, repair plans, diagnose/explain, and shadow authorization remain
**SDK / DurableWorkStore protocol** surfaces in 0.41 — not separate FastAPI
routes. Core does **not** embed a broker or worker supervisor; adopters drain
the outbox with their own dispatcher.

## PMCP errors

Control-plane failures use Problem Details with `PMCP*` codes (not pipeline
`PMPIPE*`):

| Code | Typical meaning |
|---|---|
| `PMCP401` | Unauthenticated / missing principal |
| `PMCP403` | In-scope forbid (authorization deny) |
| `PMCP404` | Not found **or** cross-scope non-enumeration |
| `PMCP409` | Conflict (for example idempotency) |
| `PMCP410` | Gone (unknown/expired SSE cursor — reconnect without cursor) |

Wire schema: `etlantic.control_plane.error/1`. Authorization runs before
existence lookup; cross-tenant misses stay opaque **404**.

## Related

- [Python API overview](API_REFERENCE.md)
- [FAQ — What is CP1?](../01_GETTING_STARTED/FAQ.md#what-is-cp1)
- [Production readiness](../06_EXECUTION/PRODUCTION_READINESS.md)
