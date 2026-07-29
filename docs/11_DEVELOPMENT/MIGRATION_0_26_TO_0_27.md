# Migration 0.26 → 0.27

> **Status: Available in ETLantic 0.27.0.** Compatibility burn-in (third slice);
> **no wire-schema reset**.

## Summary

| Area | Change |
|---|---|
| Wire schemas | Still `etlantic.pipeline/1`, `plan/1`, `run_report/1`, … |
| Package pin | `etlantic==0.27.0`; plugins `etlantic-*==0.27.0`; `medallantic==0.27.0` |
| SparkForge adapter | `etlantic-sparkforge` renamed to **`medallantic`** (`etlantic[medallantic]`) |
| Plugin SDK `/1` | Freeze-eligible; **re-scoped to 0.28+** (not frozen) |
| Root aliases | **Removed** second-wave groups (see below) |

## Upgrade steps

1. Pin core and matching plugins:

   ```bash
   python -m pip install --upgrade 'etlantic==0.27.0'
   # plus matching extras / plugin packages at 0.27.0
   ```

2. Re-run validate / plan on existing pipelines — no definition schema rewrite
   required for `/1` documents authored under 0.26.

3. **Update imports** for symbols removed from the root facade in 0.27:

   | Was (`from etlantic import …`) | Use instead |
   |---|---|
   | `BackfillDeclaration`, `FreshnessExpectation`, `WriteMode`, … | `from etlantic.reliability import …` |
   | `SchemaChange`, `NormalizedSchema`, `diff_contract_schemas`, … | `from etlantic.schema_drift import …` |
   | `PlanningContext`, `PluginDescriptor`, `RegistryBundle`, … | `from etlantic.registry import …` |

   Full second-wave list: reliability (12), schema_drift (8), registry (6).
   Remaining demoted aliases still warn once; see
   [Removal candidates](REMOVAL_CANDIDATES_0_38.md).

4. SparkForge adapter users: replace `etlantic-sparkforge` / `etlantic[sparkforge]`
   with `medallantic` / `etlantic[medallantic]` and update imports to
   `import medallantic` (API names such as `debug_request_from_sparkforge` are
   unchanged).

5. Plugin authors: pin `etlantic>=0.27.0,<0.28` and re-run public conformance
   suites. Protocol `/1` is not frozen yet.

## Triple-minor burn-in

0.27 adds golden fixtures under `tests/fixtures/burn_in/**/v0_26/` proving
0.26-authored documents load and rewrite under 0.27. Existing `v0_24/` and
`v0_25/` trees remain loadable (0.25→0.26→0.27 window).

## See also

- [What's New 0.27](../01_GETTING_STARTED/WHATS_NEW_0_27.md)
- [Exit gate 0.27](EXIT_GATE_0_27.md)
- [Wire schema ranges](../10_REFERENCE/WIRE_SCHEMA_RANGES.md)
- [Removal candidates](REMOVAL_CANDIDATES_0_38.md)
- [Migration 0.25 → 0.26](MIGRATION_0_25_TO_0_26.md)
