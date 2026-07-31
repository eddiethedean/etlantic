---
title: ETLantic 0.52 Implementation Plan
description: Implementation-grade incubation plan for a standalone TransformationModel package.
plan_status: current
plan_last_reviewed: 0.37.0
---

# ETLantic 0.52 Implementation Plan

Phase 0.52 incubates `TransformationModel` as a standalone typed modeling package
under `packages/transformationmodel`. The
[TransformationModel plan](TRANSFORMATIONMODEL_PLAN.md) remains the governing
architecture, and [DTCS](../04_TRANSFORMATIONS/DTCS.md) remains the semantic
authority throughout incubation.

## Outcome

An independent Python consumer can model typed transformations and references,
round-trip supported DTCS deterministically, inspect diagnostics/diffs/fidelity,
and integrate through a stable public protocol without importing ETLantic,
execution engines, backend adapters, orchestration, secrets, or external effects.

## Prerequisites And Non-Goals

- The existing DTCS boundary, ETLantic authoring surface, and plugin ecosystem
  have characterization tests before extraction begins.
- ETLantic keeps its direct DTCS dependency until the standalone package proves
  semantic completeness and lifecycle stability; extraction is not a flag-day
  replacement.
- The package models transformations only. Execution engines, data access,
  state/checkpoints, connectors, secrets, policy, orchestration, and medallion
  abstractions are out of scope.
- Lossy or unsupported DTCS constructs remain explicit and never round-trip as
  silently changed semantics.

## Workstreams

| ID | Workstream | Deliverables | Completion evidence |
|---|---|---|---|
| 052-B | Boundary characterization | Import/dependency map, DTCS semantic corpus, ETLantic/plugin usage inventory, extraction ADRs | Baseline characterization suite passing before moves |
| 052-M | Public model | Typed transformation, reference, expression, capability, diagnostic, diff, and fidelity protocols | Independent API/type tests and `py.typed` verification |
| 052-D | DTCS interop | Deterministic import/export, canonicalization, fingerprint, version negotiation, explicit lossy handling | Cross-platform golden round-trip corpus |
| 052-E | Extraction | Incremental move from ETLantic internals; compatibility adapters; no circular or private dependency | Dependency-boundary and import-graph enforcement |
| 052-P | Plugin compatibility | Stable extension protocol, conformance, version/deprecation rules, third-party fixture | External plugin compatibility matrix |
| 052-I | ETLantic integration | ETLantic consumes the public package for qualified paths while retaining guarded fallback during incubation | Full ETLantic suite plus before/after semantic comparison |
| 052-R | Release engineering | Independent package metadata, semver policy, supported Python matrix, docs/examples, publish rehearsal | Clean-environment build/install and independent consumer demo |

## Delivery Sequence

1. Characterize current DTCS semantics, imports, fingerprints, diagnostics, and
   plugin behaviors before changing ownership.
2. Freeze the minimal standalone public protocol and prohibited dependency list.
3. Implement the package and deterministic DTCS interop beside existing code.
4. Migrate qualified ETLantic paths incrementally through compatibility adapters.
5. Qualify third-party plugin behavior and independent consumers.
6. Decide promotion, further incubation, or rollback from evidence; do not remove
   direct DTCS authority merely to meet a date.

## Exit Gates

- A clean independent consumer installs and uses `transformationmodel` without
  ETLantic or any execution/backend/orchestration dependency.
- Supported DTCS import/export, canonical fingerprints, diagnostics, and diffs
  are deterministic across the supported operating-system and Python matrix.
- Every unsupported or lossy construct has a stable fidelity result and cannot be
  mistaken for an exact round trip.
- The full ETLantic test suite passes through the public package boundary with
  semantic comparison to the pre-extraction baseline.
- The public protocol has semver, compatibility, deprecation, Python support, and
  `py.typed` commitments and does not depend on ETLantic internals.
- The package contains no engine, connector, secret, state, policy,
  orchestration, external-effect, or medallion concern.
- Promotion away from direct DTCS authority occurs only through a separate,
  evidence-backed decision after incubation.

## Required Release Evidence

- Boundary/import dependency report.
- Cross-platform DTCS round-trip/fingerprint corpus.
- ETLantic semantic regression comparison.
- Third-party plugin compatibility matrix.
- Independent consumer and clean publish/install rehearsal.
