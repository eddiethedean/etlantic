# Migration 0.24 → 0.25

> **Status: Available in ETLantic 0.25.0.** Compatibility burn-in; **no
> wire-schema reset**.

## Summary

| Area | Change |
|---|---|
| Wire schemas | Still `etlantic.pipeline/1`, `plan/1`, `run_report/1`, … |
| Package pin | `etlantic==0.25.0`; plugins `etlantic-*=0.25.0` |
| Plugin SDK `/1` | Freeze-eligible; blockers published (not frozen) |
| Root demoted aliases | Unchanged; inventory published for 0.26+ removals |

## Upgrade steps

1. Pin core and matching plugins:

   ```bash
   python -m pip install --upgrade 'etlantic==0.25.0'
   # plus matching extras / plugin packages at 0.25.0
   ```

2. Re-run validate / plan on existing pipelines — no definition schema rewrite
   required for `/1` documents authored under 0.24.

3. Prefer owning-module imports for exceptions and demoted root symbols (warnings
   unchanged from 0.22+).

4. Plugin authors: keep pinning `etlantic>=0.25.0,<0.26` and re-run public
   conformance suites. Do not assume `/1` is frozen yet.

## Codec burn-in

0.24-authored golden fixtures under `tests/fixtures/burn_in/**/v0_24/` must load
and rewrite under 0.25. Intentional incompatible codec changes require a
documented upgrader (no silent field drops) and Migration note updates.

## See also

- [What's New 0.25](../01_GETTING_STARTED/WHATS_NEW_0_25.md)
- [Exit gate 0.25](EXIT_GATE_0_25.md)
- [Wire schema ranges](../10_REFERENCE/WIRE_SCHEMA_RANGES.md)
- [Removal candidates](REMOVAL_CANDIDATES_1_0.md)
