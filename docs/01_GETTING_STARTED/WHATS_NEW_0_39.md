# What's New in ETLantic 0.39

> **Status: Available in ETLantic 0.39.0.** CP1 control-plane incubation: typed
> identity, embeddable API, durable submission, resumable SSE, and landing-zone
> submitters outside core. **Beta** release — **CP1 is not production
> multi-tenant isolation** (that claim remains **0.43**).

## Highlights

- **Control-plane identity freeze** — `Principal`, `TenantRef`,
  `WorkspaceRef`, `EnvironmentRef`, `SecurityDomain`, and immutable
  `ControlPlaneContext` ([ADR-016](../11_DEVELOPMENT/adr/ADR-016-CONTROL-PLANE-IDENTITY.md))
- **Embeddable `etlantic-fastapi` CP1 surface** — `ETLanticAPI`,
  `include_router`, and `create_app` with stable OpenAPI 3.1 operation IDs
- **Authorization before lookup** — deny-by-default; consistent non-enumeration
  (`404` across unauthorized tenants/workspaces; `403` for in-scope forbid)
- **Durable `202 Accepted`** — accept receipt from an injected store; no
  `BackgroundTasks` for heavy pipeline work
- **Resumable SSE** — `GET /v1/runs/{run_id}/events` with
  `etlantic.control_plane.event/1` envelopes and scoped
  `etlantic.control_plane.sse_cursor/1` resume tokens (410 on unknown cursor)
- **Landing-zone submitters** — `LandingWatchSubmitter` in `etlantic-fastapi`
  composes file-drop watches outside core against 0.38 snapshot/incremental
  bindings (never embeds file bytes in plans)
- **Optional SQLModel reference stores** — request-scoped sessions in
  `etlantic-sqlmodel.control_plane`
- **Core stays optional-dep free** — `import etlantic` does not require FastAPI
  or SQLModel
- **Explicit non-claim** — CP1 is a foundation, **not** production multi-tenant
  isolation (**0.43**)

## Adopter actions

| Who | Action |
|---|---|
| Everyone on 0.39.x | Pin `etlantic==0.39.0` and matching plugins / `medallantic==0.39.0` together; see [migration](../11_DEVELOPMENT/MIGRATION_0_38_TO_0_39.md) |
| FastAPI embedders | Prefer `ETLanticAPI` / `include_router`; keep the thin `create_reference_app` for non-CP demos only |
| Control-plane authors | Build against frozen identity vocabulary; never treat path/header tenant ids as authority |
| Landing-zone watch authors | Use `LandingWatchSubmitter` (or equivalent) outside core; submit via durable API |
| Multi-tenant operators | Do **not** claim production isolation until **0.43** |

## Not in 0.39

- Production multi-tenant isolation claim (**0.43**)
- Complete tenant registry / persistence isolation (**0.40**)
- Durable execution-host protocol, leases, fencing (**0.41**)
- Policy engine, quotas, and GA audit graduation (**0.42–0.43**)
- Directory-watch loops inside ETLantic core
- Dropping the PyPI Beta classifier

## See also

- [Migration 0.38 → 0.39](../11_DEVELOPMENT/MIGRATION_0_38_TO_0_39.md)
- [Exit gate 0.39](../11_DEVELOPMENT/EXIT_GATE_0_39.md)
- [Findings ledger 0.39](../11_DEVELOPMENT/FINDINGS_0_39.md)
- [Implementation plan 0.39](../11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_39.md)
- [ADR-016: Control-Plane Identity](../11_DEVELOPMENT/adr/ADR-016-CONTROL-PLANE-IDENTITY.md)
- [Multi-tenant control plane plan](../11_DEVELOPMENT/MULTI_TENANT_CONTROL_PLANE_PLAN.md)
