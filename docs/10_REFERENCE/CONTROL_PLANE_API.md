# Control plane API (CP1–CP4 + CP-GA)

> **Status: Available in ETLantic 0.48.0.** CP1–CP4 are foundations;
> **CPn alone ≠ GA**. Production multi-tenant is **Available** for Supported
> profiles (`isolated-deployment`, `dedicated-schema`); `shared-service`
> remains Experimental; community **non-SLA**.

Short hub for the provisional `etlantic.control_plane` surface and optional
FastAPI adapter. Prefer this over digging through implementation plans when
embedding the control plane.

## Guide

| Topic | Where |
|---|---|
| Adopter how-to (embed FastAPI) | [Control plane (CP1)](../06_EXECUTION/CONTROL_PLANE.md) |
| Durable work (CP3) | [Durable work](../06_EXECUTION/DURABLE_WORK.md) |
| CP-GA claim / evidence | [What's new in 0.44](../01_GETTING_STARTED/WHATS_NEW_0_43.md) · [Exit gate 0.43](../11_DEVELOPMENT/EXIT_GATE_0_43.md) |
| What shipped in CP4 | [What's new in 0.42](../01_GETTING_STARTED/WHATS_NEW_0_42.md) |
| Identity freeze | [ADR-016](../11_DEVELOPMENT/adr/ADR-016-CONTROL-PLANE-IDENTITY.md) |
| Durable submission / state | [ADR-018](../11_DEVELOPMENT/adr/ADR-018-DURABLE-SUBMISSION-AND-STATE.md) |
| Wire schema ids | [Wire schema ranges](WIRE_SCHEMA_RANGES.md) |
| FastAPI dual surface | [`etlantic-fastapi` README](https://github.com/eddiethedean/etlantic/blob/main/packages/etlantic-fastapi/README.md) · [Optional packages](OPTIONAL_PACKAGES.md) |
| Program sequencing | [Multi-tenant control plane plan](../11_DEVELOPMENT/MULTI_TENANT_CONTROL_PLANE_PLAN.md) |
| 0.47 schedule/worker HTTP | [What's new in 0.47](../01_GETTING_STARTED/WHATS_NEW_0_47.md) — Available gateway; workers stay off FastAPI |

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

Pin: `pip install 'etlantic-fastapi==0.48.0'` (match `etlantic==0.48.0`).

When `durable_work` is set, `POST /v1/definitions/{id}/runs` dual-writes into
`DurableWorkStore.accept` with the same `submission_id` as the CP1 receipt.
If durable accept fails after a newly created CP1 receipt, the API compensates
by cancelling the CP1 run so hosts are not left with accepted work and no
outbox. `POST /v1/runs/{id}/cancel` cancels the durable submission **first**,
then the CP1 run observation (durable 404/409 are treated as continue so CP1
can still converge). Cancel expires any live durable lease; heartbeat and
checkpoint CAS fail closed under `cancel_requested`.
Shipped host routes under `/v1/durable/*` (authz first):

| Route | Purpose |
|---|---|
| `GET /v1/durable/outbox` | Pending outbox drain |
| `POST /v1/durable/outbox/{outbox_id}/published` | Mark outbox published |
| `POST /v1/durable/submissions/{id}/cancel` | Cancel accepted work |
| `POST …/leases` · `…/leases/heartbeat` · `…/leases/release` | Lease acquire / heartbeat / release |
| `POST …/attempts` · `POST /v1/durable/attempts/{id}/finish` | Attempt start / finish |
| `POST /v1/durable/checkpoints/{id}/cas` | Namespaced checkpoint CAS (**requires** `attempt_id` + `fencing_token`) |
| `POST …/replay` | Replay from optional checkpoint |
| `POST /v1/durable/previews` | Create TTL preview workspace |
| `POST /v1/durable/effects` | Record effect evidence |
| `POST /v1/durable/submissions/{id}/repair` | Plan repair / backfill |
| `POST /v1/durable/checkpoints/{id}/diagnose` | Diagnose checkpoint (mutating; POST only) |
| `POST /v1/durable/shadow` | Authorize shadow run |

Core does **not** embed a broker or worker supervisor; adopters drain the
outbox with their own dispatcher.

### Schedule routes (Available in 0.47)

The 0.47 release ships these gateway routes. FastAPI remains the gateway only;
scheduler and execution-host processes stay out of the ASGI
worker ([ADR-023](../11_DEVELOPMENT/adr/ADR-023-SCHEDULER-SERVICE-AND-FEDERATION.md)).

| Route | Purpose |
|---|---|
| `/v1/definitions/{definition_id}/schedules` | Create / list schedules for a definition |
| `/v1/schedules/{schedule_id}` | Inspect / update / delete |
| `…/pause` · `…/resume` · `…/preview` · `…/trigger` · `…/firings` | Lifecycle, next-fire preview, manual trigger, firing history |
| `/v1/scheduler/health` | Authorized scheduler-leader health |
| `/v1/workers/health` | Authorized worker health (no host leak to unauthorized callers) |

Matching CLI: `etlantic schedule …`,
`etlantic scheduler serve`, `etlantic worker serve`.

### Context and proposal routes (Available in 0.48)

Compute-only inspect routes. They do **not** persist proposals or apply
files. Apply remains `/v1/approvals*`
([ADR-024](../11_DEVELOPMENT/adr/ADR-024-HUMAN-GOVERNED-AI.md)).

| Route | Purpose |
|---|---|
| `POST /v1/definitions/{definition_id}/context` | Bounded redacted `etlantic.context_bundle/1` |
| `POST /v1/proposals/validate` | Deterministic sandbox; `applied` is always false |

Authz runs before lookup; missing or unauthorized definitions are opaque `404`.

Matching CLI: `etlantic context bundle`, `etlantic proposal validate`.

### CP4 governance routes

When the matching provider is injected on `ETLanticAPI`, hosts expose:

| Route | Purpose |
|---|---|
| `POST /v1/policy/decide` | Policy decision |
| `POST /v1/approvals` · `GET …/{id}` · `POST …/decide` · `POST …/revoke` | Approvals / SoD |
| `POST /v1/quotas/admit` · `POST …/release` · `POST …/suspend` · `POST …/contain` | Quotas |
| `POST /v1/erasure/requests` · `…/plan` · `…/plans/{id}/execute` · `GET …/reports/{id}` | Erasure lifecycle |
| `GET /v1/audit` · `GET /v1/audit/export` | Audit evidence |
| `POST /v1/attestations` · `POST …/verify-plan` · `POST …/schema-observations/verify` | Attestations |
| `POST /v1/objectives` · `GET …/{id}` · `POST …/evaluate` · `POST …/notify` | Delivery objectives |

Missing CP4 providers on a mounted route return Problem Details `PMCP501`.
Policy/quota/approval/attestation gates run on submit/promote when those
providers are configured.

## PMCP errors

Control-plane failures use Problem Details with `PMCP*` codes (not pipeline
`PMPIPE*`):

| Code | Typical meaning |
|---|---|
| `PMCP401` | Unauthenticated / missing principal |
| `PMCP403` | In-scope forbid (authorization deny) |
| `PMCP404` | Not found **or** cross-scope non-enumeration |
| `PMCP409` | Conflict (for example idempotency) |
| `PMCP501` | Provider not configured on a mounted CP route |
| `PMCP503` | Provider unavailable / fail-closed outage |

Wire schema: `etlantic.control_plane.error/1`. Authorization runs before
existence lookup; cross-tenant misses stay opaque **404**.

## Related

- [Python API overview](API_REFERENCE.md)
- [FAQ — What is CP1?](../01_GETTING_STARTED/FAQ.md#what-is-cp1)
- [Production readiness](../06_EXECUTION/PRODUCTION_READINESS.md)
