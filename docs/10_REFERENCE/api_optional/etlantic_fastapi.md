---
status: available
since: "0.43.0"
current_minor: "0.60"
audience: developer
---

# etlantic-fastapi API

> **Status: ETLantic core 0.60.0 is a Beta candidate; 0.59.x remains the published support line.** Dual surface: **CP1 control plane**
> (`ETLanticAPI`, `include_router`, `create_app`) is primary; `create_reference_app`
> is a non-CP sync demo. Hub: [Optional packages API](../API_OPTIONAL_PACKAGES.md).
> Adopter guide: [Embeddable HTTP API](../../06_EXECUTION/CONTROL_PLANE.md).

## Setup

```bash
pip install 'etlantic-fastapi==0.60.0'
```

```python
import etlantic_fastapi
print(etlantic_fastapi.__version__)
```

## Surfaces

| Surface | Entry points | Role |
|---|---|---|
| **CP1 (primary)** | `ETLanticAPI`, `include_router`, `create_app` | Embeddable, authz’d, durable `202` accept + SSE |
| **Reference (non-CP)** | `create_reference_app` | Sync `AuthoringService` demo only |

CP1 is incubation — **not** production multi-tenant GA (**0.43**). Do not use
FastAPI `BackgroundTasks` for heavy pipeline work. See
[ADR-016](../../11_DEVELOPMENT/adr/ADR-016-CONTROL-PLANE-IDENTITY.md) and the
[package README](https://github.com/eddiethedean/etlantic/blob/main/packages/etlantic-fastapi/README.md).

## Failure modes

| Topic | Behavior |
|---|---|
| Cross-tenant / unknown resource | Opaque **404** after authz (non-enumeration) |
| In-scope action deny | **403** |
| SSE unknown / expired cursor | **410** (`PMCP410`); omit cursor to replay |
| Ready probe without stores | **503** `status=not_ready` (`/health` stays **200**) |
| Reference app | Sync only; not a control plane |

## Managed Prefect dispatch reconciliation

When CP1 is composed with a managed execution service,
`POST /v1/dispatches/{submission_id}/reconcile` exposes the operator recovery
path for a dispatch that exhausted its automatic pre-execution generations.
The caller needs `execution.dispatch.reconcile` for the accepted work's
tenant and workspace and must send the exact `expected_generation`,
`expected_flow_run_id`, and a bounded `evidence` note. A stale generation or run
ID returns **409**; an out-of-scope request remains an opaque **404**. The
service stores only a digest of the redacted evidence note, records the acting
principal in durable dispatch history, and emits an audit event. The response
contains the resulting dispatch projection, not the note.

## Public API

::: etlantic_fastapi
    options:
      show_source: false
      show_submodules: true
      members_order: source
      filters:
        - "!^_"
