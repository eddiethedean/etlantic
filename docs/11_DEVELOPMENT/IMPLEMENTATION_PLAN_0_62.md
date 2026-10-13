---
title: ETLantic 0.62 Implementation Plan
description: Durable Data Mover integration and optional trusted Posit endpoint discovery.
plan_status: planned
plan_last_reviewed: 2026-10-12
---

# ETLantic 0.62 Implementation Plan

Phase 0.62 composes Data Mover with the shared runtime and qualified platform
adapters. The [Data Mover domain plan](ETLANTIC_DATA_MOVER_INTEGRATION_PLAN.md)
owns the consuming-application boundary. Former 0.62 TransformationModel scope
moves intact to [0.66](IMPLEMENTATION_PLAN_0_66.md). Integration remains planned.

## Outcome

An authenticated scheduled trigger reaches Data Mover, creates a durable run,
and dispatches independent execution. Operators can inspect actual results,
failure and recovery state. Optional `fastapi-posit` integration helps configure
the public endpoint while explicit HTTPS configuration works everywhere.

## Prerequisites And Non-Goals

- 0.59 consolidated managed implementation/configuration and 0.60/0.61 timer
  adapters compose with existing backend services. Initial reference: CP1 FastAPI
  adapting one SQLModel/PostgreSQL backend and one separately supervised installed
  durable worker. Manual/Connect/AWS-Lambda timers target that same composition.
  Prefect/ECS placements and alternative hosts require demand and separate
  consumer qualification; standalone adapter support does not imply it here.
- Extend existing `etlantic-fastapi` CP1 surfaces; `create_reference_app` remains
  a thin authoring demo. No second ETL state machine or product dependency in core.
- Data Mover supplies host identity/configuration and persistence deployment;
  public ETLantic services supply admission, execution, and result authority.
- `etlantic-rsconnect` takes compatible endpoints without depending on FastAPI.
  `fastapi-posit` remains optional and its actual public API must be verified;
  use a small consumer adapter, not a new `etlantic-fastapi-posit` wheel.
- No long ETL in ASGI workers/`BackgroundTasks`; no `etlantic-quarto` package
  creation or planning. Full operator-console scope remains 0.64.

## Workstreams

| ID | Workstream | Deliverables | Completion evidence |
|---|---|---|---|
| 062-H | HTTP receiver | Trigger validation/auth, canonical service adaptation, durable receipt/status contracts | Manual/headless/HTTP policy and acceptance parity |
| 062-P | Persistence and placement | One canonical SQLModel configuration/store composition, run linkage, shared dispatch and separately supervised durable worker | Real PostgreSQL commit/kill/restart and worker recovery |
| 062-U | URL discovery | Optional verified `fastapi-posit` adapter, explicit override, trusted prefix-preserving URL composition | Spoofed-header, prefix, no-request startup and redeployment tests |
| 062-S | Schedule composition | Backend selection, one timer owner, revision/update/pause/delete and migration | Connect/AWS lifecycle without duplicate admitted occurrences |
| 062-R | Results | Durable canonical results, authenticated callbacks, polling/event reconciliation, product projections | Missed/out-of-order callback, ETL failure and partial-effect fixtures |
| 062-Q | Consumer qualification | One installed CP1/PostgreSQL/worker host, real effects, independently qualified timer variants and unsupported combinations | Separate API/worker processes, two-scope security and end-to-end failure campaign |
| 062-O | Operations | Migration, rollback, role health/drain, backup/recovery, support boundaries | Reproducible deployment and incident drills |

## Delivery Sequence

1. Freeze one receiver/backend/worker host composition, route/schema and
   Data Mover-to-public-service mapping under the
   [consolidation plan](PACKAGE_SCOPE_CONSOLIDATION_PLAN.md).
2. Prove durable HTTP acceptance and independent execution using explicit URLs.
3. Add the separately qualified timer variants, schedule lifecycle and canonical
   result views against the same host; no general deployment-combination matrix.
4. Verify `fastapi-posit` API and add optional trusted endpoint discovery with
   persisted configuration and explicit override fallback.
5. Qualify Connect/AWS paths, failure/recovery, isolation and deployment lifecycle.

## Exit Gates

- **AC062-001:** Concurrent duplicate triggers and response loss create one
  canonical run and recoverable dispatch; conflicting/replayed triggers fail.
- **AC062-002:** Killing API/dispatcher/worker processes at acceptance, dispatch,
  effects, and publication boundaries cannot lose accepted work or invent success.
- **AC062-003:** Manual, Connect and AWS requests reuse canonical policy/admission;
  the one reference worker has real execution/publication evidence and timer
  variants are independently qualified. Unsupported host/executor swaps are explicit.
- **AC062-004:** Missing, stale, duplicated or out-of-order callbacks reconcile
  through authorized observations, preserving fencing and uncertain effects.
- **AC062-005:** Optional URL discovery validates trusted origin/path and preserves
  app/router prefixes; explicit configuration works without the optional package
  or a startup request. Untrusted headers never mutate saved destinations.
- **AC062-006:** Cross-tenant access, endpoint tampering, forged callbacks, and
  credential revocation fail closed without secret/source-row leakage.
- **AC062-007:** Real CSV→PostgreSQL and PostgreSQL→PostgreSQL consumer flows,
  backup/recovery, schedule migration and deployment rollback pass the exact
  supported timer/host matrix; API process lifetime does not own ETL execution.

## Required Release Evidence And Decisions

Map AC062-001–007 to installed consumer traces, real-store crash campaigns,
platform support tables, URL/proxy tests, security reports, and operations
runbooks. Application/API maintainers own host/route design and security owners
approve trusted proxy/origin configuration during design review. Verify optional
dependency API/version before implementation; review on consumer or platform
changes. A recipe or mocked callback is insufficient end-to-end evidence.
