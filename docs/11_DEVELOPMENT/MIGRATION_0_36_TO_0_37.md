# Migration 0.36 → 0.37

> **Status: Gate-ready for tag/publish rehearsal toward ETLantic 0.37.0.**
> Stable foundation graduation; **no intentional wire-schema major reset**
> (`etlantic.plan/1` / `pipeline/1` / `run_report/1` majors unchanged). Breaking
> changes are the scheduled removals and the plugin dependency floor.

## Summary

| Area | Change |
|---|---|
| Wire schemas | Still `pipeline/1`, `plan/1`, `run_report/1`, … (additive `/1`) |
| Package pin | `etlantic==0.37.0` (when published); plugins / `medallantic==0.37.0` |
| Plugin floor | `etlantic>=0.37.0,<0.38` |
| Demoted root aliases | **Removed** — import from owning modules or curated root |
| `DataContractModel` | **Removed** — use `ContractModel` / `Data` |
| Testing | `etlantic.testing` **graduated** to stable foundation (was preview freeze in 0.36) |
| Quality | `etlantic.quality/1` remains **provisional** |
| Scheduler | `etlantic.scheduler/1` remains **stable MVP** (Prefect bounds) |
| Arrow | Gate A only (Polars↔Pandas) |
| DataFusion | Remains **experimental** |
| Maturity | PyPI **Beta** classifier retained |

## Upgrade steps

1. Pin core and matching plugins together (do not mix 0.36 and 0.37 minors):

   ```bash
   python -m pip install --upgrade 'etlantic==0.37.0'
   python -m pip install --upgrade 'medallantic==0.37.0'
   ```

   Install every official plugin you use at `==0.37.0` as well.

2. Replace demoted root aliases with owning-module imports (or curated
   `import etlantic as etl` symbols that remain on the public facade).

3. Replace `DataContractModel` with `ContractModel` / `Data` per current
   contracts documentation.

4. Re-validate and re-plan:

   ```bash
   etlantic validate TARGET --format json
   etlantic plan TARGET --format json
   ```

5. Update pipeline tests to the graduated public `etlantic.testing` surface.
   Prefer public imports only; do not rely on private underscore modules.

6. Plugin authors: set `etlantic>=0.37.0,<0.38` and re-run public conformance.

## Breaking changes

- Plugin dependency floor becomes `etlantic>=0.37.0,<0.38`.
- Remaining demoted root aliases under `_DEMOTED_ALIASES` are removed.
- `DataContractModel` is removed as a public compatibility alias.
- No intentional wire-schema major break. Treat unexpected plan/report shape
  loss as a bug.

## Protocol status changes

| Protocol / surface | 0.36 | 0.37 |
|---|---|---|
| `etlantic.testing` | Preview minimum contract frozen | **Graduated** stable foundation |
| `etlantic.quality/1` | Provisional | Remains **provisional** |
| `etlantic.scheduler/1` | Stable MVP | Unchanged (**stable MVP**) |
| Core Plugin SDK `/1` families | Frozen since 0.28 | Unchanged (additive only) |
| Arrow interchange | Gate A | Gate A only (no Gate B) |
| DataFusion | Experimental | Remains **experimental** |

## Rollback

Re-pin `etlantic==0.36.0` and matching `0.36.0` plugins /
`medallantic==0.36.0`, then re-validate. Prefer rolling back the whole
environment together. Do not mix 0.36 and 0.37 minors in one environment.

Code that already migrated off demoted aliases and `DataContractModel` remains
valid on 0.36; code that still used removed aliases will not run on 0.37.

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

- [What's New in 0.37](../01_GETTING_STARTED/WHATS_NEW_0_37.md)
- [Exit gate 0.37](EXIT_GATE_0_37.md)
- [Findings ledger 0.37](FINDINGS_0_37.md)
- [Removal candidates 0.37](REMOVAL_CANDIDATES_0_37.md)
- [Deprecation policy](DEPRECATION_POLICY.md)
- [Wire schema ranges](../10_REFERENCE/WIRE_SCHEMA_RANGES.md)
