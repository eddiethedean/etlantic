---
status: published
since: "0.55.0"
current_minor: "0.57"
audience: adopter
---

# What's new in 0.55

> **Status: ETLantic 0.55.0 is the published Beta release.**

ETLantic 0.55 adds an Experimental, evidence-qualified subset of data-first
authoring. Users can infer a bounded schema from records, CSV, JSON, Pandas,
and Polars sources, apply portable transformations, inspect targets, and check
whether proposed output is compatible with a target. The existing typed
`Data` / `Transformation` / `Pipeline` API remains supported and unchanged.

## What is included

- Bounded inference with explicit limits, hints, provenance, and actionable
  diagnostics. One-shot inputs retain their inspected prefix for a single
  replay; unbounded materialization is not implied.
- Portable schema transfer through qualified projections, filters, casts,
  arithmetic, scalar functions, joins, unions, and aggregates.
- Read-only target observations with revision checks, write compatibility,
  and explicit output-model proposals.
- Versioned, JSON-safe, row-free observations and durable definitions for
  stable, rebindable source bindings.

## Qualification boundary

This feature remains **Experimental**. The exact qualified surfaces are listed
in the [0.55 evidence index](../11_DEVELOPMENT/evidence/inference_0_55/index.json)
and the [0.55 exit gate](../11_DEVELOPMENT/EXIT_GATE_0_55.md).

In this release, PySpark, DataFusion, and SQL/DuckDB sources are qualified for
metadata inspection only. Parquet qualification covers bounded footer
inspection and read-only source binding. Schema-registry inspection covers
read-only JSON Schema and Avro subject documents; Protobuf and live service
availability are outside the evidence scope. Qualified write-mode behavior is
limited to the transactional SQLite reference target. Other provider-backed
replay and write modes need their own qualification.

The 0.54 adaptive execution evidence is pinned to exact package versions and
does not qualify 0.55. Adaptive execution remains fail-closed in this release
until version-matched 0.55 adaptive evidence passes its qualification gate.

No target is mutated during inspection, planning, or proposal. Target
constraints remain separate from observed source facts, and source rows,
sampled values, and credentials are not stored in plans, reports, definitions,
or schema history.

## Upgrade impact

No migration is required for existing class-authored pipelines. Core and
first-party packages use the published lockstep `0.55.0` line; install matching
versions. See [Migration 0.54 → 0.55](../11_DEVELOPMENT/MIGRATION_0_54_TO_0_55.md)
for adoption guidance.
