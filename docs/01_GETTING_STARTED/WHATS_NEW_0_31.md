# What's New in ETLantic 0.31

> **Status: Available in ETLantic 0.31.0.** Execution, State, and Materialization
> Semantics (Medallantic **M3**): live `transform_ref`, intent-driven runs,
> atomic watermark/state commits, portable write intents, and lifecycle
> conformance.

## Highlights

- **`transform_ref` execution** through ETLantic Transformations (compose with
  quality gates); `MDL111` only when a ref cannot be resolved
- Run intents: **STANDARD / INITIALIZE / INCREMENTAL / REFRESH / VALIDATE**
  resolve write modes and state advancement rules
- **`IncrementalStrategy`** + **`StateStore`** (`MemoryStateStore`,
  `FileStateStore`) with commit-after-materialization and VALIDATE/failure
  non-advancement
- Portable **`WriteMode.SKIP_IF_EXISTS`** and plan/runtime capability checks
  (`PMPLAN430` / `PMPLAN431`); local memory honors append / skip-if-exists
- Medallantic layer defaults: bronze **preserve**, silver **refresh**, gold
  **publish** (facade-only)
- Accept-rate enforcement: `enforce_accept_rates` → `MDL120` when thresholds
  fail
- Lifecycle conformance: `etlantic.testing.run_lifecycle_conformance_suite`
- [Migration 0.30 → 0.31](../11_DEVELOPMENT/MIGRATION_0_30_TO_0_31.md) and
  [Exit gate 0.31](../11_DEVELOPMENT/EXIT_GATE_0_31.md)

## Not in 0.31

- Native PySpark Column / SparkForge differential parity (**0.32 / M4**)
- Moltres / SQLAlchemy builder differential (**0.33 / M5**)
- Quality-trend analytics providers (**0.34**)
- Quality `observed` port
- Live portable quality compilers on SQL / PySpark (still advertise + fail-closed)

## Upgrade

Pin core and plugins to the same minor:

```bash
python -m pip install --upgrade 'etlantic==0.31.0'
python -m pip install --upgrade 'medallantic==0.31.0'
```

Plugin authors: pin `etlantic>=0.31.0,<0.32`.
