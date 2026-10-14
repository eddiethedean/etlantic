---
title: ETLantic 0.59 Implementation Plan
description: Consolidate managed ownership, configuration and dispatch before adding external trigger seams.
plan_status: implementation_complete_qualification_deferred
plan_last_reviewed: 2026-10-14
---

# ETLantic 0.59 Implementation Plan

Phase 0.59 is implemented and published. Its external qualification campaigns
remain deferred and are not represented as passed. The phase consolidates
existing managed implementation before extending the
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

## Implementation Baseline And Owner Map

The following map is grounded in repository revision `d742f560` (0.58.0
candidate), not a claim that every implemented path is qualified. Refresh it
against the implementation branch before moving code. The 0.58 release evidence
and exact support matrix are prerequisites for claiming preserved support;
characterization and consolidation proceeded while qualification evidence was
deferred.

| Concern | Current implementation | 0.59 disposition |
|---|---|---|
| Backend graph and role lifecycle | Core `ManagedBackend`, SQLModel `create_managed_backend`, FastAPI `ManagedBackend`, core `RuntimeRoleLifecycle` | Keep one graph and lifecycle implementation. SQLModel constructs relational resources; HTTP adapts the graph. Name the duplicated methods removed before deciding on a runtime wheel. |
| Settings | SQLModel `SQLModelBackendConfig` and FastAPI `ManagedBackendConfig` | Inventory the 25 common fields plus adapter-only fields; preserve defaults, constraints and callable/resource ownership. HTTP title/version/auth settings remain separate. |
| Preparation/admission and run control | `ManagedApplicationService` | Preserve canonical preparation, authorization, acceptance, cancellation and effects. A trigger bridge invokes these operations rather than rebuilding them. |
| Schedule commands and clock | `ScheduleApplicationService`, `schedule_models`, `SchedulerService` | Reuse revision, recurrence and firing policies; add only external timer ownership/delivery facts. Ready-node scheduling remains separate. |
| Dispatch state and recovery | `DispatchRecord` / `DispatchReconciliation`, `DurableWorkStore`, service `rearm_exhausted_prefect_dispatch`, `PrefectDispatcher` | Replace shared Prefect naming through versioned compatibility. Keep remote binding verification, SDK calls and vendor state translation in the adapter. |
| Worker and result execution | `ExecutionHost`, `ManagedExecutionAdapter` | Preserve leases, fencing, checkpoints, effects and publication. Extract managed coordination only through a public boundary; embedded execution stays core. |
| Persistence | `MemoryDurableWorkStore.dump/load`, SQLModel `durable_stores`, separate schedule/definition/report stores | Characterize the union of persisted state before replacing private serialization. Current memory dump/load covers fewer entity families than SQLModel's serializer; it is not a complete replacement codec. |
| HTTP destination policy | Public `etlantic.outbound` and profile policy | Reuse policy decisions and bounds; add transport enforcement/conformance for DNS, connection destinations and redirects, rather than a second policy model. |

The ownership ADR records each symbol's old/new import, implementation owner,
delegating compatibility export, supported installation and retirement window.
Consolidation may leave canonical services in core. A compatibility delegate is
not a duplicate implementation; two independently maintained bodies are.

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

### Ordered Delivery Gates

Each gate is a reviewable change set with its own evidence. Characterization
must pass before replacing an owner; namespace consolidation can ship without
extracting a wheel. Do not combine store migration, package extraction and new
trigger activation into one unreviewable cutover.

