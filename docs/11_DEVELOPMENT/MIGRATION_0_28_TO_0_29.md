# Migration 0.28 → 0.29

> **Status: Available in ETLantic 0.29.0.** Native medallion authoring (M1);
> **no wire-schema reset**.

## Summary

| Area | Change |
|---|---|
| Wire schemas | Still `etlantic.pipeline/1`, `plan/1`, `run_report/1`, … |
| Package pin | `etlantic==0.29.0`; plugins `etlantic-*==0.29.0`; `medallantic==0.29.0` |
| Medallantic | Native `MedallionPipeline` / `MedallionBuilder` + migrate namespace |
| Facade kit | `etlantic.testing.run_facade_conformance_suite` |
| Root aliases | No new removals in 0.29 (remaining demotions still 0.29+/1.0) |

## Upgrade steps

1. Pin core and matching plugins:

   ```bash
   python -m pip install --upgrade 'etlantic==0.29.0'
   # plus matching extras / plugin packages at 0.29.0
   python -m pip install --upgrade 'medallantic==0.29.0'
   ```

2. Re-run validate / plan on existing pipelines — no definition schema rewrite
   required for `/1` documents authored under 0.28.

3. Prefer native Medallantic authoring for new medallion pipelines:

   ```python
   from medallantic import MedallionBuilder

   defn = (
       MedallionBuilder("ecommerce", schema="demo")
       .bronze("orders", asset="bronze_orders")
       .silver("clean", source="orders", asset="silver_orders")
       .gold("kpis", source="clean", asset="gold_kpis")
       .build()
   )
   ```

4. SparkForge IR users: prefer `medallantic.migrate.sparkforge` for the
   migration surface. Top-level `medallantic.adapt_pipeline` remains available
   as a compatibility re-export.

5. Plugin / facade authors: pin `etlantic>=0.29.0,<0.30` and run
   `run_facade_conformance_suite` for definition-lowering packages.

## See also

- [What's New 0.29](../01_GETTING_STARTED/WHATS_NEW_0_29.md)
- [Exit gate 0.29](EXIT_GATE_0_29.md)
- [Facade packages](FACADE_PACKAGES.md)
- [Wire schema ranges](../10_REFERENCE/WIRE_SCHEMA_RANGES.md)
- [Migration 0.27 → 0.28](MIGRATION_0_27_TO_0_28.md)
