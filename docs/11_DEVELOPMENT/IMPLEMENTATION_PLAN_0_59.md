---
title: ETLantic 0.59 Implementation Plan
description: Consolidate managed ownership, configuration and dispatch before adding external trigger seams.
plan_status: planned
plan_last_reviewed: 2026-10-12
---

# ETLantic 0.59 Implementation Plan

Phase 0.59 consolidates existing managed implementation before extending the
schedule/HTTP boundary. The [runtime domain plan](ETLANTIC_RUNTIME_PLAN.md) owns
architecture; the [package consolidation plan](PACKAGE_SCOPE_CONSOLIDATION_PLAN.md)
traces all accepted review recommendations. `etlantic-runtime` is a conditional
implementation extraction, not a contracts-only wrapper. These changes are
planned and do not alter the qualified 0.56–0.58 support matrices.
Brownfield scope follows in [0.63](IMPLEMENTATION_PLAN_0_63.md).

## Outcome

Headless, HTTP and managed Prefect callers use one managed service graph, one
configuration authority and provider-neutral dispatch. Missing external timer
and HTTP-delivery concepts adapt existing admission, run, result and effect
models. A compatible receiver durably admits a trigger and an independent worker
executes it. Embedded pipeline/DAG execution remains in core.

## Prerequisites And Non-Goals

- Reuse public 0.56 admission/execution/effects/results, 0.57 headless services,
  schedules and supervision, and bounded 0.58 accepted references/dispatch.
- Map every proposed operation/type to its existing owner before adding schemas
  or moving code. Reuse contracts; do not introduce parallel state machines.
- Runtime may depend on public core and receive stores/platform operations by
  injection. Core has no mandatory reverse dependency; runtime never imports
  concrete persistence, web or vendor adapters. If extraction would create a
  cycle, consolidate namespaces first and defer the wheel.
- No whole-directory runtime move, persistence layout redesign, new engine
  support, product dependency or `etlantic-quarto` creation/planning.
- [SQLModel](SQLMODEL_INTEGRATION_PLAN.md) keeps one distribution. Engine/helper,
  existing HTTP-client and fixture consolidation continue in 0.63; new transport
  work in 0.60/0.61 must already consume shared outbound policy.
- The [shared delivery contract](FORWARD_IMPLEMENTATION_PLANS.md) applies.

## Workstreams

| ID | Workstream | Deliverables | Completion evidence |
|---|---|---|---|
| 059-V | Factory and release truth | Actual backend/live capability/qualification metadata, one distribution-version source, reference-only labels, supported dependency-range decision, SparkForge final-version/window declaration | SDK × requested mode × actual factory matrix; installed metadata; resolver matrix and sunset record |
| 059-F | Canonical configuration | Provider/backend settings with one default/validator; separate HTTP settings; preferred existing-backend adaptation; legacy translation and headless recipe/extra | All 25 shared fields covered; no-default-drift, installed headless/HTTP parity; documented managed-extra migration |
| 059-B | Ownership and packaging | Before/after map of managed roles, dispatch, accepted references, schedules and results; package charters; public seams; compatibility/install/version ADR | Named code moved and duplicate API retired for any new wheel; acyclic installed imports; embedded/core self-contained |
| 059-G | Generic dispatch | Evolve existing records/operations to validated backend kind, immutable deployment binding and opaque remote-run ID; versioned Prefect decoder/migration | Accepted Prefect work survives upgrade/rollback; unknown kinds rejected; vendor APIs/state translation stay adapter |
| 059-P | Persistence seam | Public modeling/stores/schema/managed namespaces with compatible exports; characterized versioned snapshot codec or transition boundary | All persisted entity coverage, no private dictionary serialization, store recovery/conformance; contention baseline before redesign |
| 059-M | Managed consolidation | Single role construction/supervision, dispatch coordination and reconciliation implementation; staged optional runtime extraction through public interfaces | Same service graph for headless/HTTP/Prefect; no second runtime or state machine; compatibility migration |
| 059-C | Missing contracts | External timer capabilities, trigger wire/receipt bridge and authentication context mapped to existing authoritative values | Owner mapping; version-skew and malformed/unsupported corpus; minimal generated wire consumer |
| 059-O | Occurrence lifecycle | Revision/occurrence identity, one timer owner, replay/dedupe retention, pause/update/delete semantics | Concurrent duplicates/conflicts, delayed retry, DST/misfire and timer migration fixtures |
| 059-A | Auth and outbound policy | Scoped credentials, authorization, existing outbound policy/conformance, rotation/revocation and bounded payloads | Cross-scope/replay, destination/redirect/byte/redaction tests, actual DNS/connect behavior and trusted private deployments |
| 059-D | Durable admission and dispatch | Canonical service adaptation, transactional occurrence/run/outbox linkage and durable receipts | Kill/response-loss recovery across acceptance and dispatch boundaries |
| 059-R | Results and recovery | Distinct transport/job/ETL/effect/publication observations, authenticated hints and canonical reconciliation | Lost/stale/duplicate callbacks, worker loss and unknown-effect fixtures |
| 059-T | Conformance | Installed headless/HTTP/Prefect parity and framework-neutral trigger harness over the same authority | Existing direct/managed compatibility, independent receiver/worker, restart and real-store effects |

