---
title: ETLantic 0.61 Implementation Plan
description: Bounded AWS Scheduler/Lambda delivery and one ECS/Fargate executor over shared dispatch.
plan_status: planned
plan_last_reviewed: 2026-10-12
---

# ETLantic 0.61 Implementation Plan

Phase 0.61 builds optional `etlantic-aws` with independent scheduling and
execution capabilities. The [AWS domain plan](ETLANTIC_AWS_PLAN.md) owns service
boundaries and the [package consolidation plan](PACKAGE_SCOPE_CONSOLIDATION_PLAN.md)
applies F02/F09/F12. Enterprise provider candidates follow in
[0.65](IMPLEMENTATION_PLAN_0_65.md) under demand gates. New AWS adapters remain planned.

## Outcome

EventBridge Scheduler delivers runtime triggers through a qualified HTTPS relay;
One ECS/Fargate adapter executes canonically accepted work with durable correlation,
recovery, and publication. Scheduling can use a different executor, and AWS
execution can receive work admitted from another scheduler.

## Prerequisites And Non-Goals

- Reuse consolidated 0.59 managed implementation, generic dispatch and outbound
  policy/conformance plus public 0.56–0.58 admission, accepted
  references, execution/fencing, and effect recovery. No dependency on Connect,
  FastAPI, or Data Mover; no vendor SDK in core.
- Initial scope is static-batch `/1` with PostgreSQL durable state. Broader
  plan/runtime support requires separate evidence, never inferred compatibility.
- Do not promise direct arbitrary HTTPS delivery from EventBridge Scheduler.
  Qualify Scheduler → scoped Lambda relay → receiver as the initial transport.
- ECS/Fargate is the sole initial executor. Batch, event-bus/API-destination
  relay variants and other AWS services are unscheduled demand-gated candidates.
  No S3 data access, Secrets Manager, general infrastructure provisioning or
  second runtime is absorbed into this package. Broader provider packs stay in 0.65.

## Workstreams

| ID | Workstream | Deliverables | Completion evidence |
|---|---|---|---|
| 061-S | Scheduling | Native schedule lifecycle and exact recurrence/identity mapping | Live schedule, timezone/DST, update/pause/delete and misfire matrix |
| 061-H | HTTPS relay | Scoped delivery-only Lambda, shared outbound policy, bounded retry/deadline, DLQ/redrive | Lost responses, duplicates, replay and redacted delivery failure tests |
| 061-E | ECS/Fargate | Pinned task binding, immutable accepted reference, installed targeted worker | Live ETL effects/publication, task loss, cancel and recovery |
| 061-D | Durable dispatch | Reuse validated backend kind, immutable binding, opaque remote-run ID and shared reconciliation/callback/publication operations | Response-loss, orphan, stale callback and uncertain-write campaign |
| 061-I | Identity and operations | Least-privilege roles, workload identity, network policy, scoped cleanup | Cross-scope denial, revoked credentials, outage, quotas and cleanup proof |
| 061-Q | Qualification | One relay topology and one ECS reference deployment; separate timer/executor matrices and unsupported combinations | Installed package and isolated account/region qualification |

## Delivery Sequence

1. Freeze one Scheduler/Lambda transport and one ECS/Fargate reference deployment,
   supported versions/regions, trust/network policy and explicit unsupported combinations.
2. Qualify scheduled delivery to the 0.59 receiver independently of executors.
3. Prove accepted-reference execution through an installed ECS/Fargate worker.
4. Prove ECS is the second concrete consumer of the same generic dispatch
   operations, preserving Prefect migration compatibility and adding no AWS fields
   to shared core records. Inject worker/callback/credential/effect failures.
5. Publish independent timer/executor decisions, recipes, cleanup proof and the
   demand criteria for any later executor; Batch is not required for this exit.

## Exit Gates

- **AC061-001:** Optional installation keeps AWS SDKs out of core and supports
  schedule-only and execution-only configuration independently.
- **AC061-002:** Schedule retries/relay retries/redrive preserve occurrence
  identity and authorization; unsupported recurrence fails before activation.
- **AC061-003:** The one ECS/Fargate adapter executes actual accepted pipelines
  through pinned installed workers and publishes canonical effects/results.
  The same generic dispatch operations serve Prefect and ECS without per-vendor
  core fields or a copied managed runtime.
- **AC061-004:** Lost submit responses, crashes, stale callbacks, and remote
  retry defaults cannot cause unfenced publication or blind repeated effects.
- **AC061-005:** Cross-scope identity/override attempts fail; secrets resolve only
  at authorized runtime boundaries and remain absent from persistent artifacts.
- **AC061-006:** Live cancellation, polling recovery, resource cleanup, upgrades,
  and service outages preserve durable evidence within the advertised matrix.

## Required Release Evidence And Decisions

Map AC061-001–006 to per-service live tests, real PostgreSQL execution/effect
traces, IAM/redaction reports, install/version matrices, and cost/quota/cleanup
runbooks. AWS/security maintainers own relay, regions, IAM, and task/job bindings
before implementation. Fakes do not qualify live support; a scheduler gate cannot
close the ECS execution gate. Include shared outbound DNS/connect conformance.
Batch may be considered only for a named workload ECS cannot adequately serve,
with an owner, dependency/operational cost decision and its own live/failure gates.
It has no assigned release and is not a 0.61 completion requirement. Any expansion
requires the roadmap and owning plans to be updated first.
