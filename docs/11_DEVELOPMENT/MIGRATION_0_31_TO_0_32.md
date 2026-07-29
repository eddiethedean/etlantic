# Migration 0.31 → 0.32

> **Status: Available in ETLantic 0.32.0.** PySpark / Delta differential parity
> (M4); **no wire-schema reset** (`etlantic.plan/1` / `pipeline/1` unchanged).

## Summary

| Area | Change |
|---|---|
| Wire schemas | Still `pipeline/1`, `plan/1`, … |
| Package pin | `etlantic==0.32.0`; plugins / `medallantic==0.32.0` |
| Storage caps | Advertise `storage.delta.*` extras; maintenance ≠ `write.*` |
| Diagnostics | `PMPLAN440` / `PMPLAN441` for missing Delta storage caps |
| Medallantic | Live `from_pipeline_builder`; Column rules → `MDL130` off Spark |
| Testing | `run_sparkforge_differential_suite` |

## Upgrade steps

1. Pin core and matching plugins:

   ```bash
   python -m pip install --upgrade 'etlantic==0.32.0'
   python -m pip install --upgrade 'medallantic==0.32.0'
   ```

2. If you previously relied on a blanket `spark_delta` claim for optimize /
   vacuum / history / time travel, advertise the matching `storage.delta.*`
   extras (or expect `PMPLAN441` / `PMSF323`).

3. Prefer `medallantic.migrate.sparkforge.from_pipeline_builder(...)` for live
   builders; keep frozen IR fixtures for CI without SparkForge installed.

4. Native PySpark Column rules are **not** portable `etlantic.quality/1` —
   they require `quality.pyspark_column` and fail with `MDL130` on local /
   non-Spark engines.

5. Debug / rerun: pass `implementation_overrides` and `invalidation` through
   `debug_request_from_sparkforge`.

## Breaking / behavior notes

- `etlantic-pyspark` now claims `dataframe=True` (required by `lazy` implication).
- Fine-grained Delta maintenance no longer succeeds plan-time checks on
  `spark_delta` alone (merge still accepts legacy `spark_delta` /
  `spark_merge` / `write.merge`).

## See also

- [What's New 0.32](../01_GETTING_STARTED/WHATS_NEW_0_32.md)
- [Exit gate 0.32](EXIT_GATE_0_32.md)
- [Capability vocabulary](../07_PLUGIN_SDK/CAPABILITY_VOCABULARY.md)
