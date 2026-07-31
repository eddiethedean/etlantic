---
title: ETLantic 0.49 Implementation Plan
description: Implementation-grade plan for brownfield metadata bridges and orchestration compilers.
plan_status: current
plan_last_reviewed: 0.37.0
---

# ETLantic 0.49 Implementation Plan

Phase 0.49 lets existing projects adopt ETLantic incrementally through static
metadata readers, semantic comparison, safe skeleton generation, and
orchestration compilers. The
[adoption ecosystem plan](ADOPTION_ECOSYSTEM_PLAN.md) governs brownfield and
interoperability boundaries.

## Outcome

Teams can import metadata from real dbt and ETL projects without executing their
code, identify what ETLantic can and cannot preserve, generate reviewable
skeletons, compile qualified pipelines to Dagster, Prefect, or Argo, and compare
old and new paths side by side without a flag-day migration.

## Prerequisites And Non-Goals

- Stable registry identities, semantic plan diff, generated-code preservation,
  and conformance protocols from earlier phases are available, including 0.46
  bounded dynamic-control identities and capability rules.
- Readers parse supported static artifacts only; they do not execute Jinja,
  macros, Python project code, hooks, or package installation.
- External dbt or orchestration ownership can remain authoritative. Import does
  not silently transfer ownership to ETLantic.
- Compilers reject semantics they cannot preserve; they do not approximate
  retries, partitions, schedules, assets, state, policy, dynamic mapping,
  branch/failure/compensation behavior, or external effects.

## Workstreams

| ID | Workstream | Deliverables | Completion evidence |
|---|---|---|---|
| 049-D | dbt bridge | Manifest/catalog/run-results readers; model/source/test/exposure/metric metadata; stable identity mapping | Versioned public dbt artifact corpus with no code/Jinja execution |
| 049-M | ETL migration model | Sources, transforms, joins, filters, assertions, schedules, retries, partitions, dynamic maps/reduces, conditions, failure/compensation paths, effects, ownership, fidelity states | Representative framework-neutral migration fixtures |
| 049-G | Skeleton generation | Safe ETLantic project skeletons, TODO/fidelity markers, user-region preservation, repeatable regeneration | Golden output and incremental re-run tests |
| 049-S | Semantic diff | Source/field/transform/quality/state/schedule/dynamic-control/effect comparison with explicit unsupported/lossy results | Side-by-side fixture report and false-equivalence tests |
| 049-O | Orchestration compilers | Dagster definitions compiler, expanded Prefect deployment adapter, Argo workflow compiler, including truthful 0.46 dynamic-control lowering/rejection | Backend conformance and rejection matrix |
| 049-V | Side-by-side validation | Shadow/dual-run correlation, bounded result/quality/lineage comparison, cutover evidence | Realistic incremental migration campaign |
| 049-F | Fixture ecosystem | Versioned real-world-shape projects, anonymized metadata, compatibility matrix, contribution guide | CI corpus across supported artifact/backend versions |

## Delivery Sequence

1. Freeze fidelity vocabulary and the framework-neutral migration model.
2. Implement static dbt artifact readers against versioned fixtures.
3. Add semantic diff and safe skeleton generation before orchestration output.
4. Qualify Dagster, Prefect, and Argo compilers independently.
5. Add side-by-side validation and incremental ownership/cutover workflows.
6. Publish support matrices per source artifact and orchestration backend.

## Exit Gates

- Brownfield inspection performs no project code, Jinja, hook, macro, dependency,
  secret, network, or data execution.
- Every imported element has provenance and an exact, lossy, unsupported, or
  externally-owned fidelity status.
- Skeleton generation is deterministic, reviewable, preserves user regions, and
  does not overwrite existing ownership without an explicit operation.
- Semantic diff never labels unsupported behavior equivalent.
- Each compiler preserves declared semantics or fails before emitting a runnable
  artifact with a stable capability diagnostic.
- Supported map/reduce and conditional/failure/compensation constructs retain
  stable logical and expanded identities, bounds, retry/replay behavior, and
  report correlation on every compiler that claims them.
- A realistic project adopts ETLantic incrementally, retains an external owner
  where chosen, runs side-by-side, and produces cutover evidence without a
  flag-day rewrite.

## Required Release Evidence

- Static-reader no-execution security report.
- Import fidelity and semantic-diff corpus.
- Generator determinism/preservation report.
- Per-backend compiler conformance and rejection matrix.
- Incremental brownfield migration case study with side-by-side evidence.
