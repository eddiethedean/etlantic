# Control plane API (CP1)

> **Status: Available in ETLantic 0.39.0** (incubation). **CP1 ≠ production
> multi-tenant isolation** — that claim remains **0.43**.

Short hub for the provisional `etlantic.control_plane` surface and optional
FastAPI adapter. Prefer this over digging through implementation plans when
embedding CP1.

## Guide

| Topic | Where |
|---|---|
| Adopter how-to (embed FastAPI) | [Control plane (CP1)](../06_EXECUTION/CONTROL_PLANE.md) |
| What shipped / non-claims | [What's new in 0.39](../01_GETTING_STARTED/WHATS_NEW_0_39.md) |
| Identity freeze | [ADR-016](../11_DEVELOPMENT/adr/ADR-016-CONTROL-PLANE-IDENTITY.md) |
| Wire schema ids | [Wire schema ranges](WIRE_SCHEMA_RANGES.md) |
| FastAPI dual surface | [`etlantic-fastapi` README](https://github.com/eddiethedean/etlantic/blob/main/packages/etlantic-fastapi/README.md) · [Optional packages](OPTIONAL_PACKAGES.md) |
| Program sequencing | [Multi-tenant control plane plan](../11_DEVELOPMENT/MULTI_TENANT_CONTROL_PLANE_PLAN.md) |

## Core import (`etl.control_plane`)

```python
import etlantic as etl

# Models / protocols (provisional CP1)
from etlantic.control_plane import (
    ControlPlaneContext,
    Principal,
    MemoryAuthorizer,
    MemoryDefinitionRepository,
    MemorySubmissionStore,
    MemoryEventStore,
)
```

Lazy namespace: `etl.control_plane` (same symbols). Core stays free of FastAPI /
SQLModel imports. Optional SQLModel reference stores live under
`etlantic_sqlmodel.control_plane`.

## HTTP embed (`etlantic-fastapi`)

| Surface | Entry | Role |
|---|---|---|
| **CP1** | `ETLanticAPI`, `include_router`, `create_app` | Authz’d durable-accept API + `GET /health` / `GET /ready` |
| **Non-CP** | `create_reference_app` | Thin sync authoring demo only |

Pin: `pip install 'etlantic-fastapi==0.39.0'` (match `etlantic==0.39.0`).

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
