# Migration 0.37 → 0.38

> **Status: Gate-ready for tag/publish rehearsal toward ETLantic 0.38.0.**
> Upgrade guide for adopters moving from the 0.38 stable foundation to the
> 0.38 connectivity line.

## Summary

| Area | Change |
|---|---|
| Package pin | `etlantic==0.38.0` (when published); matching plugins / `medallantic==0.38.0` |
| Plugin floor | `etlantic>=0.38.0,<0.39` |
| New protocols | `etlantic.source/1`, `etlantic.sink/1`, `etlantic.storage/1` |
| Public package | `etlantic.connectors` |
| Entry points | `etlantic.source_connectors`, `etlantic.sink_connectors`, `etlantic.storage_connectors` |
| Landing zone | Built-in `local-files` snapshot + incremental; checkpoint `etlantic.landing_checkpoint/1` |
| Reference packages | `etlantic-s3`, `etlantic-iceberg`, `etlantic-snowflake`; PostgreSQL via `etlantic-sql` |
| StorageBinding | Remains via compatibility adapter; no automatic connector capability claims |
| Continuous watch | Still out of core — compose in 0.39+ |
| Wire schemas | Prefer additive `/1` extensions; no intentional major reset |

## Upgrade steps

1. Pin core and every official plugin / Medallantic together at `0.38.0`
   (do not mix 0.37 and 0.38 minors):

   ```bash
   python -m pip install --upgrade 'etlantic==0.38.0'
   python -m pip install --upgrade 'medallantic==0.38.0'
   # plus every official plugin you use at ==0.38.0
   ```

2. Update production `plugin_allowlist` pins to `==0.38.0`.

3. Replace or extend asset bindings with structured connector descriptors where
   you need landing-zone, object-store, table-format, warehouse, or relational
   connectors. Keep existing memory/CSV/JSON/callable storage paths unless you
   intentionally migrate.

4. For landing zones, choose `mode: snapshot` or `mode: incremental` on the
   binding/profile. Do not rewrite `Extract` topology. Incremental requires a
   checkpoint reference.

   ```python
   from etlantic import Profile

   Profile(
       name="landing",
       assets={
           "orders_in": {
               "provider": "local-files",
               "format": "csv",
               "root": "inbox",
               "root_ref": "landing",
               "glob": "*.csv",
               "mode": "incremental",
               "consume": "ledger",
               "checkpoint": "orders_ckpt",
           },
           "orders_out": "memory://orders_out",
       },
   )
   ```

5. Re-validate and re-plan:

   ```bash
   etlantic validate TARGET --format json
   etlantic plan TARGET --format json
   ```

   Expect connector selection and identity **scheme** in the plan — not a live
   file list. Concrete identities appear in run reports /
   `LandingReadManifest` evidence.

6. Optional cloud connectors (Experimental):

   ```bash
   pip install 'etlantic[s3]==0.38.0'          # or iceberg / snowflake
   ```

7. Plugin / connector authors: implement against `etlantic.connectors`, declare
   the frozen capability vocabulary, set the 0.38 plugin floor, and run public
   `etlantic.testing` connector conformance.

## Breaking changes

- Plugin dependency floor becomes `etlantic>=0.38.0,<0.39`.
- Unsupported connector modes/writes/transactions/pushdown fail at plan time
  (no silent fallback).
- New plans retain root aliases/references rather than absolute landing-root
  paths.
- StorageBinding paths do not gain connector capability claims without an
  explicit connector registration.

## Non-goals for this migration

- Continuous directory watching in core
- Vendor SDKs as core dependencies
- Expanding public single-file `CsvStorage` into directory landing-zone
  semantics
- Promoting cloud packages beyond Experimental

## Rollback

Re-pin `etlantic==0.37.0` and matching `0.37.0` plugins / `medallantic==0.37.0`,
then re-validate. Prefer rolling back the whole environment together.

## Security notes

- Plans, reports, diagnostics, checkpoints, and test evidence must never
  contain resolved secret values or arbitrary source rows.
- Production profiles still require an explicit `plugin_allowlist` and fail
  closed before connector import.
- Physical landing-root paths must not appear in new plans or reports.

## See also

- [What's New in 0.38](../01_GETTING_STARTED/WHATS_NEW_0_38.md)
- [Exit gate 0.38](EXIT_GATE_0_38.md)
- [Findings ledger 0.38](FINDINGS_0_38.md)
- [Capability matrix](CONNECTOR_CAPABILITY_MATRIX_0_38.json)
- [ADR-015: Connector Protocols](adr/ADR-015-CONNECTOR-PROTOCOLS.md)
- [Implementation plan 0.38](IMPLEMENTATION_PLAN_0_38.md)
- [Landing-zone file connector plan](LANDING_ZONE_CONNECTOR_PLAN.md)
- [Connector SDK overview](../07_PLUGIN_SDK/CONNECTOR_SDK.md)
- [Migration 0.36 → 0.37](MIGRATION_0_36_TO_0_37.md)
