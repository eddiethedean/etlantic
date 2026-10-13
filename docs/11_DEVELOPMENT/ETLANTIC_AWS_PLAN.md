---
title: ETLantic AWS Integration Plan
description: Independent AWS scheduling and execution adapters over canonical ETLantic runtime contracts.
plan_status: planned
plan_last_reviewed: 2026-10-12
---

# ETLantic AWS Integration Plan

**Status: planned; phase [0.61](IMPLEMENTATION_PLAN_0_61.md).** The proposed
`etlantic-aws` package is optional and unavailable until its own gates pass.
See the [runtime plan](ETLANTIC_RUNTIME_PLAN.md) for source provenance, shared
contracts, and the four-phase program.

## Outcome And Dependencies

AWS can supply a schedule backend, an execution backend, or both independently.
It can send the same trigger contract as Connect to any compatible authorized
HTTPS receiver, including Data Mover. It can also execute canonically admitted
work on independently managed compute. Neither mode requires Posit Connect,
FastAPI, or Data Mover; AWS SDKs never enter ETLantic core.

This phase owns one EventBridge Scheduler → scoped Lambda → HTTPS transport
and one ECS/Fargate executor, qualified independently. This is the accepted
F12 narrowing in the [package consolidation plan](PACKAGE_SCOPE_CONSOLIDATION_PLAN.md).
Batch is a demand-gated unscheduled candidate, not part of the 0.61 exit. Broad
Kubernetes/managed Spark hardening, cross-cloud secret/connector packs, Helm,
and enterprise provider selection remain [0.65](IMPLEMENTATION_PLAN_0_65.md).
S3 data access stays in `etlantic-s3`; secret providers use the existing secret
protocol and separate optional SDK packages. No general infrastructure framework
or cloud-wide orchestration scope belongs in `etlantic-aws`.

## Scheduling Path

EventBridge Scheduler invokes AWS service APIs through templated or universal
targets; it must not be modeled as an arbitrary direct HTTPS client. The initial
proposed transport is Scheduler → scoped Lambda relay → configured HTTPS
receiver. Other relay topologies require demonstrated demand and a separate
reviewed scope/qualification decision. See [Scheduler targets](https://docs.aws.amazon.com/scheduler/latest/UserGuide/managing-targets.html)
and [Lambda scheduling](https://docs.aws.amazon.com/lambda/latest/dg/with-eventbridge-scheduler.html).

The relay only delivers triggers and handles bounded delivery failure. It never
executes ETL. Apply existing outbound policy/conformance to destination, redirects,
timeouts, byte bounds and redaction; prove DNS/connect behavior and explicit
trusted private-network support rather than inventing another URL policy. Preserve the intended occurrence identity across Scheduler and
relay retries; invocation/attempt IDs and delivery times cannot become new
occurrences. Model retry budgets, deadlines, DLQ disposition, redrive, timezone,
DST, flexible windows, misfires, and overlap explicitly. Unsupported semantics
fail before activation. A redrive preserves identity and must satisfy replay
and authorization rules, rather than bypass them.

## Execution Path

1. Canonical ETLantic services prepare and accept a run, binding scope, plan,
   resource references, trusted code/runtime versions, and execution placement.
2. Durable dispatch submits a bounded immutable accepted reference to a pinned
   ECS/Fargate task configuration. Caller-controlled images,
   commands, backend factories, credentials, and arbitrary overrides are denied.
3. The installed worker reconstructs trusted runtime and claims exactly that
   work through existing public targeted execution, heartbeat, fencing,
   cancellation, recovery, and publication services.
4. Provider status/callbacks correlate remote jobs to canonical attempts. Polling
   repairs missed callbacks; remote exit status cannot substitute for ETL result
   publication or external-effect reconciliation.

Use the consolidated 0.59 managed implementation and existing accepted-reference
protections. Shared dispatch records/operations use validated backend kind,
immutable deployment binding and opaque remote-run ID; AWS owns API calls,
binding verification and remote-state translation. Prove this as the second
concrete adapter without AWS-specific fields or another store family in core.
Do not copy Prefect implementation or infer AWS support from Prefect qualification. Provider/queue retry defaults must not blindly rerun effects.
Unknown writes require reconciliation before retry. Lost submission responses
must reconcile through durable dispatch identity before creating another job.

## Deliverables And Gates

| Workstream | Required evidence |
|---|---|
| Scheduler and HTTPS relay | Live schedule lifecycle, exact recurrence matrix, duplicate/lost-response handling, failed delivery and identity-preserving redrive |
| ECS/Fargate execution | Installed pinned worker, actual pipeline effects/results, scope and image validation, cancellation, task loss and restart |
| Identity and resources | Least-privilege roles, workload identity, secret references, network policy, rotation/revocation and denied cross-scope operations |
| Operations | Bounded provider-owned cleanup, orphan reconciliation, quotas/costs/regions, deployment/update/rollback and service outage drills |

First qualify a static-batch `/1` matrix with PostgreSQL-backed durable state.
Adaptive `/2`, dynamic control, streaming, and other AWS services stay rejected
unless separately scoped and qualified. Publish independent timer/executor gates
for one reference deployment; a working scheduler does not qualify ECS. Document
unsupported combinations instead of a Cartesian product of every host and backend.

Batch may be proposed only for a concrete workload that needs its queue/job
semantics, with a maintainer, measured operational/dependency cost and live
qualification plan over the same shared dispatch. No release is reserved and
Batch is not a 0.61 completion requirement. New relay variants follow the same
demand and scope-change gate.

Production plugins/resources are allowlisted; IAM cannot expand application
authorization. Plans, images, task/job parameters, reports, logs, and fixtures
contain references and bounded metadata only, never resolved credentials or
source rows. Store references to protected diagnostic artifacts rather than
unbounded cloud logs in results.

AWS and security maintainers freeze relay topology, supported regions, role
permissions, network reachability, and execution support matrices before the
pilot. Review on changes to service APIs, retry behavior, runtime contracts,
or release qualification. Required release artifacts include independently
installable wheels, reproducible deployment recipes, per-service live failure
reports, cleanup proof, and the shared conformance results.
