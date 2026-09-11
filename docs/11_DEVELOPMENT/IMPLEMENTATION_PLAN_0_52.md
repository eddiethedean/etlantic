---
title: ETLantic 0.52 Implementation Plan
description: Implementation-grade plan for adaptive placement planning, physical lowering, and explainability.
plan_status: current
plan_last_reviewed: 0.51.0
---

# ETLantic 0.52 Implementation Plan

Phase 0.52 delivers the planning half of the adaptive-execution program frozen
by [ADR-025](adr/ADR-025-ADAPTIVE-EXECUTION-AND-PHYSICAL-DAG.md). It builds on
the 0.51 Profile, report-compatibility, and closed `etlantic.plan/2` wire
foundation. The detailed algorithms, bounds, diagnostics, and acceptance
criteria remain governed by the
[adaptive program plan](IMPLEMENTATION_PLAN_0_51.md).

## Outcome

An opted-in static-batch pipeline can produce a deterministic, inspectable
`etlantic.plan/2` document containing a complete trusted target inventory,
candidate matrix, exact placement decision, connected regions, an authoritative
physical DAG, and stored explain/diff evidence. Adaptive `/2` execution remains
unavailable in this phase and every execution consumer must reject before I/O.

## Scope

This phase owns Phases 3–7 and increment I1 of the adaptive program plan:

| Workstream | Deliverable | Completion evidence |
|---|---|---|
| 052-I | Trusted inventory and evidence lineage | Deterministic authorize-before-load inventory with exact evidence digests |
| 052-C | Complete candidate matrix | One truthful record per selected node × eligible target, including every rejection |
| 052-S | Exact bounded solver | Independent-oracle equality, stable tie-breaking, permutation invariance, and deterministic resource limits |
| 052-P | Connected regions and physical lowering | Maximal compatible regions and a validated seven-kind physical DAG with complete attribution |
| 052-E | Explain and diff | Bounded, redacted Python/CLI/IDE/notebook projections derived only from the stored plan |
| 052-R | Rejection boundary | Local, compile, control-plane, remote, streaming, and unqualified consumers reject `/2` before external I/O |

## Acceptance Criteria

- **AC-052-01 — Trusted inventory:** Every admitted placement target is
  Profile-eligible, authorized before load, versioned, capability-complete, and
  bound to immutable qualification evidence; denied or drifted targets are not
  loaded or selected.
- **AC-052-02 — Candidate truthfulness:** The selected logical scope has a
  complete node × target matrix. Native bodies and unknown required evidence
  never become adaptive candidates.
- **AC-052-03 — Exact deterministic placement:** Identical semantic inputs
  produce the same complete assignment, objective tuple, explanation, and `/2`
  fingerprint, and the result matches the independent oracle within the frozen
  bounds.
- **AC-052-04 — Physical topology:** Regions and all seven physical-unit kinds
  preserve logical coverage, protected boundaries, directional handoffs,
  ownership, cleanup, retry, validation, and publication authority.
- **AC-052-05 — Explainability:** Explain and diff projections expose stored
  decisions and rejected alternatives consistently without replanning, while
  remaining deterministic, bounded, and free of secrets and source rows.
- **AC-052-06 — No execution claim:** Every `/2` execution or compilation
  consumer rejects before connector discovery, resource acquisition, reads,
  staging, or mutation.

## Delivery Sequence

1. Implement trusted inventory and immutable evidence lineage.
2. Materialize the complete candidate matrix before optimization.
3. Implement the exact bounded solver and independent oracle campaign.
4. Form connected regions and lower the validated physical DAG.
5. Project explain/diff from stored records and verify every rejection boundary.

## Exit Gates

- The adaptive-program ACs AC-007 through AC-015 and the planning portions of
  AC-021 through AC-023 are verified.
- Fixed node, target, candidate, work-unit, transient-byte, and explain-size
  boundaries accept their exact limit and reject the first excess.
- Planning is invariant under process hash seeds and semantic-preserving graph,
  registry, and component permutations.
- `/1` canonical bytes, fingerprints, planning, and execution remain unchanged.
- No `/2` unit can execute in this release, including through an old or optional
  consumer.

## Required Release Evidence

- Trusted-inventory and evidence-lineage conformance report.
- Candidate-matrix and exact-solver oracle report.
- Deterministic resource-budget report.
- Physical-DAG topology, attribution, tamper, and redaction report.
- Cross-surface explain/diff identity report.
- Unsupported-consumer before-I/O rejection matrix.

## Explicit Non-Scope

- Physical-unit execution, live admission, runtime scheduling, or publication.
- Adaptive native transformation bodies, streaming, or runtime-expanded graphs.
- SQL, PySpark, DataFusion, DuckDB, remote, federated, or external-orchestrator
  adaptive availability.
- Runtime replanning, telemetry feedback, trial execution, or cost prediction.
