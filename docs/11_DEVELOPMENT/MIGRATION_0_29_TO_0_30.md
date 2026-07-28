# Migration 0.29 → 0.30

> **Status: Available in ETLantic 0.30.0.** Portable quality / M2; **no
> wire-schema reset** (`etlantic.plan/1` unchanged; additive plan metadata).

## Summary

| Area | Change |
|---|---|
| Wire schemas | Still `pipeline/1`, `plan/1`, …; new provisional `etlantic.quality/1` |
| Package pin | `etlantic==0.30.0`; plugins / `medallantic==0.30.0` |
| Quality | `etlantic.quality` namespace + `make_quality_gate` |
| Medallantic | `rules=` enforced via portable gates; `MDL110` only for invalid DSL |
| Engines | Polars/Pandas live portable core; SQL/PySpark fail-closed unless they advertise |

## Upgrade steps

1. Pin core and matching plugins:

   ```bash
   python -m pip install --upgrade 'etlantic==0.30.0'
   python -m pip install --upgrade 'medallantic==0.30.0'
   ```

2. Re-run validate / plan. Pipelines with Medallantic `rules=` now insert quality
   gates (bronze steps may gain an `{name}__ingest` source node).

3. Engines that do not advertise `quality.*` capabilities fail at plan time with
   `PMPLAN420` / `PMPLAN421` when required rules are present. Prefer Polars or
   Pandas for portable rules in 0.30.

4. Plugin authors: pin `etlantic>=0.30.0,<0.31`. Advertise only the quality
   capabilities you implement; every advertised portable rule must pass
   `run_quality_conformance_suite` fixtures.

5. Optional: import `etlantic.quality` or `etl.quality` for AST helpers.

## Breaking / behavior notes

- Medallantic bronze `rules=` are no longer passthrough warnings — they compile
  to quality gates. Graphs that assumed Extract-only bronze node names should
  expect `{step}__ingest` when rules are present.
- `MDL111` remains for uneexecuted `transform_ref` (0.31).

## See also

- [What's New 0.30](../01_GETTING_STARTED/WHATS_NEW_0_30.md)
- [Exit gate 0.30](EXIT_GATE_0_30.md)
- [Wire schema ranges](../10_REFERENCE/WIRE_SCHEMA_RANGES.md)
- [Migration 0.28 → 0.29](MIGRATION_0_28_TO_0_29.md)
