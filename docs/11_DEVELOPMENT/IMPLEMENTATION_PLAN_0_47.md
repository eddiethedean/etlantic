---
title: ETLantic 0.47 Implementation Plan
description: Implementation-grade plan for the FastAPI scheduler/runner service and remote execution federation.
plan_status: current
plan_last_reviewed: 0.37.0
---

# ETLantic 0.47 Implementation Plan

Phase 0.47 adds an optional FastAPI-fronted scheduler and runner service while
separating API requests, durable scheduling, and execution-host processes. It
also federates remote execution while preserving signed-plan identity, scoped
authority, durable state, policy, reliability evidence, 0.46 dynamic-control
and streaming-error semantics, and normalized external-effect outcomes.

## Outcome

An adopter can use ETLantic's FastAPI service as the product boundary for
versioned schedules, manual triggers, dispatch, execution, status, and recovery
without adopting a separate orchestrator. The API durably records intent;
separately supervised scheduler and execution-host roles evaluate timers, lease
work, execute validated plans, and publish fenced results. The same control
plane can negotiate with remote execution hosts, resume events and reports
after disconnect, and compare results across runtime providers.

## Prerequisites And Non-Goals

- 0.43 control-plane support and 0.46 state/effect compatibility gates are closed.
- The remote protocol carries references and bounded artifacts, never ambient
  credentials or undeclared authority.
- Kubernetes and managed Spark are reference providers, not core dependencies.
- Network delivery does not imply exactly-once effects; unknown remote commit
  states remain explicit and governed by repair policy.
- FastAPI remains optional and never executes heavy pipelines in request
  handlers, `BackgroundTasks`, or application lifespan hooks.
- ETLantic supplies the scheduler service and execution-host roles, but does not
  become a general-purpose broker, cluster manager, or proprietary distributed
  scheduler. Durable stores and wake-up transports remain replaceable public
  providers.
- Production profiles require separate supervision for API, scheduler, and
  execution-host roles plus shared transactional storage. A single-process
  composition is development-only.
- Schedule semantics explicitly define timezone and DST handling, misfires,
  bounded catch-up, overlap, jitter, and effective start/end boundaries.

## Service Topology

```text
FastAPI gateway ── schedule/run mutations ──> transactional control store
                                                   │
scheduler service <── leader lease + due timers ───┤
       │ atomic, idempotent run acceptance         │
       └───────────────────────────────────────────┤
                                                   │
execution host <──── claim/lease/fence work ───────┘
       │
       └── PipelineRuntime + selected scheduler/backend plugins
```

## Workstreams

| ID | Workstream | Deliverables | Completion evidence |
|---|---|---|---|
| 047-N | Negotiation | Protocol/version, capability, identity, trust, policy, artifact, and recovery negotiation | Compatible/incompatible/version-skew matrix |
| 047-P | Remote protocol | Submit, accept/reject, lease, fence, heartbeat, cancel, retry, event cursor, report, artifact, disconnect/recover | State-machine model tests and fault injection |
| 047-A | Artifacts | Signed plans, content-addressed bundles, OCI image identity, SBOM/attestation linkage, resumable transfer | Tamper, partial-transfer, replay, and cache-poisoning tests |
| 047-L | Placement | Runtime constraints, locality, quota, region/residency, capability and cost evidence, explainable selection | Policy/capability placement rejection fixtures |
| 047-K | Kubernetes provider | Job reference provider, workload identity, scoped cleanup, logs/events/artifacts, cancellation | Isolated cluster conformance and orphan-cleanup tests |
| 047-S | Managed Spark reference | Versioned runtime image plus one managed Spark/Spark Connect provider contract | Semantic and failure comparison with local runtime |
| 047-O | Operations | Gateway integration, fleet health, capacity, recovery, upgrade/rollback, diagnostics | Multi-host loss/reconnect drills and runbooks |
| 047-SC | Schedule contracts | Versioned interval and cron schedules; timezone/DST, pause/resume, misfire, bounded catch-up, overlap, jitter, and effective-window policies | Canonicalization fixtures and deterministic clock/timezone matrix |
| 047-ST | Scheduler store | Schedule revisions, next-fire state, leader leases, atomic firing claims, idempotent run creation, and audit history | Transactional provider conformance and migration/rollback tests |
| 047-SD | Scheduler service | Separately supervised timer loop, leader election, clock-skew tolerance, bounded scans, backpressure, drain, and readiness | Multi-replica failover and duplicate-tick chaos tests |
| 047-EH | Execution host | Poll/consume, claim, lease, fence, heartbeat, cancel, execute validated plans, checkpoint, and publish normalized terminal results | Worker-loss, stale-fence, cancellation, and restart campaigns |
| 047-API | Schedule API and CLI | Authorized CRUD, manual trigger, pause/resume, firing history, next-fire preview, scheduler/worker health, and service-role commands | OpenAPI snapshots, generated-client smoke tests, and authz/non-enumeration matrix |
| 047-PR | Durable providers | Memory test provider, SQLModel transactional reference, and optional broker wake-up adapter with polling fallback | Cross-process conformance using the PostgreSQL reference deployment |

