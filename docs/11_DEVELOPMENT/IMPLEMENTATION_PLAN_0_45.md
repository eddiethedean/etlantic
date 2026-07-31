---
title: ETLantic 0.45 Implementation Plan
description: Implementation-grade plan for the planner and optimization SDK.
plan_status: current
plan_last_reviewed: 0.37.0
---

# ETLantic 0.45 Implementation Plan

Phase 0.45 opens a stable optimization-pass SDK while preserving the logical
plan, policy, schema, reliability, and backend-capability boundaries established
by earlier releases.

## Outcome

Third-party and built-in optimization passes can propose deterministic physical
plan changes, explain their evidence and expected benefit, prove semantic and
security equivalence, and participate in plan comparison without gaining runtime
authority or silently changing policy-visible behavior.

## Prerequisites And Non-Goals

- Stable logical/physical plan identity, capability reporting, policy decisions,
  and plan-diff artifacts are available from 0.42–0.44.
- Optimization is advisory until proof and policy checks accept a candidate.
- The SDK does not promise a universal cost model or permit backend-specific
  internals to leak into core logical semantics.
- An optimization pass cannot execute data access, resolve secrets, or mutate
  registry, state, schema, or reliability baselines.

## Workstreams

| ID | Workstream | Deliverables | Completion evidence |
|---|---|---|---|
| 045-P | Pass protocol | Versioned pass metadata, prerequisites, candidates, proof obligations, deterministic ordering, diagnostics | Third-party pass conformance and compatibility tests |
| 045-S | Statistics/evidence | Cardinality, partitioning, ordering, locality, reuse, freshness, confidence, provenance, expiry | Stale/missing/conflicting evidence tests |
| 045-C | Cost and selection | Rule-based and statistical cost providers; multi-objective selection; budget constraints | Golden selection fixtures and sensitivity analysis |
| 045-R | Rewrites | Pushdown, pruning, fusion, materialization, reuse, repair/backfill selection, cross-backend boundaries | Semantic equivalence and capability rejection suites |
| 045-E | Explanation | Candidate list, chosen/rejected reasons, expected benefit, proof, policy result, plan diff | Stable machine/human-readable explanation snapshots |
| 045-H | Shadow validation | Baseline/candidate comparison, shadow plans, bounded trial evidence, regression thresholds | Representative workload and adversarial regression corpus |
| 045-O | SDK lifecycle | Packaging, plugin allowlist integration, deprecation/version policy, author guide | External example pass and multi-version compatibility matrix |

## Delivery Sequence

1. Freeze proof obligations and pass protocol before implementing rewrites.
2. Build deterministic evidence/statistics and cost-provider interfaces.
3. Implement reference passes one class at a time with semantic fixtures.
4. Add explanation and plan-diff artifacts to CLI, API, and IDE surfaces.
5. Add shadow comparison, regression thresholds, and third-party conformance.
6. Publish SDK lifecycle rules only after external example passes qualify.

## Exit Gates

- Every candidate records inputs, evidence freshness/confidence, expected benefit,
  semantic proof, policy result, backend capability, and chosen/rejected reason.
- Re-running the same pass set on the same plan and evidence is deterministic.
- Missing, stale, or conflicting statistics degrade to a safe choice and stable
  diagnostic rather than an unjustified rewrite.
- No pass crosses a schema, policy, residency, classification, side-effect,
  idempotency, ordering, or backend capability boundary without proof.
- Reference and third-party passes pass semantic, security, determinism,
  compatibility, and resource-budget conformance.
- CLI, API, and IDE compare baseline and optimized plans using the same immutable
  artifacts and explanation schema.

## Required Release Evidence

- Pass SDK compatibility and conformance report.
- Optimization proof/diagnostic golden corpus.
- Workload cost/benefit and regression analysis.
- Policy and capability boundary adversarial suite.
- External example-pass build and upgrade transcript.

