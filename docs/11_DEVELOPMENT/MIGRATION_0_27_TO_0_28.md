# Migration 0.27 → 0.28

> **Status: Available in ETLantic 0.28.0.** Compatibility burn-in (fourth slice);
> **no wire-schema reset**.

## Summary

| Area | Change |
|---|---|
| Wire schemas | Still `etlantic.pipeline/1`, `plan/1`, `run_report/1`, … |
| Package pin | `etlantic==0.28.0`; plugins `etlantic-*==0.28.0`; `medallantic==0.28.0` |
| Plugin SDK `/1` | **Frozen** for core families in 0.28.0 |
| Root aliases | **Removed** third-wave groups (see below) |
| SparkForge adapter | Optional `etlantic-sparkforge==0.28.0` redirect → `medallantic` |

## Upgrade steps

1. Pin core and matching plugins:

   ```bash
   python -m pip install --upgrade 'etlantic==0.28.0'
   # plus matching extras / plugin packages at 0.28.0
   ```

2. Re-run validate / plan on existing pipelines — no definition schema rewrite
   required for `/1` documents authored under 0.27.

3. **Update imports** for symbols removed from the root facade in 0.28:

   | Was (`from etlantic import …`) | Use instead |
   |---|---|
   | `col`, `concat`, `select`, `RelationRef`, `SqlQuery`, `discover_sql_plugins` | `from etlantic.sql import …` |
   | `load_profile`, `write_profile`, `development_profile`, `production_profile`, `resolve_profile`, `test_profile` | `from etlantic.profile import …` |
   | `Inject`, `Emit`, `FailureAction`, `OutboundEvent`, `StepFailureContext` | `from etlantic.lifecycle import …` |

4. SparkForge users: prefer `medallantic` directly. If needed, install the final
   redirect wheel (`etlantic-sparkforge==0.28.0`) which re-exports Medallantic
   and warns on import.

5. Plugin authors: pin `etlantic>=0.28.0,<0.29` and re-run public conformance
   suites. Protocol `/1` is **frozen** — only additive optional evolution within
   `/1` is permitted.

## Quadruple-minor burn-in

0.28 adds golden fixtures under `tests/fixtures/burn_in/**/v0_27/` proving
0.27-authored documents load and rewrite under 0.28. Existing `v0_24/` through
`v0_26/` trees remain loadable (0.26→0.27→0.28 window).

## See also

- [What's New 0.28](../01_GETTING_STARTED/WHATS_NEW_0_28.md)
- [Exit gate 0.28](EXIT_GATE_0_28.md)
- [Wire schema ranges](../10_REFERENCE/WIRE_SCHEMA_RANGES.md)
- [Removal candidates](REMOVAL_CANDIDATES_1_0.md)
- [Migration 0.26 → 0.27](MIGRATION_0_26_TO_0_27.md)
- [Facade packages](FACADE_PACKAGES.md)
