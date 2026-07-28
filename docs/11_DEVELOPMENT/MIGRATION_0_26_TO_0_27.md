# Migration 0.26 → 0.27

> **Status: Planned for ETLantic 0.27** (not shipped). Compatibility burn-in
> (third slice); **no wire-schema reset** expected.

## Summary (planned)

| Area | Planned change |
|---|---|
| Wire schemas | Still `etlantic.pipeline/1`, `plan/1`, `run_report/1`, … |
| Package pin | `etlantic==0.27.0`; plugins `etlantic-*==0.27.0` (when shipped) |
| Plugin SDK `/1` | Freeze closure **or** dated re-scope (see PROTOCOL_EVOLUTION) |
| Root aliases | `REM-RELIABILITY-ROOT` + bounded demoted wave removed from root |

## Upgrade steps (draft)

1. Pin core and matching plugins to 0.27.0 when released.
2. Re-run validate / plan — no `/1` definition schema rewrite expected for
   documents authored under 0.26.
3. Update imports for any symbols removed from the root facade in 0.27 (exact
   table filled when the removal wave lands). Prefer owning modules per
   [Removal candidates](REMOVAL_CANDIDATES_1_0.md).
4. Plugin authors: pin `etlantic>=0.27.0,<0.28` and re-run public conformance.

## Triple-minor burn-in

0.27 plans golden fixtures under `tests/fixtures/burn_in/**/v0_26/` proving
0.26-authored documents load and rewrite under 0.27. Existing `v0_25/` trees
remain part of the documented window.

## See also

- [What's New 0.27](../01_GETTING_STARTED/WHATS_NEW_0_27.md) (planned)
- [Exit gate 0.27](EXIT_GATE_0_27.md)
- [Migration 0.25 → 0.26](MIGRATION_0_25_TO_0_26.md)
- [Wire schema ranges](../10_REFERENCE/WIRE_SCHEMA_RANGES.md)
- [Removal candidates](REMOVAL_CANDIDATES_1_0.md)
