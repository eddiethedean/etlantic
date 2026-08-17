---
title: ETLantic 0.47 Implementation Plan
description: Implementation-grade plan for the FastAPI scheduler/runner service and remote execution federation.
plan_status: current
plan_last_reviewed: 0.46.0
---

# ETLantic 0.47 Implementation Plan

> **Status: Current — not started.** Planning freeze after ETLantic **0.46.0**.
> See [ADR-023](adr/ADR-023-SCHEDULER-SERVICE-AND-FEDERATION.md) (Proposed) and
> [EXIT_GATE_0_47](EXIT_GATE_0_47.md). Do not describe 0.47 surfaces as
> Available. Implementation of scheduler/worker processes, FastAPI schedule
> routes, Kubernetes, Spark Connect, SQLModel migration `004`, or new packages
> is **out of scope for this freeze**.

Phase 0.47 adds an optional FastAPI-fronted scheduler and runner service while
separating API requests, durable scheduling, and execution-host processes. It
also federates remote execution while preserving signed-plan identity, scoped
authority, durable state, policy, reliability evidence, 0.46 dynamic-control
and streaming-error semantics, and normalized external-effect outcomes.

It reuses CP3 `DurableWorkStore`, `ETLanticAPI` `/v1/*`,
`ExecutionScheduler` / `LocalScheduler`, and `PipelineRuntime` instead of
inventing a second orchestrator or executing pipelines in the API process.

## Outcome

An adopter can use ETLantic's FastAPI service as the product boundary for
versioned schedules, manual triggers, dispatch, execution, status, and recovery
without adopting a separate orchestrator. The API durably records intent;
separately supervised scheduler and execution-host roles evaluate timers, lease
work, execute validated plans, and publish fenced results. The same control
plane can negotiate with remote execution hosts, resume events and reports
after disconnect, and compare results across runtime providers.

`Pipeline.run` / `arun`, Prefect local MVP, and Airflow `compile_plan` remain
independently usable.

## Prerequisites And Non-Goals

- 0.43 control-plane support and 0.46 state/effect compatibility gates are
  closed ([EXIT_GATE_0_46](EXIT_GATE_0_46.md),
  [ADR-022](adr/ADR-022-DYNAMIC-CONTROL-AND-STREAMING.md)).
- [ADR-018](adr/ADR-018-DURABLE-SUBMISSION-AND-STATE.md) remains authority:
  accept is not execute; core does not embed a broker.
- The remote protocol carries references and bounded artifacts, never ambient
  credentials or undeclared authority.
- Kubernetes and Spark Connect are Experimental reference extras, not core
  dependencies. Live Kind/cluster and live Databricks/EMR are 0.51 (or
  explicit 0.47 live skips). Helm/OCI production images are out of 0.47.
- Network delivery does not imply exactly-once effects; unknown remote commit
  states remain explicit and governed by repair policy.
- FastAPI remains optional and never executes heavy pipelines in request
  handlers, `BackgroundTasks`, or application lifespan hooks.
- ETLantic supplies the scheduler service and execution-host roles, but does
  not become a general-purpose broker, cluster manager, or proprietary
  distributed scheduler. Durable stores and wake-up transports remain
  replaceable public providers.
- Production profiles require separate supervision for API, scheduler, and
  execution-host roles plus shared transactional storage. A single-process
  composition is development-only.
- Schedule semantics explicitly define timezone and DST handling, misfires,
  bounded catch-up, overlap, jitter, and effective start/end boundaries.
- Do not merge timer-service discovery with `etlantic.scheduler/1` or
  `etlantic.orchestration/1`. Do not conflate connectors
  (`etlantic.source/1` / `sink/1`) with compute placement.

## Optional packages (named before implementation)

Per [FORWARD_IMPLEMENTATION_PLANS](FORWARD_IMPLEMENTATION_PLANS.md) Shared
Entry Criteria §3, extras are named now. None of these packages exist yet.

