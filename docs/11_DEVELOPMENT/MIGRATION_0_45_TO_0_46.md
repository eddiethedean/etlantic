# Migration 0.45 → 0.46

> **Status: Available for ETLantic 0.46.0.** Upgrade notes for adopters moving
> from the published 0.45 planner and optimization SDK line to the gate-ready
> 0.46 streaming and dynamic-control line.

## Summary

| Area | Change |
|---|---|
| Package pin | `etlantic==0.46.0` (do not mix 0.45 and 0.46 minors) |
| Plugin floor | `etlantic>=0.46.0,<0.47` |
| New surface | `etlantic.streaming` (`etlantic.streaming/1`) |
| New node kinds | `map`, `reduce`, `conditional`, `failure`, `compensation` |
| New profile field | `schema_registry_allowlist` |
| New CLI | `etlantic stream` (`dead-letters inspect`, `redrive plan`, `schemas check`) |
| New testing | `run_streaming_conformance_suite`, `run_schema_registry_conformance_suite` |
| Experimental extras | `etlantic-kafka`, `etlantic-schemaregistry` (fake-first; not Available in core) |
| Optimizer | Unknown rewrite kinds fail closed (`PMOPT112`); no expansion/stream rewrites |

## Upgrade steps

1. Complete adoption on **0.45.x**.

2. Pin core and official plugins / Medallantic together:

   ```bash
   python -m pip install --upgrade 'etlantic==0.46.0'
   # plus matching plugins / medallantic at ==0.46.0
   ```

3. Production: keep `plugin_allowlist` explicit. If you load a schema-registry
   adapter, also set `schema_registry_allowlist`:

   ```python
   from etlantic import Profile

   profile = Profile(
       name="production",
       security_mode="production",
       plugin_allowlist={"etlantic-polars": "==0.46.0"},
       schema_registry_allowlist={"etlantic-schemaregistry": "==0.46.0"},
   )
   ```

   Empty production allowlists fail closed (`PMPLUG*` / `PMREG140`). CLI trust
   failures stay exit `11`.

4. Compilers that cannot preserve map/branch/stream nodes **reject before emit**
   (`PMDYN130`). Do not expect a silent flatten to a static DAG.

5. Optional Kafka / registry extras are Experimental:

   ```bash
   pip install 'etlantic[kafka]==0.46.0'
   pip install 'etlantic[schemaregistry]==0.46.0'
   ```

   Default tests use in-process fakes. Live clusters require
   `ETLANTIC_KAFKA_BOOTSTRAP` / `ETLANTIC_SCHEMA_REGISTRY_URL` and are skipped
   in CI.

## Compatibility notes

- Wire families remain `etlantic.plan/1` and `etlantic.run_report/1` with
  additive `etlantic.streaming.*` / `etlantic.expansion.*` metadata.
- Plans and reports must not contain event payloads or source rows.
- `optimization_policy` default remains `off`. Do not add expansion/stream
  `RewriteKind`s until a later proof-kind line.

## Related

- [What's New in 0.46](../01_GETTING_STARTED/WHATS_NEW_0_46.md)
- [Streaming connectors](../07_PLUGIN_SDK/STREAMING_CONNECTORS.md)
- [Schema registry](../07_PLUGIN_SDK/SCHEMA_REGISTRY.md)
- [ADR-022](adr/ADR-022-DYNAMIC-CONTROL-AND-STREAMING.md)
