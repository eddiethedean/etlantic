---
title: ETLantic 0.53 Implementation Plan
description: Implementation-grade plan for qualified local adaptive physical-DAG execution.
plan_status: current
plan_last_reviewed: 0.51.0
---

# ETLantic 0.53 Implementation Plan

Phase 0.53 makes the physical DAG planned in 0.52 executable for a deliberately
small local static-batch envelope. It owns increment I2 and Phases 8–9 of the
[adaptive program plan](IMPLEMENTATION_PLAN_0_51.md). The implementation may
execute only fixture-qualified Local, Polars, and Pandas combinations; public
availability is withheld until the independent 0.54 qualification gate.

## Outcome

The local runtime atomically admits a complete `etlantic.plan/2` document,
schedules only its physical dependencies, dispatches the exact stored target
and unit kinds, and preserves retry, cancellation, cleanup, validation,
publication, and logical-step reporting semantics.

## Scope

| Workstream | Deliverable | Completion evidence |
|---|---|---|
| 053-A | Whole-DAG live admission | Every mutable dependency rechecked before any resource acquisition or I/O |
| 053-P | Physical execution protocol | Versioned seven-kind executor contract and fail-closed dispatch |
| 053-S | Physical scheduler | Readiness derived only from stored physical dependencies with bounded concurrency |
| 053-L | Local adapters and lifecycle | Local, Polars, and Pandas compute/handoff paths plus retry, cancellation, cleanup, and reconciliation |
| 053-R | Reports and attribution | Namespaced built-in metadata and complete fused/logical-step attribution |
| 053-D | Differential semantics | Fixture-gated comparison against explicit `/1` behavior for outputs and lifecycle |

## Acceptance Criteria

- **AC-053-01 — Atomic admission:** Any trust, version, capability, contract,
  policy, resource, authorization, selection, or evidence drift starts zero
  physical units and performs no external I/O.
- **AC-053-02 — Runtime authority:** Readiness and dispatch come exclusively
  from the stored physical DAG; the runtime never performs placement or silently
  falls back to logical scheduling.
- **AC-053-03 — Lifecycle:** Failure, retry, timeout, cancellation, transfer,
  collection, materialization, reuse, validation, cleanup, and publication
  preserve the explicit baseline or fail earlier safely.
- **AC-053-04 — Publication safety:** Publication commits once or records an
  explicit unknown outcome requiring reconciliation; no ambiguous retry can
  duplicate an external effect.
- **AC-053-05 — Attribution:** Fused units retain per-logical-step lifecycle and
  report attribution, and new writers emit only namespaced built-in metadata.
- **AC-053-06 — Bounded envelope:** Only the named Local/Polars/Pandas static-
  batch fixture combinations can run. Every other `/2` consumer or topology
  rejects before I/O.

## Delivery Sequence

1. Freeze and implement the physical-unit executor protocol.
2. Add whole-DAG admission and verify zero-I/O failure behavior.
3. Add the dependency-driven physical scheduler.
4. Implement fixture-gated Local, Polars, and Pandas adapters and handoffs.
5. Complete lifecycle, reporting, failure-injection, and differential tests.

## Exit Gates

- The adaptive-program ACs AC-016 through AC-019 and execution portions of
  AC-021 through AC-023 are verified.
- Every admission failure is proven to start zero units and perform zero reads,
  staging, mutation, or publication.
- Failure injection covers each physical-unit boundary, unsafe retry,
  cancellation during handoff, cleanup, and unknown publication outcomes.
- Adaptive and explicit fixtures agree on outputs, validation, lifecycle,
  attribution, cleanup, and publication results.
- Execution remains capability-gated and is not documented as Available before
  the 0.54 release decision.

## Required Release Evidence

- Whole-DAG admission and unsupported-consumer report.
- Physical scheduler and executor-protocol conformance report.
- Lifecycle, cleanup, retry, cancellation, and publication campaign.
- Adaptive-versus-explicit differential report.
- Namespaced report-metadata and fused-attribution compatibility report.

## Explicit Non-Scope

- General third-party adaptive availability or maturity inheritance.
- SQL, PySpark, DataFusion, DuckDB, remote, durable, federated, streaming, or
  external-orchestrator `/2` execution.
- Runtime replanning, speculative execution, or telemetry-driven placement.
