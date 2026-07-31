# Migration 0.35 → 0.36

> **Status: Available in ETLantic 0.36.0.** Joint compatibility burn-in;
> **no wire-schema reset** (`etlantic.plan/1` / `pipeline/1` /
> `run_report/1` majors unchanged).

## Summary

| Area | Change |
|---|---|
| Wire schemas | Still `pipeline/1`, `plan/1`, `run_report/1`, … (additive `/1`) |
| Package pin | `etlantic==0.36.0`; plugins / `medallantic==0.36.0` |
| Plugin floor | `etlantic>=0.36.0,<0.37` |
| Run reports | Bare top-level metadata keys migrate to namespaced keys |
| Scheduler | `etlantic.scheduler/1` promoted to **stable MVP** (Prefect bounds) |
| Quality | `etlantic.quality/1` remains **provisional** (outside full foundation claim) |
| Testing | Preview minimum case/result/snapshot contract frozen for burn-in |
| Medallantic | Joint definition / migration-IR / differential burn-in on matching minors |
| Production trust | `plugin_allowlist` entries require non-empty version pins |
| Plan / run | Missing implementations fail at plan (`PMPLAN301`); soft-continued runs are `PARTIAL` |
| Reliability CLI | `partition-check` needs `--observed`; `quality-trends` needs `--values` |

## Upgrade steps

1. Pin core and matching plugins together (do not mix 0.35 and 0.36 minors):

   ```bash
   python -m pip install --upgrade 'etlantic==0.36.0'
   python -m pip install --upgrade 'medallantic==0.36.0'
   ```

   Install every official plugin you use at `==0.36.0` as well
   (`etlantic-polars`, `etlantic-pandas`, `etlantic-sql`, `etlantic-pyspark`,
   `etlantic-airflow`, `etlantic-prefect`, …).

2. Re-validate and re-plan pipelines after the pin bump:

   ```bash
   etlantic validate TARGET --format json
   etlantic plan TARGET --format json
   ```

3. Re-load durable run reports written under 0.35. Bare (non-namespaced)
   metadata keys are migrated to namespaced keys without silent field loss.
   Preserve the 0.35.0 known-defect fixture path when verifying:

   `tests/fixtures/releases/v0_35/known_defects/run_report_bare_metadata.json`

4. Optional: continue using `etlantic.testing` pipeline-case helpers. The
   0.36 burn-in freezes the minimum preview contract; full foundation
   graduation remains **0.37**.

5. Scheduler adopters: Prefect-bounded `scheduler/1` is the stable MVP path.
   Airflow remains a compile target via `etlantic-airflow` (no core Airflow
   dependency).

## Breaking changes

- Plugin dependency floor becomes `etlantic>=0.36.0,<0.37`.
- No intentional wire-schema major break. Treat unexpected plan/report shape
  loss as a bug.
- Consumers that assumed bare run-report metadata keys remain stable without
  namespacing must update to namespaced keys (or rely on the documented
  migration path).
- Production `plugin_allowlist` values of `null` / `""` no longer authorize any
  version — set an explicit pin such as `"==0.36.0"`.
- Pipelines without a registered `@Transformation.implementation` (or portable
  selection) fail at **plan** with `PMPLAN301` (previously deferred to run).
- `FailureAction.CONTINUE` soft-skips yield overall run status `PARTIAL` (CLI
  non-zero), never pure `SUCCEEDED`.
- `etlantic reliability partition-check` requires `--observed` partition
  evidence; `quality-trends` requires `--values` samples.

## Protocol status changes

| Protocol / surface | 0.35 | 0.36 |
|---|---|---|
| `etlantic.scheduler/1` | Provisional / off freeze path | **Stable MVP** on foundation path (Prefect bounds) |
| `etlantic.quality/1` | Provisional wire | Remains **provisional** (not a full stable-foundation claim) |
| `etlantic.testing` preview | Preview | Minimum burn-in contract **frozen**; graduation at **0.37** |
| Core Plugin SDK `/1` families | Frozen since 0.28 | Unchanged (additive only) |

## Rollback

Re-pin `etlantic==0.35.0` and matching `0.35.0` plugins /
`medallantic==0.35.0`, then re-validate. Prefer rolling back the whole
environment together. Do not mix 0.35 and 0.36 minors in one environment.

If you already rewrote durable reports under 0.36 with namespaced metadata,
keep a copy of the pre-migration artifacts before rollback, or regenerate
reports after re-pinning.

## Security notes

- Plans, reports, diagnostics, snapshots, migration reports, and test
  evidence must never contain resolved secret values.
- Production profiles still require an explicit `plugin_allowlist` and fail
  closed.
- Schema-history and compatibility fixtures store schemas, fingerprints, and
  bounded metadata only — never source rows.
- Review release digests and attestations as for any release. Prefer exact
  pins for core and every official plugin.

## See also

- [What's New in 0.36](../01_GETTING_STARTED/WHATS_NEW_0_36.md)
- [Exit gate 0.36](EXIT_GATE_0_36.md)
- [Findings ledger 0.36](FINDINGS_0_36.md)
- [Wire schema ranges](../10_REFERENCE/WIRE_SCHEMA_RANGES.md)