| Gate | Workstreams | Required input | Exit artifact / stop condition |
|---|---|---|---|
| A — truth and characterization | 059-V/F/B/P | Existing 0.58 candidate and review findings | Factory/version matrix, shared-setting inventory, owner/dependency ADR and persisted-entity inventory. Missing qualification is recorded explicitly. |
| B — public seams and compatibility | 059-F/P/G | Gate A inventories | One settings validator, complete public codec/transition boundary, generic dispatch decoder and tested legacy translations. Unknown schemas or unrepresentable rollback block mutation. |
| C — one managed implementation | 059-M/B/T | Gate B seams and migration fixtures | Installed headless/HTTP/Prefect parity, lifecycle/restart evidence and optional wheel decision with named implementation retirement. A deferred wheel does not waive consolidation. |
| D — trigger contract freeze | 059-C/O/A | Gate C authority; security and schedule decisions | Versioned wire/receipt schema, lifecycle/replay/authentication profile, shared transport conformance and minimal consumer. Unresolved occurrence identity or retention prevents activation. |
| E — durable bridge and recovery | 059-D/R/T | Gate D contract | Independent receiver/worker campaign over real stores; process kill, response loss, concurrent admission and uncertain-effect evidence. A request-local executor fails the gate. |
| F — release and downstream handoff | All | In-repository outputs from A–E and unchanged 0.58 support evidence; external campaigns may be deferred by an explicit exit-gate decision | AC/finding evidence index, compatibility/install report, bounded support matrix, runbook and explicit release decision that records deferred evidence without claiming it passed. |

## Trigger Admission And Lifecycle Contract

The runtime domain plan owns the lifecycle rules below; Gate D freezes their
exact public schema and diagnostic codes. Proposed fields are requirements,
not currently shipped API names.

- A registered schedule revision binds its allowed pipeline/revision policy,
  parameters, receiver, execution binding and trusted workload identity. The
  trigger carries only bounded references and correlation metadata; it cannot
  supply arbitrary pipeline code, profiles, factories, URLs or credential values.
  Any transmitted target reference must match the registered binding.
- Identity is scoped by trusted tenant/workspace, schedule ID/revision and a
  stable occurrence ID. Intended scheduled time is checked against the declared
  recurrence, timezone and ambiguity policy. Timer-owner generation authorizes
  delivery; it must not change the occurrence's deduplication identity. Delivery
  attempt, correlation and send time are excluded from the semantic digest.
- Authenticate, authorize the operation and bound/validate the wire before
  scoped receipt lookup. An authorized duplicate with matching semantic content
  recovers the existing receipt without repeating live preparation, quota
  charging or admission. Changed semantic content conflicts. Revocation denies
  access without exposing another scope's receipt.
- A new occurrence resolves pinned/latest-approved selection once, durably binds
  the selected revision and effective intent, then uses canonical preparation
  and admission. Recoverable preparation has the existing operation identity;
  retries cannot choose a newer pipeline revision. Recheck policy and credential
  access at the existing required boundaries without rewriting accepted intent.
- A preparation acknowledgement reports pending preparation and its query
  reference; it is not an accepted-run receipt. An accepted receipt binds the
  occurrence, submission/run identities and authorized status reference only
  after durable acceptance and recoverable dispatch linkage. Freeze response
  statuses and retry classification; an HTTP 2xx alone cannot establish acceptance.
- Persist occurrence reservation, resolved intent, canonical acceptance linkage
  and outbox/dispatch intent in one transaction where supported. Otherwise reuse
  a qualified durable handoff with recovery for every intermediate state. A
  crash before acceptance leaves a recoverable operation or explicit rejection;
  a crash after acceptance returns the same receipt and never admits again.
- Replay deadlines, clock skew and deduplication retention are one policy.
  After receipt compaction, a tombstone or validated admission horizon prevents
  an old occurrence from becoming new work. An authorized retained receipt may
  be queried after the delivery window; expiry cannot create a fresh admission.
- Pause/delete stops new occurrences at a recorded cutoff. Updates create a new
  immutable schedule revision. Owner migration fences the old generation before
  activating the new one and transfers outstanding occurrence identities.
  Specify admissibility of issued-but-unaccepted occurrences at each cutoff;
  already accepted work remains queryable and follows explicit run cancellation.

## Compatibility And Rollout

1. Freeze 0.58 installed import/config/dispatch/store fixtures, including pending,
   leased, uncertain, dispatched, cancelled and reconciliation-required work,
   route lifecycle history, attempts, checkpoints, effects and publication.
