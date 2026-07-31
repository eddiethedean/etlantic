---
title: ETLantic 0.41 Implementation Plan
description: Implementation-grade plan for durable submission, state, replay, and preview workspaces.
plan_status: current
plan_last_reviewed: 0.41.0-dev
---

# ETLantic 0.41 Implementation Plan

Phase 0.41 makes accepted work, execution ownership, checkpoints, and replay
durable across API and worker failure. It consumes the 0.39 API and 0.40 registry
without weakening their scope boundaries.

The provider-neutral CP3 contracts and in-memory conformance provider are now
implemented. Transactional database/broker adapters, multi-host chaos evidence,
and the release exit gate remain required before this phase can be released.

## Outcome

A transactionally accepted submission is delivered to a leased, fenced
execution host; attempts, events, checkpoints, artifacts, and external effects
have enough provenance to resume, replay, repair, or fail safely. Preview
workspaces are durable, bounded, expiring forks rather than ad hoc flags.

## Prerequisites And Non-Goals

- 0.40 registry migrations, scope keys, and recovery gates are closed.
- Submission, attempt, checkpoint, and artifact identities reuse registry scope.
- Exactly-once marketing claims are out of scope. ETLantic records normalized
  effect state and reports unknown commit outcomes rather than guessing.
- Broker and persistence vendors remain provider choices, not core requirements.

## Workstreams

| ID | Workstream | Deliverables | Completion evidence |
|---|---|---|---|
| 041-S | Transactional submission | Admission record, scoped idempotency, transactional outbox, broker dispatcher | Crash-point matrix between API commit, outbox publication, and broker delivery |
| 041-H | Execution host | Lease, fencing token, heartbeat, cancellation, attempt history, stale-owner rejection | Multi-host lease expiry and stale publish tests |
| 041-C | State providers | Cursor, watermark, checkpoint, partition, snapshot, compare-and-swap, atomic acknowledge protocols | Provider conformance, corruption, conflict, and migration suite |
| 041-R | Reproducibility | Immutable plan/revision/plugin/policy linkage; secret-free attempt context; exact artifact selection | Replay fixture proving the same declared inputs and differences are explainable |
| 041-E | External effects | Normalized pending/committed/failed/unknown effect record; idempotent sink hooks | Unknown-commit tests that fail closed without duplicating effects |
| 041-B | Repair/backfill | Resume, replay, repair, partition backfill, dry-run state preview, baseline linkage | Partial-failure recovery and bounded backfill fixtures |
| 041-V | Preview workspaces | Fork provenance, TTL, cleanup, quotas, promotion inputs, diff and shadow-run records | Expiry/cleanup, stale fork, quota, and no-production-authority tests |
| 041-O | Operations | Queue/lease metrics, stuck-work diagnostics, state migration and recovery runbooks | Failure injection, capacity results, and operator drill |

## Delivery Sequence

1. Freeze submission/outbox/attempt/lease/event state machines and invariants.
2. Implement transactional acceptance and dispatcher crash recovery.
3. Implement execution-host leasing, fencing, heartbeats, and cancellation.
4. Add state-provider conformance, checkpoints, and external-effect records.
5. Add replay, repair, backfill, dry-run state, and preview workspaces.
6. Run chaos tests across API, broker, host, database, checkpoint, and sink edges.

## Exit Gates

- Accepted work survives API loss, broker redelivery, dispatcher restart, and
  execution-host loss without being silently dropped or run by a stale owner.
- Scoped idempotency suppresses duplicate submissions and deliveries without
  conflating tenants, workspaces, revisions, or requested operations.
- Checkpoint compare-and-swap and atomic acknowledgement prevent a failed or
  stale attempt from advancing durable state.
- Replay selects exact immutable inputs and explains every permitted difference.
- An unknown external commit is surfaced as unknown and requires explicit repair;
  it is never automatically treated as safe to repeat.
- Preview forks expire and clean up only their own scoped resources, respect
  quotas, record staleness, and grant no implicit production authority.
- State migrations and corrupted-state recovery preserve auditability and fail
  closed when compatibility cannot be established.

## Required Release Evidence

- Submission/outbox crash-point and duplicate-delivery matrix.
- Lease/fencing chaos report with at least two execution hosts.
- State-provider conformance and corruption-recovery results.
- Replay/repair/backfill provenance records.
- Preview TTL, cleanup, staleness, and authority matrix.