| Extra / PyPI name | Role | Target maturity |
|---|---|---|
| `etlantic-k8s` | Kubernetes Job resource provider + `FakeKubernetes` | **Experimental** |
| `etlantic-spark-connect` | Spark Connect `SparkProvider` + in-process fake | **Experimental** |

SQLModel schedule persistence extends the existing `etlantic-sqlmodel`
package (migration `004_schedules_0_47`). FastAPI schedule routes extend
existing `etlantic-fastapi`. Scheduler/worker loops and `ScheduleStore` live
in core so workers do not import FastAPI.

Core gains no Kubernetes, Spark Connect, or broker SDK. Production discovery
of these plugins fails closed on `Profile.plugin_allowlist`; resource
providers additionally require a non-empty
`Profile.resource_provider_allowlist` (name → optional version pin) under
`security_mode="production"` when a resource provider is selected.

Default wake-up is polling. An optional wake-transport protocol may exist; no
new broker package ships in 0.47.

## Supported vs Experimental target freeze

Claims only. Nothing below is Available until [EXIT_GATE_0_47](EXIT_GATE_0_47.md)
records Met evidence.

| Surface | Target | Notes |
|---|---|---|
| Schedule contracts + fake-clock DST/misfire/catch-up | **Supported** (core) | Deterministic |
| `ScheduleStore` + memory test provider | **Supported** (core tests) | Production rejects memory |
| Scheduler + execution-host loops | **Supported** (core CLI) | Split-role required in production |
| SQLModel schedule provider + `004` | **Supported** (`etlantic-sqlmodel`) | Optional package |
| FastAPI/CLI schedule surfaces | **Supported** (`etlantic-fastapi`) | Gateway only |
| In-process fake remote host + signed-plan/artifact fakes | **Supported** (core tests) | No network credentials |
| Wake-up adapter (broker-style) | **Experimental** | Protocol + polling fallback |
| `etlantic-k8s` + `FakeKubernetes` | **Experimental** | Live Kind/cluster = skip `047-K-01` |
| `etlantic-spark-connect` + fake | **Experimental** | Live Databricks/EMR = 0.51; skip `047-S-01` |
| Helm/OCI production images | **Out of 0.47** | 0.51 `051-D` |

## Service topology

```text
FastAPI gateway ── schedule/run mutations ──> transactional control store
                                                   │
scheduler service <── leader lease + due timers ───┤
       │ atomic, idempotent run acceptance         │
       └───────────────────────────────────────────┤
                                                   │
execution host <──── claim/lease/fence work ───────┘
       │
       └── PipelineRuntime + LocalOrchestrator
              │
              ├── in-process fake remote host
              ├── etlantic-k8s (Experimental FakeKubernetes)
              └── etlantic-spark-connect (Experimental fake)
```

## Frozen public names

Exact names freeze here. Do not implement them in this freeze.

### CLI

- `etlantic schedule create|list|inspect|pause|resume|delete|preview|trigger`
- `etlantic scheduler serve`
- `etlantic worker serve`

### HTTP

Workspace-scoped; same authz, idempotency, and non-enumeration as CP1.
Unauthorized callers must not learn host identity from worker health.

- `/v1/definitions/{definition_id}/schedules`
- `/v1/schedules/{schedule_id}` plus `pause`, `resume`, `preview`, `trigger`,
  `firings`
- `/v1/scheduler/health` (authorized)
- `/v1/workers/health` (authorized)

### Wire ids (provisional `/1`)

- `etlantic.schedule/1` — revision, timezone, misfire, catch-up, overlap,
  jitter, window, secret-free parameter refs
- `etlantic.firing/1` — logical key
  `(schedule_id, revision_id, nominal_fire_time)`
- `etlantic.remote-runtime/1` — negotiate / submit / lease / event-cursor /
  report / disconnect
- `etlantic.resource/1` — discoverable entry `etlantic.resource_providers`

Reuse `etlantic.control_plane.accept_receipt/1`, durable lease/attempt
records, and `etlantic.plan/1`. Schedule rows store revision + profile
identity + policy fingerprints + opaque secret refs — never resolved secrets
or rows.

