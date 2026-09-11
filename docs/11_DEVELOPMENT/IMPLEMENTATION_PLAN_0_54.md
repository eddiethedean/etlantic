---
title: ETLantic 0.54 Implementation Plan
description: Implementation-grade plan for adaptive conformance, qualification, and availability graduation.
plan_status: current
plan_last_reviewed: 0.51.0
---

# ETLantic 0.54 Implementation Plan

Phase 0.54 independently qualifies the adaptive planner and local physical
runtime delivered across 0.52 and 0.53. It owns increment I3 and Phase 10 of the
[adaptive program plan](IMPLEMENTATION_PLAN_0_51.md). Only rows backed by the
published evidence matrix become Available; all other combinations remain
Experimental or unavailable.

## Outcome

ETLantic publishes a reproducible, security-reviewed adaptive support matrix
for fixed Local-only, Polars-only, Pandas-only, Polars→Pandas, and
Pandas→Polars static-batch topologies, along with public provider conformance,
operational rollback guidance, and precise compatibility/non-claim docs.

## Scope

| Workstream | Deliverable | Completion evidence |
|---|---|---|
| 054-C | Public conformance | Provider-facing protocol, fixtures, and maturity rules that confer no authority by installation |
| 054-T | Fixed topology campaign | Single-target and bidirectional Polars/Pandas handoff fixtures with exact physical evidence |
| 054-D | Differential qualification | Output, validation, lifecycle, retry, cancellation, cleanup, attribution, and publication equivalence |
| 054-S | Security and compatibility | Allowlists, evidence drift, redaction, tamper, old-reader, and unsupported-consumer matrices |
| 054-O | Operations and rollback | Admission, disablement, drain, cleanup, reconciliation, and no-downgrade procedures |
| 054-G | Graduation decision | Dated matrix, weakest-link maturity, owners, residual risks, and go/no-go record |

## Acceptance Criteria

- **AC-054-01 — Public conformance:** Third-party providers can exercise the
  same behavior-level planning and execution contract without gaining maturity
  or production authority merely by passing a local test.
- **AC-054-02 — Fixed launch matrix:** Every claimed single-target and
  directional cross-target row passes exact topology, second-target dispatch,
  handoff, validation, cleanup, attribution, and publication verification.
- **AC-054-03 — Differential semantics:** The fixed matrix is equivalent to its
  explicit `/1` baseline for outputs and all material lifecycle outcomes.
- **AC-054-04 — Security and privacy:** Plans, diagnostics, reports, explain
  artifacts, and evidence contain no resolved secret or source row; production
  allowlists and policy domains fail closed.
- **AC-054-05 — Compatibility:** Existing explicit profiles and `/1` bytes stay
  unchanged, old readers fail safely, and every unqualified `/2` consumer
  rejects before external I/O.
- **AC-054-06 — Truthful graduation:** Documentation and machine-readable
  evidence advertise only the exact passing matrix and retain all explicit
  non-claims.

## Delivery Sequence

1. Freeze the public conformance protocol and exact launch matrix.
2. Run single-target and bidirectional handoff qualification.
3. Complete differential, security, compatibility, resource, and failure
   campaigns across the supported Python and operating-system matrix.
4. Publish concepts, operations, rollback, provider, migration, and API/CLI
   documentation with runnable examples.
5. Record the dated final matrix and release decision.

## Exit Gates

- Every adaptive-program acceptance criterion AC-001 through AC-023 has a
  reproducible passing artifact or an explicit non-applicable rationale.
- All required adaptive evidence artifacts are digest-bound to the released
  repository revision and contain no secrets or source rows.
- Full unit, integration, conformance, type, lint, formatting, packaging,
  documentation, compatibility, and security gates pass.
- No unresolved critical or high-severity security, correctness,
  compatibility, data-loss, or publication-safety finding remains in scope.
- The final decision names the exact Available rows, weakest-link maturity,
  residual risks, owners, and rollback trigger.

## Required Release Evidence

- Public adaptive-provider conformance report.
- Fixed single-target and directional handoff matrix.
- Adaptive-versus-explicit differential and failure-injection campaign.
- Security, redaction, compatibility, and unsupported-consumer matrix.
- Resource-budget and cross-platform determinism report.
- Documentation/example transcript and dated graduation decision.

## Explicit Non-Scope

- Adaptive availability beyond the rows that independently pass this gate.
- Native transformation bodies, SQL, PySpark, DataFusion, DuckDB, remote,
  durable, federated, streaming, runtime-expanded, or external-orchestrator
  `/2` execution unless separately qualified in a later release.
- Universal cost prediction, runtime replanning, telemetry feedback, or
  speculative execution.
