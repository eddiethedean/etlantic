# What's New in ETLantic 0.51

> **Status: ETLantic 0.51.0 release candidate; publication pending.**

ETLantic 0.51.0 ships the first closed foundation for adaptive heterogeneous
planning without claiming an adaptive planner or runtime. It adds opt-in
Profile policy, immutable placement-target descriptors, a fingerprinted
`etlantic.plan/2` document model, and the built-in run-report metadata
namespace migration.

## Upgrade impact

- Pin core and every first-party plugin to `0.51.0`; plugin requirements use
  `etlantic>=0.51.0,<0.52`.
- Existing explicit profiles remain the executable path and continue to use
  canonical `etlantic.plan/1` documents.
- New writers emit built-in step metrics under `etlantic.dataframe`,
  `etlantic.sql`, `etlantic.spark`, and `etlantic.spark_schema`. The `/1`
  report reader migrates the matching 0.50 bare aliases without warnings and
  preserves a namespaced value when both forms are present.
- Adaptive Profile fields and `/2` plan documents can be authored, inspected,
  serialized, and verified. Adaptive planning and execution remain
  unavailable and fail closed.

See [Migration 0.50 → 0.51](../11_DEVELOPMENT/MIGRATION_0_50_TO_0_51.md)
and the [0.51 exit gate](../11_DEVELOPMENT/EXIT_GATE_0_51.md).

## Available foundation

| Surface | 0.51.0 status |
|---|---|
| Existing explicit Profile and `etlantic.plan/1` | Available and executable |
| Adaptive Profile policy and `PlacementTarget` | Available for opt-in contract authoring |
| `AdaptivePipelinePlan` / `etlantic.plan/2` | Available for authoring, inspection, deterministic serialization, and verification |
| Built-in step-metadata namespace migration | Available; 0.50 aliases remain readable |
| Adaptive candidate discovery and solver | Unavailable; planning rejects with `PMADP221` |
| Physical-DAG execution | Unavailable; consumers reject `/2` before external I/O |
| Adaptive external compilation, orchestration, federation, and streaming | Unavailable |

The frozen 0.50 portable transformation matrix remains the execution baseline.
Native `@Transformation.implementation(engine)` bodies remain explicit,
engine-specific `/1` escape hatches and never become adaptive candidates.