### Diagnostics (preview families until ship)

Do not overload existing `PMSCHED*` (`etlantic.scheduler/1` plugin analysis).

- `PMSVC*` — topology / role / production store
- `PMFIRE*` — schedule / firing / DST / misfire / catch-up
- `PMFED*` — remote negotiation / skew / fencing / unknown-commit
- `PMRES*` — resource providers / `resource_provider_allowlist`

## Scheduler and runner invariants

- The logical firing key derives from schedule identity, schedule revision,
  and nominal fire time. Re-evaluation, API retries, or leader failover
  returns the original accepted run.
- Firing creation and durable run/outbox acceptance are one transactional
  operation or leave no partial firing.
- Only the current scheduler-leader lease may advance next-fire state; only
  the current execution lease and fencing token may checkpoint or finalize
  work. These leases are distinct.
- Catch-up and execution retry are separately bounded. An outage cannot
  create an unbounded firing or retry storm.
- Cancellation prevents new attempts and is cooperatively observed in flight;
  uncertain external effects remain `unknown` and are never silently retried.
- Schedule deletion is auditable and does not erase prior firing/run evidence.

## 0.46 and optimizer interaction

[ADR-022](adr/ADR-022-DYNAMIC-CONTROL-AND-STREAMING.md) remains the streaming
and dynamic-control authority. Remote hosts preserve stable mapped-child and
branch identities, expansion bounds, compensation/failure semantics,
dead-letter identifiers, registry evidence, and normalized report correlation
or reject those capabilities during negotiation (`PMFED*`).

Optimization stays advisory ([ADR-021](adr/ADR-021-OPTIMIZER-PASS-PROTOCOL.md)).
Federation must not silently rewrite map/branch/stream plans. Default
`optimization_policy` remains `off`.

## Fail-closed production trust

- Production `plugin_allowlist` covers k8s / spark-connect plugins.
- Production `resource_provider_allowlist` covers resource providers when
  selected; empty allowlists fail closed.
- Production rejects `MemoryScheduleStore`, missing plugin allowlists,
  insecure authentication, and unresolved durability dependencies.
- Plans, reports, schedules, diagnostics, audit, and fixtures never contain
  event payloads, source rows, or resolved secrets (FORWARD invariant).
- FastAPI is a gateway/control dependency and is not imported by workers.

## Workstreams

| ID | Workstream | Deliverables | Completion evidence |
|---|---|---|---|
| 047-SC | Schedule contracts | Versioned interval and cron schedules; timezone/DST, pause/resume, misfire, bounded catch-up, overlap, jitter, and effective-window policies | Canonicalization fixtures and deterministic clock/timezone matrix |
| 047-ST | Schedule store | Schedule revisions, next-fire state, **scheduler-leader** leases (distinct from CP3 execution leases), atomic firing claims, idempotent run creation, and audit history | Transactional provider conformance and migration/rollback tests |
| 047-SD | Scheduler service | Separately supervised timer loop, leader election, clock-skew tolerance, bounded scans, backpressure, drain, and readiness | Multi-replica failover and duplicate-tick chaos tests |
| 047-EH | Execution host | Poll/consume CP3 outbox, claim, lease, fence, heartbeat, cancel, execute validated plans via `LocalOrchestrator`, checkpoint, and publish normalized terminal results; no FastAPI import | Worker-loss, stale-fence, cancellation, unknown-commit, and restart campaigns |
| 047-API | Gateway and CLI | Frozen routes/commands; authorized CRUD, manual trigger, pause/resume, firing history, next-fire preview, scheduler/worker health | OpenAPI snapshots, generated-client smoke tests, and authz/non-enumeration matrix |
| 047-PR | Durable providers | Memory test provider, SQLModel transactional reference (`004_schedules_0_47`), polling wake-up; optional wake-transport protocol | Cross-process conformance using the PostgreSQL reference deployment |
| 047-N | Negotiation | Protocol/version, capability, identity, trust, policy, artifact, recovery, and 0.46 stream/dyn caps | Compatible/incompatible/version-skew matrix |
| 047-P | Remote protocol | Submit, accept/reject, lease, fence, heartbeat, cancel, retry, event cursor, report, artifact, disconnect/recover | State-machine model tests and fault injection |
| 047-A | Artifacts | Signed plans, content-addressed bundles, OCI image identity, SBOM/attestation linkage, resumable transfer (fakes in CI) | Tamper, partial-transfer, replay, and cache-poisoning tests |
| 047-L | Placement | Runtime constraints, locality, quota, region/residency, capability and cost evidence, explainable selection | Policy/capability placement rejection fixtures **before** artifact transfer |
| 047-K | Kubernetes reference | `etlantic-k8s` Job provider, `FakeKubernetes`, workload identity, scoped cleanup, logs/events/artifacts, cancellation | Fake conformance; live Kind/cluster skip `047-K-01` |
| 047-S | Spark Connect reference | `etlantic-spark-connect` plus in-process fake; semantic compare vs local Spark | Fake conformance; live Databricks/EMR skip `047-S-01` |
| 047-O | Operations | Split-role compose, fleet health, capacity, recovery, upgrade/rollback, diagnostics | Multi-host loss/reconnect drills and runbooks (no live cluster required) |