## Proposed Public Surface

- `etlantic schedule create|list|inspect|pause|resume|delete|preview|trigger`
- `etlantic scheduler serve` for timer evaluation and leadership
- `etlantic worker serve` for the execution-host role
- `/v1/definitions/{definition_id}/schedules`
- `/v1/schedules/{schedule_id}` with lifecycle, firing-history, preview, and
  manual-trigger subresources
- `/v1/scheduler/health` and an authorized worker-health surface

Exact names and wire schemas must freeze before implementation. Schedule
records contain revision selection, profile identity, policy fingerprints,
bounded parameters, and opaque secret references—never resolved secrets or
source rows.

## Scheduler And Runner Invariants

- The logical firing key derives from schedule identity, schedule revision, and
  nominal fire time. Re-evaluation, API retries, or leader failover returns the
  original accepted run.
- Firing creation and durable run/outbox acceptance are one transactional
  operation or leave no partial firing.
- Only the current scheduler-leader lease may advance next-fire state; only the
  current execution lease and fencing token may checkpoint or finalize work.
- Catch-up and execution retry are separately bounded. An outage cannot create
  an unbounded firing or retry storm.
- Cancellation prevents new attempts and is cooperatively observed in flight;
  uncertain external effects remain `unknown` and are never silently retried.
- Schedule deletion is auditable and does not erase prior firing/run evidence.

## Delivery Sequence

1. Freeze schedule/time semantics, scheduler and remote state machines, trust
   negotiation, wire schemas, diagnostics, and recovery invariants.
2. Implement the transactional scheduler provider, migrations, atomic
   firing-to-run acceptance, and deterministic fake-clock conformance suite.
3. Implement the separately supervised scheduler service and local execution
   host over existing durable-work and runtime boundaries.
4. Add FastAPI and CLI scheduling surfaces, authz, quotas, generated-client
   fixtures, observability, and split-role deployment profiles.
5. Build an in-process fake remote host, signed artifact transfer, resumable
   events, fencing, and disconnect repair.
6. Implement Kubernetes and one managed Spark reference provider, then run
   failover, backup/restore, capacity, and cross-runtime campaigns.

## Exit Gates

- The same signed plan runs on at least two qualified runtimes with comparable
  result, reliability, lineage, and effect evidence; differences are explained.
- Remote runtimes preserve stable mapped-child and branch identities, expansion
  bounds, compensation/failure semantics, dead-letter identifiers, registry
  evidence, and normalized report correlation or reject those capabilities
  during negotiation.
- Reconnect resumes ordered events and report retrieval without duplicating an
  attempt or allowing a stale host to publish final state.
- Remote identity and workload credentials are scoped, short-lived, provider
  supplied, and absent from plans, reports, artifacts, and logs.
- Worker loss after a possible external commit yields a durable unknown outcome,
  not an automatic safe-to-retry classification.
- Placement rejects missing capability, trust, policy, quota, residency, or
  recovery compatibility before artifact transfer or execution.
- Kubernetes and managed Spark providers pass isolated conformance, workload
  identity, cancellation, upgrade, and scoped cleanup tests.
- FastAPI remains a gateway/control dependency and is not imported by workers.
- Two scheduler replicas against one transactional store produce exactly one
  durable run per logical firing across duplicate ticks and leader failover.
- API or scheduler restart cannot lose an accepted schedule mutation or run;
  API processes perform no pipeline execution.
- Pause, resume, manual trigger, cancellation, bounded catch-up, DST, overlap,
  and misfire policies pass deterministic clock-driven tests.
- Production profiles reject memory stores, missing plugin allowlists, insecure
  authentication, and unresolved durability dependencies.
- Existing `Pipeline.run`/`arun`, LocalScheduler, Prefect, and Airflow compile
  paths remain compatible and independently usable.

## Required Release Evidence

- Remote protocol state-machine and version-skew report.
- Cross-runtime semantic/effect comparison.
- Disconnect, lease, fencing, cancellation, and unknown-commit chaos matrix.
- Artifact signature/transfer and credential-redaction report.
- Provider isolation, workload-identity, and cleanup evidence.
- Schedule semantics and DST/misfire/catch-up matrix.
- Scheduler-store and execution-host conformance reports.
- Multi-replica scheduler/worker chaos, fencing, and idempotency report.
- FastAPI scheduling OpenAPI/authz/non-enumeration snapshots.
- Schedule-count, due-fire scan, queue-depth, and worker-throughput envelope.
- Split-role deployment, upgrade/rollback, backup/restore, and incident runbooks.
