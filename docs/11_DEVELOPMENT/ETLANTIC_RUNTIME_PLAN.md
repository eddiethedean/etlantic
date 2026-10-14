---
title: ETLantic Runtime Integration Plan
description: Consolidation of shared managed implementation with missing external timer and HTTP trigger seams.
plan_status: planned
plan_last_reviewed: 2026-10-12
---

# ETLantic Runtime Integration Plan

**Status: 0.59 is implemented and published; external qualification is deferred; see the
[phase plan](IMPLEMENTATION_PLAN_0_59.md).** The proposed
`etlantic-runtime` package is a conditional implementation extraction, not a
shipped API or another contracts-only layer. The accepted
[package scope review](PACKAGE_SCOPE_REVIEW_2026-10-12.md) is integrated by the
[consolidation plan](PACKAGE_SCOPE_CONSOLIDATION_PLAN.md). Existing 0.56/0.57 backend
services and the bounded 0.58 managed Prefect profile retain their current
authority and support limits. See [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md).

## Source And Program Sequence

This four-plan set reconstructs the decisions in
[ETLantic Quarto Orchestration](https://chatgpt.com/c/6acbd4a8-6d60-83e9-98f4-963bc85b2357),
including the subsequent endpoint-independence and optional `fastapi-posit`
clarifications. The conversation's downloadable Markdown/ZIP artifacts were
not available through the chat reader; these are repository-integrated plans,
not verbatim copies of those files. Detailed gates below reconcile that design
with the existing durable backend and the accepted package scope review. The
review supersedes the initial contracts-only runtime and dual-executor AWS scopes.

| Phase | Outcome | Domain plan |
|---|---|---|
| 0.59 | Managed runtime consolidation and missing trigger seams | This plan |
| 0.60 | One explicit-URL Connect trigger topology | [rsconnect](ETLANTIC_RSCONNECT_PLAN.md) |
| 0.61 | Scheduler/Lambda delivery and ECS/Fargate execution | [AWS](ETLANTIC_AWS_PLAN.md) |
| 0.62 | One Data Mover host and optional endpoint discovery | [Data Mover](ETLANTIC_DATA_MOVER_INTEGRATION_PLAN.md) |
| 0.63 | Brownfield bridges (formerly 0.59) | [Implementation](IMPLEMENTATION_PLAN_0_63.md) |
| 0.64 | Operator console (formerly 0.60) | [Implementation](IMPLEMENTATION_PLAN_0_64.md) |
| 0.65 | Enterprise provider packs (formerly 0.61) | [Implementation](IMPLEMENTATION_PLAN_0_65.md) |
| 0.66 | TransformationModel incubation (formerly 0.62) | [Implementation](IMPLEMENTATION_PLAN_0_66.md) |

Later phase slots remain 0.63–0.66; their package decisions are demand-gated
under the consolidation plan. Published versions, package pins, and qualification
evidence are not renumbered or rewritten. `etlantic-quarto` does not exist and
must not be created or planned. Platform tooling required by Connect does not
create an ETLantic package requirement.

## Ownership And Dependencies

| Owner | Responsibility |
|---|---|
| `etlantic` | Authoring, canonical value models and durable transitions, deterministic planning, public protocols, embedded DAG execution, policy, fencing and effect/publication semantics |
| Conditional `etlantic-runtime` | One shared managed role construction/supervision, dispatch coordination, accepted-reference/reconciliation implementation and missing external trigger bridge; reuse core authorities |
| `etlantic-sqlmodel` and injected stores | Relational persistence, migrations and provider configuration; consume a public versioned codec/transition seam, not core private dictionaries |
| Proposed `etlantic-rsconnect` | Deploy/configure lightweight scheduled trigger content; authenticated HTTPS delivery |
| Proposed `etlantic-aws` | Scheduler/Lambda timer delivery and ECS/Fargate execution over generic shared dispatch; Batch deferred |
| Existing `etlantic-fastapi` | Optional HTTP receiver and authorized status/result projections over shared services |
| Optional `fastapi-posit` | Trusted public base-URL integration, subject to public-API verification |
| Data Mover | Product identity/configuration, credential references, durable storage configuration, execution placement, and run/result views |

`etlantic-rsconnect` and `etlantic-fastapi` consume the same public/wire contract
without depending on each other. A compatible non-FastAPI receiver must work.
Runtime depends on public core; concrete persistence/platform adapters consume
runtime where needed. Runtime receives stores and platform operations through
injected public interfaces and must not import concrete adapters. Core has no
mandatory runtime, web or platform dependency. Existing managed import paths
may use compatibility exports with explicit optional-install diagnostics and a
recorded migration window; ordinary authoring/embedded imports remain complete.

If this dependency direction cannot be preserved, refactor existing namespaces
first and defer the runtime wheel. Do not move the whole `runtime/` directory or
introduce a second state machine. Generated trigger scripts use the minimal
versioned wire contract without installing the complete ETL engine/provider
stack; this does not justify a separate contracts distribution.

## Consolidation Before New Contracts

Phase 0.59 maps each proposed model and operation to its current owner, including
`ManagedBackend`, `ManagedApplicationService`, `ExecutionHost`,
`ManagedExecutionAdapter`, `SchedulerService`, durable schedules/dispatch and
0.58 accepted-reference/reconciliation behavior. Keep existing value models and
transition semantics authoritative. Add only missing external timer and HTTP
concepts. External occurrence scheduling is distinct from ready-node
`ExecutionScheduler`; they must not become one universal scheduler abstraction.

Extract named role construction, supervision, dispatch coordination and
reconciliation implementation in stages through public seams. Record the
before/after map and duplicate APIs retired; a wheel containing new models over
unchanged owners fails the packaging gate. Headless/HTTP/Prefect installed parity,
restart and uncertain-effect recovery must pass after each change. No engine,
frontend, DDL, SQLModel schema, platform SDK, provider credential or Data Mover
product logic moves into runtime.

Generalize existing dispatch records/operations to a validated backend kind,
immutable deployment binding and opaque remote-run ID. Vendor calls, binding
verification and remote-state translation remain in Prefect/AWS adapters. Use
versioned decoders and migration/rollback fixtures for accepted Prefect work;
do not widen routes to arbitrary strings or add a new record/store family for
each vendor. ECS/Fargate supplies second-concrete-backend evidence in 0.61.

Canonicalize the 25 shared FastAPI/SQLModel backend fields under one provider
configuration, separate HTTP settings, and prefer adapting an existing backend.
Keep legacy constructors as checked compatibility translations. Plan an explicit
headless recipe/extra and a documented migration for the existing HTTP-oriented
`managed` extra. SQLModel keeps modeling/stores/schema/managed namespaces in one
wheel and consumes one characterized public codec/transition boundary. Benchmark
contention before any persistence layout redesign.

Correct actual fake/live identity and distribution metadata before expansion,
classify reference-only factories, and record the SparkForge compatibility sunset.
Targeted engine/helper/fixture/client/driver cleanup follows in 0.63. The
[consolidation plan](PACKAGE_SCOPE_CONSOLIDATION_PLAN.md) owns all package charters
and conditional package decisions.

## Contracts And Lifecycle

`ScheduleBackend` and `ExecutionBackend` are illustrative names, pending
0.59 mapping to existing public protocols. New interfaces require a demonstrated
missing seam, not an overlapping name for existing behavior. Scheduling decides
when to request fresh admission; execution consumes only canonically accepted
work. Neither capability implies the other.
The existing local scheduler, 0.57 schedule service, and 0.58 Prefect adapter
remain compatible and retain their distinct supported matrices.

1. Register a schedule revision with one timer owner, pipeline reference,
   receiver endpoint, credential reference, recurrence, timezone, and explicit
   DST, misfire, catch-up, overlap, retry, pause, and deletion semantics.
2. Deliver a versioned trigger containing bounded identifiers: schedule ID and
   revision, stable occurrence ID, intended scheduled time, pipeline reference,
   and correlation metadata. Delivery-attempt IDs are separate. Retries and
   redelivery preserve occurrence identity; wall-clock send time is not identity.
3. Authenticate the caller and derive authorized scope server-side. Authorize
   the operation and validate the bounded wire before scoped receipt lookup;
   payload scope does not grant authority. A matching authorized duplicate
   recovers its receipt without repeating preparation or quota charging.
   For a new occurrence, validate revision, replay window, registered target,
   policy and references; resolve pinned/latest-approved intent once and persist
   that selection before recoverable canonical preparation and admission.
4. Atomically persist the deduplication record, canonical run linkage, and
   dispatch intent, or use an existing qualified outbox/recovery protocol where
   stores differ. A bounded accepted receipt is returned only after durable
   acceptance. A pending preparation response names the canonical operation and
   is not an accepted-run receipt. Same occurrence and semantic content returns
   the same run; conflicting content under that key is rejected. Delivery-attempt
   IDs, correlation and send timestamps do not change semantic identity.
   Concurrent requests cannot admit twice or select different pipeline revisions.
5. Independently supervised workers claim accepted work through public runtime
   contracts. Dispatch acknowledgement, remote job state, ETL outcome, external
   effect certainty, and result publication remain separate facts.
6. Reconcile missed callbacks by authorized polling or durable events. Callback
   signatures, scope, attempt identity, fencing, and monotonic transitions must
   be checked; a callback cannot fabricate ETL success or clear unknown effects.

Define retention and replay policy together: an expired deduplication record
must not permit a delayed occurrence to create a new run. Schedule updates,
pause/delete, deployment replacement, and timer-owner migration must specify
which already-issued occurrences remain admissible.

### Occurrence Authority And Change Boundaries

The deduplication key uses trusted tenant/workspace, schedule ID/revision and
stable occurrence identity. Intended scheduled time is validated against the
declared recurrence and timezone/ambiguity policy. The registered schedule binds
the permitted pipeline, parameters, receiver, execution binding and workload
identity; wire references cannot replace those bindings. Retries of pending
preparation reuse its durable resolved intent even if the pipeline is edited.
Policy/credential checks still occur at the canonical required boundaries.

| Change | Required behavior |
|---|---|
| Schedule update | Create an immutable revision and record the cutoff for previously issued but unaccepted occurrences. Never rewrite accepted intent. |
| Pause or delete | Stop new occurrences at a durable cutoff. Define whether previously issued deliveries can still be admitted; cancel accepted work only through an explicit authorized run command. |
| Timer-owner transfer | Fence the old owner generation before activating the new one; transfer outstanding identities. Generation authorizes delivery but is not part of occurrence deduplication identity. |
| Receipt compaction | Retain a tombstone or enforce a validated admission horizon so delayed deliveries cannot become new work. Retained receipt queries remain distinct from new delivery admission. |
| Credential rotation/revocation | Reauthorize delivery and receipt lookup using the current trusted scope. A duplicate key does not bypass revocation or expose another scope's work. |

Freeze the exact wire version, semantic digest, error/retry classes, response
statuses, machine-credential profile, body bounds, clock skew and retention
limits before trigger activation. Unsupported semantics fail closed. An HTTP 2xx
or a preparation acknowledgement cannot establish durable run acceptance.

### Persistence And Dispatch Migration

Characterize the complete persisted-entity inventory before selecting a public
codec/transition seam. The current memory `dump/load` and SQLModel private
serializer have different coverage; replacing the latter with the former alone
would omit state. The [phase owner map and rollout](IMPLEMENTATION_PLAN_0_59.md)
identify these implementations and the entity families requiring evidence.
Keep separately owned schedule/definition/event/input/report stores separate.
Version and validate the complete payload before state replacement; malformed or
unsupported snapshots must not partially mutate a live store.

Preserve existing `local`/`prefect:<digest>` routes, binding/envelope fingerprints,
remote identities, scope, dispatch idempotency and lease/fencing ownership during
generic-record migration. Compatibility readers precede new writers; declared
mixed-version process combinations pass readiness before claims. Provider schema
migrations remain explicit and read-only inspection never runs DDL.

Prove upgrade and rollback on accepted legacy Prefect work. A legacy binary is
not assumed to read new backend kinds or trigger state: reject unrepresentable
downgrades before mutation and document compatible recovery or drain/export.
Backup restore cannot authorize replay of externally committed effects.

## Security And Failure Boundaries

- Require HTTPS, scoped trigger credentials, rotation/revocation, replay
  protection, bounded payloads/timeouts/retries, and redacted diagnostics.
- Endpoint registration is authorized configuration. Reuse existing outbound
  policy/conformance for origins, paths, redirects, timeouts, byte bounds and
  redaction. Test actual DNS/connect behavior and explicit trusted private
  deployment configuration; a URL validator alone is insufficient. Under that
  policy, untrusted callers cannot choose URLs, credential references, backend
  factories, or code.
- Schedulers receive trigger credentials only, never source/sink credentials,
  source rows, transformations, or complete pipeline configuration.
- Production plugins and applicable optimization, schema-registry, and resource
  providers remain explicitly allowlisted. Schema inspection does not run DDL.
- API process exit must not lose accepted work. FastAPI `BackgroundTasks` and
  in-process request execution are not durable executors.
- Execution uncertainty invokes existing effect reconciliation; transport retry
  never implies exactly-once external writes or permission to repeat effects.

## Gates, Evidence, And Open Decisions

Phase 0.59 owns the operation map, canonical configuration, generic dispatch,
public persistence seam, conditional extraction/value gate, truthful factory
metadata and contract/version freeze. Installed headless/HTTP/Prefect parity,
import isolation, compatibility, receiver/worker conformance and failure evidence
are required. Phases 0.60/0.61
qualify actual platform behavior; phase 0.62 proves the full application path.
No live-support claim follows from mocks or a successful trigger response.

The [0.59 ordered gates and decision register](IMPLEMENTATION_PLAN_0_59.md)
sequence characterization, public seams, managed consolidation, contract freeze,
durable recovery and release handoff. Runtime/backend maintainers freeze the
dependency map before extraction; security/schedule maintainers freeze wire,
occurrence/replay retention and authentication before trigger activation.
Unresolved decisions block their dependent work while characterization proceeds.
Platform maintainers must resolve recurrence translation and stable occurrence
derivation before platform qualification.
Review this plan whenever those decisions, upstream APIs, or release gates change.

Required evidence includes a before/after single-owner implementation map,
named duplicate retirement, accepted Prefect upgrade/rollback, configuration
parity, complete codec/store recovery, factory/version and install-range matrices,
SparkForge migration-window decisions, a protocol-to-existing-service mapping, schema and
version-skew corpus, non-FastAPI interoperability, duplicate/conflict/replay
tests, restart and lost-response recovery, callback reconciliation, credential
redaction, and explicit supported/unsupported matrices. The
[forward delivery contract](FORWARD_IMPLEMENTATION_PLANS.md) applies throughout.
The phase evidence index maps E059-OWN/MIG/WIRE/OCC/SEC/REC/REL to all
AC059-001–011 and assigned findings, with exact wheel/provider/process versions
and immutable results. Gate F hands the frozen contract, minimal consumer and
unsupported matrix to 0.60–0.62; it does not qualify their platform behavior.
