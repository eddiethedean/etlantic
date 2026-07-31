# Exit Gate 0.39 — Control-Plane API and Identity (CP1)

> **Status: Gate-ready for tag/publish rehearsal toward ETLantic 0.39.0** after
> post-exit honesty pass (top-20 P0/P1 closed; see [FINDINGS_0_39](FINDINGS_0_39.md)).
> Package version is **0.39.0**. **P0 = 0.** Soft-continue: `038-X-01`.
> **CP1 is not a production multi-tenant isolation claim** — that remains
> gated to **0.43**. Close only against exact candidate wheels when publishing.

| Deliverable | Status |
|---|---|
| Planning: ADR-016 / this exit gate / findings / What's New / migration | **Met** |
| Identity models + scoped request context | **Met** (`etlantic.control_plane`) |
| `etlantic-fastapi` embeddable router / app factory + OpenAPI 3.1 | **Met** (`ETLanticAPI`; thin `create_reference_app` remains non-CP) |
| Resource routes (discover, validate, plan, submit, status, …) | **Met** |
| Authorization before lookup + non-enumeration matrix | **Met** (`test_cp1_full_authz_matrix.py`) |
| Durable `202` acceptance + scoped idempotency | **Met** (`test_cp1_durable.py`, `test_idempotency_scope_0_39.py`; **`accepted` ≠ executed**) |
| Resumable SSE / event envelope | **Met** (`cp_stream_run_events`, `test_cp1_sse.py`) |
| Landing-zone submitter bridge (outside core) | **Met** (`landing_sensor.py`, `test_cp1_landing.py`) |
| Optional SQLModel reference stores (request-scoped) | **Met** (`etlantic_sqlmodel.control_plane`; `pytest.mark.sqlmodel`) |
| Release notes: CP1 ≠ production multi-tenant | **Met** (What's New / Migration / CHANGELOG / this gate) |

## Quantified exit scorecard

From [IMPLEMENTATION_PLAN_0_39](IMPLEMENTATION_PLAN_0_39.md) exit gates:

| Measure | Required | Current |
|---|---:|---|
| Existing FastAPI app embeds router without replacing lifespan, DI, middleware, or exception handling | Pass | **Met** (`include_router`; host owns Problem Details handlers — see residual notes) |
| OpenAPI 3.1 stable with deterministic operation IDs | Pass | **Met** (`openapi_cp1_snapshot.json`; fail-if-missing, no silent auto-write) |
| Generated client completes reference workflow | Pass | **Met** (OpenAPI dump + happy-path smoke) |
| Two API workers share durable submissions and event history | Pass | **Met** (shared store + threadpool idempotency; SQLModel restart) |
| Restart of either worker does not lose accepted work | Pass | **Met** (accept receipt in injected store) |
| Authn/authz precede existence lookup, count, search, pagination, artifact access, and event subscription | Pass | **Met** |
| Every operation passes two-tenant/two-workspace allow/deny and non-enumeration matrix | Pass | **Met** (`test_cp1_full_authz_matrix.py`) |
| Live schema observations labeled observations; cannot become contract authority via API side effect | Pass | **Met** |
| Optional SQLModel stores use request-scoped sessions and separate request / persistence / response models | Pass | **Met** |
| Heavy pipeline work depends on FastAPI `BackgroundTasks` | 0 | **Met** (0) |
| Process-local globals used as production acceptance store | 0 | **Met** (0; memory fakes test-only) |
| Production multi-tenant claim at CP1 | 0 | **Met** (docs boundary explicit) |
| Core long-lived directory-watch loops | 0 | **Met** (submitter outside core) |
| Unresolved P0 findings | 0 | **Met** ([FINDINGS_0_39](FINDINGS_0_39.md)) |
| FastAPI / SQLModel remain optional dependencies of core | Pass | **Met** (`test_optional_deps_report.py`) |

## Evidence map

| Gate item | Evidence |
|---|---|
| Identity / non-enum / durable / SSE freeze | [ADR-016](adr/ADR-016-CONTROL-PLANE-IDENTITY.md) |
| Implementation order | [IMPLEMENTATION_PLAN_0_39](IMPLEMENTATION_PLAN_0_39.md) |
| Domain architecture | [MULTI_TENANT_CONTROL_PLANE_PLAN](MULTI_TENANT_CONTROL_PLANE_PLAN.md) |
| HTTP adapter plan | [FASTAPI_INTEGRATION_PLAN](FASTAPI_INTEGRATION_PLAN.md) |
| Finding severity / threat review | [FINDINGS_0_39](FINDINGS_0_39.md) |
| Adopter migration | [MIGRATION_0_38_TO_0_39](MIGRATION_0_38_TO_0_39.md) |
| Adopter highlights | [WHATS_NEW_0_39](../01_GETTING_STARTED/WHATS_NEW_0_39.md) |
| OpenAPI snapshot | `tests/fastapi/openapi_cp1_snapshot.json` (fail-if-missing) |
| Authz matrix | `tests/fastapi/test_cp1_full_authz_matrix.py` |
| Redaction / SSE / landing / durable / submit | `tests/fastapi/test_cp1_{redaction,sse,landing,durable,submit_hardening}.py` |
| Idempotency scope | `tests/control_plane/test_idempotency_scope_0_39.py` |
| SQLModel stores (marked) | `tests/sqlmodel/test_control_plane_stores.py` |
| Optional-deps report | `tests/control_plane/test_optional_deps_report.py` |
| Prior connectivity exit | [EXIT_GATE_0_38](EXIT_GATE_0_38.md) |

## Acceptance checklist

### Planning (Wave 0)

- [x] [IMPLEMENTATION_PLAN_0_39](IMPLEMENTATION_PLAN_0_39.md) published
- [x] [ADR-016](adr/ADR-016-CONTROL-PLANE-IDENTITY.md) Accepted
- [x] This exit gate published
- [x] [FINDINGS_0_39](FINDINGS_0_39.md) ledger opened
- [x] [WHATS_NEW_0_39](../01_GETTING_STARTED/WHATS_NEW_0_39.md) completed
- [x] [MIGRATION_0_38_TO_0_39](MIGRATION_0_38_TO_0_39.md) completed
- [x] Indexes / roadmap / mkdocs mark 0.39 CP1 gate-ready

### Identity, API, and authorization

- [x] Versioned identity models and immutable `ControlPlaneContext`
- [x] Embeddable router / app factory with stable operation IDs
- [x] Authz before lookup on every resource operation
- [x] Two-tenant / two-workspace non-enumeration matrix green

### Durability and events

- [x] `202 Accepted` + accept receipt from durable store (`accepted` ≠ executed)
- [x] Scoped idempotency across workers / restart
- [x] Resumable SSE cursor + authorized event history
- [x] No `BackgroundTasks` heavy execution path

### Composition and release

- [x] Landing-zone watch submitter outside core
- [x] Optional SQLModel stores request-scoped and collected under `-m sqlmodel`
- [x] Release notes state CP1 ≠ production multi-tenant
- [x] Package bump to 0.39.0 with optional-dependency report
- [x] Post-exit honesty pass closed top-20 P0/P1 rows with evidence

## Residual / follow-ons

- Tenant registry and persistence isolation — **0.40**
- Durable execution hosts, leases, fencing — **0.41**
- Policy, quotas, audit hardening — **0.42**
- Production multi-tenant graduation — **0.43**
- Echo plugin connector on PyPI (`038-X-01`) — separate soft-continue
- **`include_router`:** does **not** install Problem Details exception handlers;
  hosts that embed must register them (or use `create_app`)
- **`accepted` ≠ executed:** accept receipt status means durable accept only
- Optional `pytest.mark.fastapi` on `tests/fastapi/test_cp1_*.py` for selective CI

## See also

- [Implementation plan 0.39](IMPLEMENTATION_PLAN_0_39.md)
- [Findings ledger 0.39](FINDINGS_0_39.md)
- [ADR-016: Control-Plane Identity](adr/ADR-016-CONTROL-PLANE-IDENTITY.md)