## Quantified scorecard

All **Current** cells are **Not started**. Implementation must not begin until
this freeze is recorded and [EXIT_GATE_0_47](EXIT_GATE_0_47.md) exists.

| # | Measure | Required | Current |
|---|---|---:|---|
| 1 | 047-SC schedule contracts + fake-clock DST/misfire/catch-up | Pass | **Not started** |
| 2 | 047-ST ScheduleStore + leader lease distinct from CP3 | Pass | **Not started** |
| 3 | 047-SD scheduler service dual-replica one-firing | Pass | **Not started** |
| 4 | 047-EH execution host wraps CP3; no FastAPI import | Pass | **Not started** |
| 5 | 047-API FastAPI/CLI frozen names; authz/non-enumeration | Pass | **Not started** |
| 6 | 047-PR SQLModel `004` + memory; polling wake-up | Pass | **Not started** |
| 7 | 047-N negotiation + 0.46 dyn/stream caps or reject | Pass | **Not started** |
| 8 | 047-P remote protocol state machine + fault injection | Pass | **Not started** |
| 9 | 047-A signed-plan/artifact fakes; no secrets in artifacts | Pass | **Not started** |
| 10 | 047-L placement rejects before transfer | Pass | **Not started** |
| 11 | 047-K `etlantic-k8s` Experimental FakeKubernetes | Pass | **Not started** |
| 12 | 047-S `etlantic-spark-connect` Experimental fake | Pass | **Not started** |
| 13 | 047-O split-role ops/runbooks (no live cluster required) | Pass | **Not started** |
| 14 | Two replicas → one durable run per logical firing | Pass | **Not started** |
| 15 | Unknown commit never auto-retry; worker-loss explicit | Pass | **Not started** |
| 16 | Production allowlists fail closed; memory store rejected | Pass | **Not started** |
| 17 | Existing `Pipeline.run`/`arun`, LocalScheduler, Prefect, Airflow compile unchanged | Pass | **Not started** |
| 18 | No unresolved P0 in [FINDINGS_0_47](FINDINGS_0_47.md) | 0 | **Not started** |
| 19 | Claim freeze recorded on [EXIT_GATE_0_47](EXIT_GATE_0_47.md) | Pass | **Not started** |

Live Kind (`047-K-01`) and live Spark Connect (`047-S-01`) are **deferred
Experimental skips**, not blockers.

## Delivery sequence

Implementation (later — not this freeze):

1. Freeze schedule/time semantics, scheduler and remote state machines, trust
   negotiation, wire schemas, diagnostics, and recovery invariants (this
   document + ADR-023).