2. Introduce checked compatibility readers/exports before switching writers.
   Preserve `local` and `prefect:<digest>` meaning, remote IDs, idempotency keys,
   accepted envelope fingerprints, principal scope and lease/fencing ownership.
   A new backend kind is trusted registered configuration, not arbitrary input.
3. Inventory complete codec coverage, including action jobs and
   their idempotency, result publications, checkpoints, previews, diffs, shadows,
   baselines, diagnostics and route reference counts, plus separately stored
   schedules, definitions, events, inputs and reports. Each entity has one owner,
   schema/version and round-trip/restart case; explicitly cover families missing
   from the existing memory dump. Do not merge all stores into one
   snapshot. Validate the whole snapshot before replacing any live state.
4. Migrate schemas explicitly through the provider's migration authority, with
   backup/restore and process-version compatibility checks. Constructors, HTTP
   startup and read-only schema inspection never perform implicit DDL. Declare
   mixed-version worker/dispatcher compatibility; unsupported combinations fail
   readiness before claims or writes.
5. Exercise upgrade and rollback on populated Prefect stores. Rollback promises
   apply only to representable legacy work; a pre-0.59 binary cannot be assumed
   to understand new kinds or trigger records. Block unsafe downgrade before
   mutation and document drain/export or compatible recovery requirements.
   Restoring an old backup must not repeat externally committed effects.
6. Publish the `managed-headless` extra with SQLModel and the supported
   PostgreSQL driver without FastAPI. Preserve the existing HTTP-oriented `managed`
   extra during its declared window; adding a headless option does not silently
   change that extra's meaning. Test legacy HTTP constructors and explicit
   backend injection, including borrowed/owned engine and partial-start cleanup.

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

## Acceptance Evidence Matrix

These are required evidence families, not assertions that tests already pass.
Keep AC059-001–011 stable and attach each subcase to its gate and artifact. A
single happy-path receipt cannot satisfy a family.

| Evidence family | AC coverage | Required cases | Environment / owner |
|---|---|---|---|
| E059-OWN | 001, 007, 008 | Before/after symbols; all shared defaults/invalid values/legacy translations; direct and managed imports; separate HTTP settings; start/drain/close and partial-start failure | Built wheels in clean core-only, headless, HTTP and Prefect installs; runtime/backend |
| E059-MIG | 001, 009, 010 | Every persisted entity; unknown/truncated schema; upgrade/rollback; mixed process versions; accepted fingerprint/binding preservation; no implicit DDL or private serializer coupling | Memory/SQLite labelled separately; real PostgreSQL populated-store, multi-process and backup/restore campaign; persistence/Prefect |
| E059-WIRE | 002, 007 | Minimal wire-only consumer; non-FastAPI receiver; version skew, malformed/oversize payloads, unknown semantic fields and response validation | Independent receiver and worker processes over the canonical services; runtime/transport |
| E059-OCC | 003, 004, 005 | Concurrent duplicates/content conflicts; response loss; preparation crash and revision edit; delayed replay after compaction; DST/misfire/overlap; pause/update/delete and fenced owner transfer | Deterministic clock fixtures plus real PostgreSQL races and restart; schedule/backend |
| E059-SEC | 002, 003, 008 | Cross-scope lookup denial; revoked/rotated machine credentials; binding substitution; secret/row redaction; destination/DNS rebinding/redirect/TLS/byte/timeout bounds; explicitly trusted private destinations | Credential-free fixtures and controlled network servers using actual connections; security/transport |
| E059-REC | 005, 006, 007, 009 | Kill before/after acceptance/outbox/remote-create linkage; uncertain remote create; worker lease loss/stale callback; cancellation race; committed effect with missing result publication; stale/out-of-order observations | Independent real workers and durable stores; effectful 0.58 qualified tuples; runtime/Prefect/persistence |
| E059-REL | 011 | SDK absent/present × requested fake/live × actual backend; metadata/protocol version separation; lower/upper supported dependency boundaries and rejected combinations; declared SparkForge sunset | Built first-party wheel resolver/factory matrix, with actual live qualification separately identified; provider/release |

