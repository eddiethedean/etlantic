# Migration 0.25 → 0.26

> **Status: Available in ETLantic 0.26.0.** Compatibility burn-in (second slice);
> **no wire-schema reset**.

## Summary

| Area | Change |
|---|---|
| Wire schemas | Still `etlantic.pipeline/1`, `plan/1`, `run_report/1`, … |
| Package pin | `etlantic==0.26.0`; plugins `etlantic-*==0.26.0` |
| Plugin SDK `/1` | Freeze-eligible; **owned by 0.27** (not frozen) |
| Root aliases | **Removed** first-wave groups (see below) |

## Upgrade steps

1. Pin core and matching plugins:

   ```bash
   python -m pip install --upgrade 'etlantic==0.26.0'
   # plus matching extras / plugin packages at 0.26.0
   ```

2. Re-run validate / plan on existing pipelines — no definition schema rewrite
   required for `/1` documents authored under 0.25.

3. **Update imports** for symbols removed from the root facade in 0.26:

   | Was (`from etlantic import …`) | Use instead |
   |---|---|
   | `ETLanticError`, `PipelineExecutionError`, … | `from etlantic.exceptions import …` |
   | `MemoryStorage`, `JsonStorage`, … | `from etlantic.storage import …` |
   | `RunIntent`, `RunRequest`, … | `from etlantic.runtime import …` |
   | `DATAFRAME_PROTOCOL_VERSION`, … | owning protocol module (`etlantic.dataframe`, …) |
   | `diff_pipelines`, `load_bundle`, … | `from etlantic.interchange import …` |

   Remaining demoted aliases still warn once; see
   [Removal candidates](REMOVAL_CANDIDATES_1_0.md).

4. Plugin authors: pin `etlantic>=0.26.0,<0.27` and re-run public conformance
   suites. Protocol `/1` is not frozen yet.

## Dual-minor burn-in

0.26 adds golden fixtures under `tests/fixtures/burn_in/**/v0_25/` proving
0.25-authored documents load and rewrite under 0.26. Existing `v0_24/` trees
remain loadable (0.24→0.25→0.26 window).

## See also

- [What's New 0.26](../01_GETTING_STARTED/WHATS_NEW_0_26.md)
- [Exit gate 0.26](EXIT_GATE_0_26.md)
- [Wire schema ranges](../10_REFERENCE/WIRE_SCHEMA_RANGES.md)
- [Removal candidates](REMOVAL_CANDIDATES_1_0.md)