2. Implement the transactional scheduler provider, migrations, atomic
   firing-to-run acceptance, and deterministic fake-clock conformance suite.
3. Implement the separately supervised scheduler service and local execution
   host over existing durable-work and runtime boundaries.
4. Add FastAPI and CLI scheduling surfaces, authz, quotas, generated-client
   fixtures, observability, and split-role deployment profiles.
5. Build an in-process fake remote host, signed artifact transfer, resumable
   events, fencing, and disconnect repair.
6. Implement Experimental `etlantic-k8s` and `etlantic-spark-connect` fakes,
   then run failover, backup/restore, and capacity campaigns without requiring
   a live cluster.

## Exit Gates

- Two scheduler replicas against one transactional store produce exactly one
  durable run per logical firing across duplicate ticks and leader failover.
- API or scheduler restart cannot lose an accepted schedule mutation or run;
  API processes perform no pipeline execution.
- Pause, resume, manual trigger, cancellation, bounded catch-up, DST,
  overlap, and misfire policies pass deterministic clock-driven tests.
- The same signed plan runs on at least two qualified runtimes with comparable
  result, reliability, lineage, and effect evidence; differences are explained.
- Remote runtimes preserve stable mapped-child and branch identities,
  expansion bounds, compensation/failure semantics, dead-letter identifiers,
  registry evidence, and normalized report correlation or reject those
  capabilities during negotiation.
- Reconnect resumes ordered events and report retrieval without duplicating an
  attempt or allowing a stale host to publish final state.
- Remote identity and workload credentials are scoped, short-lived, provider
  supplied, and absent from plans, reports, artifacts, and logs.
- Worker loss after a possible external commit yields a durable unknown
  outcome, not an automatic safe-to-retry classification.
- Placement rejects missing capability, trust, policy, quota, residency, or
  recovery compatibility before artifact transfer or execution.
- Kubernetes and Spark Connect Experimental extras pass fake conformance;
  live isolated deployments remain skip `047-K-01` / `047-S-01` until 0.51.
- FastAPI remains a gateway/control dependency and is not imported by workers.
- Production profiles reject memory stores, missing plugin allowlists,
  empty resource-provider allowlists when those plugins are selected, insecure
  authentication, and unresolved durability dependencies.
- Existing `Pipeline.run`/`arun`, LocalScheduler, Prefect, and Airflow compile
  paths remain compatible and independently usable.

## Required Release Evidence

Planning freeze (now):

- This implementation plan
- [ADR-023](adr/ADR-023-SCHEDULER-SERVICE-AND-FEDERATION.md)
- [EXIT_GATE_0_47](EXIT_GATE_0_47.md)
- [FINDINGS_0_47](FINDINGS_0_47.md)

At ship (not written in this freeze):

- Remote protocol state-machine and version-skew report
- Cross-runtime semantic/effect comparison
- Disconnect, lease, fencing, cancellation, and unknown-commit chaos matrix
- Artifact signature/transfer and credential-redaction report
- FakeKubernetes / FakeSparkConnect conformance; live skips recorded
- Schedule semantics and DST/misfire/catch-up matrix
- Scheduler-store and execution-host conformance reports
- Multi-replica scheduler/worker chaos, fencing, and idempotency report
- FastAPI scheduling OpenAPI/authz/non-enumeration snapshots
- Schedule-count, due-fire scan, queue-depth, and worker-throughput envelope
- Split-role deployment, upgrade/rollback, backup/restore, and incident runbooks
- Future `WHATS_NEW_0_47` / `MIGRATION_0_46_TO_0_47` (do not publish as
  Available until the exit gate is Met)

## 0.51 boundary

[IMPLEMENTATION_PLAN_0_51](IMPLEMENTATION_PLAN_0_51.md) hardens live Kubernetes
and managed Spark (Databricks, EMR, Spark Connect), signs OCI/Helm
distribution, and promotes provider packs. 0.47 ships protocols plus
in-process fakes. Do not pull 0.51 live-cluster production claims into this
gate.