Each evidence row records case ID, AC IDs, workstream/finding, source revision,
wheel hashes, exact dependency/provider/store/process tuple, expected and observed
outcome, immutable artifact reference and pass/fail/unavailable/deferred status.
The 0.59 [exit gate](EXIT_GATE_0_59.md) defers all external campaigns in these
families. A deferred row remains unqualified and must retain its requirements
for follow-on work; it is not a pass. Required skips remain incomplete until
evidence is supplied or an explicit deferral is recorded in the relevant exit
gate. Accepted F01–F04/F06–F07/F09–F11 findings link to these families; F12 is
covered by the bounded downstream handoff.

## Decision Register And Downstream Handoff

| Decision | Accountable owner | Due / required record |
|---|---|---|
| D059-OWN: package or namespace consolidation | Runtime + backend | Gate A freezes boundaries; Gate C decides the wheel from actual retired implementations and installed acyclic imports. |
| D059-CFG: canonical settings and install migration | SQLModel + FastAPI + release | Gate B freezes the field/validator inventory, precedence, legacy translation and named optional extra/import windows. |
| D059-STORE: codec and dispatch compatibility | Persistence + Prefect | Gate B freezes schema versions, complete entity coverage, supported process combinations and downgrade guard; Gate E proves recovery. |
| D059-WIRE: delivery/authentication profile | Runtime + security | Frozen in `etlantic.control_plane.trigger`: envelope/1, 16 KiB UTF-8 JSON maximum, exact fields, duplicate-key rejection, trusted `ControlPlaneContext`, `schedule.trigger` authorization, bound workload identity, scoped receipt lookup, and OpenAPI JSON Schema. Malformed/unsupported is 400, oversize 413, stale or early occurrence 409, pending preparation 202, and accepted/skipped receipt 200. Gate D still requires independent consumer and credential-rotation evidence. |
| D059-OCC: occurrence and retention policy | Schedule + security | Frozen: occurrence identity is SHA-256 of schedule ID, revision ID and canonical UTC nominal time; delivery attempt and correlation are excluded. New delivery must match the atomic next-fire cursor and may be at most 60 seconds early. Known deliveries recover their receipt; schedule firings have no automatic compaction in 0.59 and remain durable. Pause/delete atomically reject new deliveries; delete also waits for unlinked occurrences to recover. Amendment invalidates unaccepted old-revision triggers, and owner transfer compare-and-swaps generation only after unlinked firings recover. Gate D still requires concurrency, delayed-retry, DST/misfire and retention evidence. |
| D059-REL: truthful ranges and sunset | Provider + release | Final SparkForge compatibility release is 0.62.0 with visible warnings through 0.62; Gate F still supplies resolver and migration evidence. |

Decisions block dependent activation or mutation, not unrelated characterization.
Other unresolved decisions remain assigned to their owner and gate; never present a proposed wire,
package or support tuple as shipped.

The Gate F handoff to 0.60–0.62 contains the versioned schema/error corpus,
minimal trigger consumer, endpoint/auth registration rules, capability and
occurrence mapping, timer-transfer procedure, generic dispatch public operations,
installed recipes and exact supported matrix. It qualifies a framework-neutral
receiver and existing durable worker with managed Prefect compatibility; Connect
and AWS platform behavior and Data Mover product integration retain their own
later gates. A second backend contract fixture can test extensibility here but
cannot establish ECS/Fargate support.

## Required Release Evidence And Decisions

Map AC059-001–011 and F01–F04/F06–F07/F09–F11 to installed-package, real-store,
compatibility, resolver, metadata and security evidence. Runtime/backend owners
record package/no-package decisions, moved operations and retired duplicates;
provider/release owners record truthful scope and version/sunset decisions.
Security owners freeze authentication, outbound and retention policy. P2 engine,
helper, fixture, existing-client and driver work has explicit 0.63 ownership in
the consolidation plan. No finding is closed by documentation alone, and a
transport receipt alone cannot close an execution gate.
