---
status: available
since: "0.43.0"
current_minor: "0.46"
audience: developer
---

# etlantic-fastapi API

> **Status: Available in ETLantic 0.46.0.** Dual surface: **CP1 control plane**
> (`ETLanticAPI`, `include_router`, `create_app`) is primary; `create_reference_app`
> is a non-CP sync demo. Hub: [Optional packages API](../API_OPTIONAL_PACKAGES.md).
> Adopter guide: [Control plane (CP1)](../../06_EXECUTION/CONTROL_PLANE.md).

## Setup

```bash
pip install 'etlantic-fastapi==0.46.0'
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

## Public API

::: etlantic_fastapi
    options:
      show_source: false
      show_submodules: true
      members_order: source
      filters:
        - "!^_"
