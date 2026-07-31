---
title: ETLantic 0.47 Implementation Plan
description: Implementation-grade plan for remote execution federation.
plan_status: current
plan_last_reviewed: 0.37.0
---

# ETLantic 0.47 Implementation Plan

Phase 0.47 separates control-plane submission from remote execution while
preserving signed-plan identity, scoped authority, durable state, policy,
reliability evidence, 0.46 dynamic-control and streaming-error semantics, and
normalized external-effect outcomes.

## Outcome

A control plane can negotiate with a remote execution host, place a signed,
content-addressed workload on an authorized runtime, resume events and reports
after disconnect, cancel or recover fenced attempts, and compare results across
runtime providers without embedding FastAPI into worker processes.

## Prerequisites And Non-Goals

- 0.43 control-plane support and 0.46 state/effect compatibility gates are closed.
- The remote protocol carries references and bounded artifacts, never ambient
  credentials or undeclared authority.
- Kubernetes and managed Spark are reference providers, not core dependencies.
- Network delivery does not imply exactly-once effects; unknown remote commit
  states remain explicit and governed by repair policy.

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

## Delivery Sequence

1. Freeze protocol state machines, trust negotiation, and recovery invariants.
2. Build an in-process fake remote host for deterministic protocol conformance.
3. Add signed artifact transfer, resumable events, fencing, and disconnect repair.
4. Implement Kubernetes, then one managed Spark reference provider.
5. Add placement evidence, operations, compatibility, and capacity qualification.
6. Run cross-runtime semantic and failure campaigns using the same signed plan.

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

## Required Release Evidence

- Remote protocol state-machine and version-skew report.
- Cross-runtime semantic/effect comparison.
- Disconnect, lease, fencing, cancellation, and unknown-commit chaos matrix.
- Artifact signature/transfer and credential-redaction report.
- Provider isolation, workload-identity, and cleanup evidence.