## Delivery Sequence

1. Correct actual-backend and version claims; label reference fixtures. Record
   supported ranges and an explicit SparkForge final compatibility version and
   warning/migration window before changing release owners.
2. Canonicalize backend settings and characterize existing services/records and
   persistence codec coverage. Freeze the before/after ownership and dependency
   ADR, migration windows and headless installation design.
3. Generalize dispatch with accepted Prefect fixtures, upgrade and rollback
   evidence. Preserve validated bindings and scope; do not admit arbitrary routes.
4. Introduce the public persistence seam and consolidate managed operations in
   small changes. Extract runtime only when it removes named implementations or
   duplicate APIs and preserves an acyclic dependency graph.
5. Add only missing timer/HTTP wire concepts, canonical occurrence admission,
   outbound policy and effect-aware reconciliation. Reuse existing result values.
6. Publish installed parity, failure/security evidence, migration examples and
   exact seams consumed by 0.60–0.62. A second concrete dispatch adapter is proven
   in 0.61, not by claiming AWS support in this phase.

## Exit Gates

- **AC059-001:** Existing imports/protocols remain compatible; plain core
  authoring/embedded execution is self-contained. Any runtime wheel has a named
  extraction/duplicate-retirement map, public acyclic imports and explicit
  optional-install diagnostics. A models-only wrapper fails the package gate.
- **AC059-002:** Wire negotiation rejects unknown versions, unsupported semantics
  and untrusted scope before effects; no resolved secrets or source rows persist.
- **AC059-003:** Duplicate occurrences return one run; conflicting content and
  expired/delayed replay cannot silently admit new runs.
- **AC059-004:** Every occurrence receives fresh canonical admission under one
  timer authority, preserving revision and recurrence policy across changes.
- **AC059-005:** Receipts survive receiver/dispatcher failure; accepted work
  never depends on request-local tasks or an API process remaining alive.
- **AC059-006:** Worker loss/callback loss reconciles without fabricated success,
  unfenced publication or blind replay of uncertain effects.
- **AC059-007:** One managed implementation passes installed headless/HTTP/Prefect
  parity and the independent non-FastAPI trigger harness; direct scheduling and
  the exact existing execution/effect matrix remain compatible.
- **AC059-008:** Every shared backend setting has one default and validator;
  HTTP settings cannot independently change worker behavior. Legacy constructors
  translate correctly; an explicit headless install does not install FastAPI.
- **AC059-009:** Generic dispatch uses validated kind/binding/remote identity;
  accepted Prefect records survive migration/rollback. No new vendor record/store
  family or AWS field is introduced in core; second-backend proof is a 0.61 gate.
- **AC059-010:** SQLModel consumes a complete public versioned codec/transition
  seam, not core private dictionaries. Compatible namespaces and read-only schema
  inspection pass conformance/recovery; storage redesign needs measured contention.
- **AC059-011:** Iceberg, Snowflake, S3 and registered factories report actual
  implementation, capability and qualification truthfully; unavailable live
  requests fail. Factory/distribution versions agree independently of protocol
  versions, reference packages are clearly labelled, dependency policy has resolver
  evidence, and SparkForge has a recorded final version and migration window.

## Required Release Evidence And Decisions

Map AC059-001–011 and F01–F04/F06–F07/F09–F11 to installed-package, real-store,
compatibility, resolver, metadata and security evidence. Runtime/backend owners
record package/no-package decisions, moved operations and retired duplicates;
provider/release owners record truthful scope and version/sunset decisions.
Security owners freeze authentication, outbound and retention policy. P2 engine,
helper, fixture, existing-client and driver work has explicit 0.63 ownership in
the consolidation plan. No finding is closed by documentation alone, and a
transport receipt alone cannot close an execution gate.
