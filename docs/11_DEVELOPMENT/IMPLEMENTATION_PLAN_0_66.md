---
title: ETLantic 0.66 Implementation Plan
description: Implementation-grade incubation plan for a standalone TransformationModel package.
plan_status: current
plan_last_reviewed: 2026-10-12
---

# ETLantic 0.66 Implementation Plan

Phase 0.66 conditionally incubates `TransformationModel` as a standalone typed package
under `packages/transformationmodel`. The
[TransformationModel plan](TRANSFORMATIONMODEL_PLAN.md) remains the governing
architecture, and [DTCS](../04_TRANSFORMATIONS/DTCS.md) remains the semantic
authority throughout incubation.

## Outcome

An independent Python consumer can model typed transformations and references,
round-trip supported DTCS deterministically, inspect diagnostics/diffs/fidelity,
and integrate through a stable public protocol without importing ETLantic,
execution engines, backend adapters, orchestration, secrets, or external effects.

This phase moves from 0.62 to 0.66 after insertion of the
[0.59–0.62 scheduling and execution integration program](ETLANTIC_RUNTIME_PLAN.md).
Its modeling outcome remains conditional on the accepted
[package consolidation gates](PACKAGE_SCOPE_CONSOLIDATION_PLAN.md).

## Prerequisites And Non-Goals

- Before creating a wheel, identify an independent consumer, the exact reusable
  authoring code to move and the duplicate implementation to retire. If the
  package would only wrap unchanged owners, keep module organization and defer it.
- The existing DTCS boundary, ETLantic authoring surface, and plugin ecosystem
  have characterization tests before extraction begins.
- Characterize the 0.55 inferred-schema transfer rules and generated-contract
  evidence before extracting reusable transformation authoring. The 0.55
  feature does not depend on this incubating package.
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
| 066-B | Boundary characterization | Independent consumer/value decision, import map, DTCS corpus, named authoring extraction and duplicate-retirement map | Baseline characterization suite passing before moves |
| 066-M | Public model | Typed transformation, reference, expression, capability, diagnostic, diff, and fidelity protocols | Independent API/type tests and `py.typed` verification |
| 066-D | DTCS interop | Public DTCS delegation for parsing/canonicalization/validation/fingerprints plus authoring translation and explicit fidelity | Cross-platform golden round-trip corpus |
| 066-E | Extraction | Incremental authoring move and deletion of migrated duplication; compatibility adapters delegate to one owner; no circular/private dependency | Dependency-boundary and import-graph enforcement |
| 066-P | Plugin compatibility | Stable extension protocol, conformance, version/deprecation rules, third-party fixture | External plugin compatibility matrix |
| 066-I | ETLantic integration | ETLantic consumes the public package for qualified paths while retaining guarded fallback during incubation | Full ETLantic suite plus before/after semantic comparison |
| 066-R | Release engineering | Independent package metadata, semver policy, supported Python matrix, docs/examples, publish rehearsal | Clean-environment build/install and independent consumer demo |

## Delivery Sequence

1. Characterize current DTCS semantics, imports, fingerprints, diagnostics, and
   plugin behaviors before changing ownership.
2. Prove a named independent consumer and extraction/duplicate-retirement value
   before freezing the minimal public protocol and creating a package.
3. Implement the package and deterministic DTCS interop beside existing code.
4. Migrate qualified authoring paths through compatibility adapters and delete
   the migrated implementation from its old owner; parallel incubation code has
   a recorded retirement gate and cannot become a second normative DTCS authority.
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
- Named migrated authoring duplication is removed; compatibility exports call
  one implementation. No second DTCS parser, canonicalizer or normative validator
  exists. Any change from direct to transitive ETLantic dependency on `dtcs`
  requires a separate evidence-backed decision; DTCS semantic authority remains.

## Required Release Evidence

- Independent-consumer/value decision and before/after ownership/duplicate-
  retirement report, plus import/dependency evidence.
- Cross-platform DTCS round-trip/fingerprint corpus.
- ETLantic semantic regression comparison.
- Third-party plugin compatibility matrix.
- Independent consumer and clean publish/install rehearsal.
