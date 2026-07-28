# Migration 0.30 → 0.31

> **Status: Available in ETLantic 0.31.0.** Execution / materialization (M3);
> **no wire-schema reset** (`etlantic.plan/1` unchanged; additive intents and
> report state transitions).

## Summary

| Area | Change |
|---|---|
| Wire schemas | Still `pipeline/1`, `plan/1`, … |
| Package pin | `etlantic==0.31.0`; plugins / `medallantic==0.31.0` |
| Transforms | Medallantic `transform_ref` executes (import path / `module:attr`) |
| Run intents | VALIDATE / INITIALIZE / INCREMENTAL / REFRESH change write + state behavior |
| State | `IncrementalStrategy` + `StateStore`; commit only after successful writes |
| Writes | `WriteMode.SKIP_IF_EXISTS`; capability fail-closed `PMPLAN430`/`431` |
| Accept rates | `enforce_accept_rates` can fail runs (`MDL120`) |

## Upgrade steps

1. Pin core and matching plugins:

   ```bash
   python -m pip install --upgrade 'etlantic==0.31.0'
   python -m pip install --upgrade 'medallantic==0.31.0'
   ```

2. Point `transform_ref` at importable callables (`pkg.mod:fn` or `pkg.mod.fn`).
   Unresolvable import paths emit `MDL111` and fail lowering; symbolic
   SparkForge-style names remain passthrough with a warning.

3. Use `RunIntent.VALIDATE` (or SparkForge `validation_only`) for validation-only
   runs — writes are skipped and watermarks do not advance.

4. Optionally attach incremental columns via step metadata
   (`incremental_column` / `watermark_column`) and pass `state_candidates` on
   `RunRequest.metadata` so the orchestrator can commit after materialization.

5. Call `medallantic.enforce_accept_rates(report, policy_metadata=...)` when
   layer thresholds must fail the run.

6. Plugin authors: pin `etlantic>=0.31.0,<0.32`. Advertise `write.*` extras for
   modes beyond default append/overwrite.

## Breaking / behavior notes

- Medallantic `transform_ref` executes when the ref is an importable callable.
- `skip` / `ignore` write modes map to `SKIP_IF_EXISTS` (not `NO_WRITE`).
- Local memory storage appends when `write_mode=append` instead of always
  replacing.

## See also

- [What's New 0.31](../01_GETTING_STARTED/WHATS_NEW_0_31.md)
- [Exit gate 0.31](EXIT_GATE_0_31.md)
- [Migration 0.29 → 0.30](MIGRATION_0_29_TO_0_30.md)
