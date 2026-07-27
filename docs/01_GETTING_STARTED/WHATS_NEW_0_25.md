# What's New in ETLantic 0.25

> **Status: Available in ETLantic 0.25.0.** Compatibility Burn-In (first slice):
> prove 0.24 wire contracts survive a real minor upgrade without a schema-id
> reset.

## Highlights

- Golden **0.24 → 0.25** fixtures for `etlantic.pipeline/1` (old↔new
  reader/writer) plus CI fingerprint gate
  (`scripts/check_pipeline_codec_burn_in.py`)
- Cross-artifact burn-in matrix: `etlantic.plan/1`, `etlantic.run_report/1`,
  profile JSON, `etlantic.capabilities/1`, `etlantic.interchange/1`
- Documented [wire schema ranges](../10_REFERENCE/WIRE_SCHEMA_RANGES.md) and
  unsupported downgrade behavior
- Plugin SDK `/1` freeze decision: **remaining blockers published** (not frozen);
  see [Protocol evolution](../07_PLUGIN_SDK/PROTOCOL_EVOLUTION.md)
- Published [1.0 removal candidates](../11_DEVELOPMENT/REMOVAL_CANDIDATES_1_0.md)
  (inventory only — no removals in 0.25)

## Not in 0.25

- Dual-minor **0.25 → 0.26** proof (0.26)
- Freezing Plugin SDK `/1` or locking conformance suite versions (0.26)
- Executing demoted-alias removals (0.26+)
- Production FastAPI control plane / GUI / new engines

## Try it (pip-only)

```bash
python -m pip install 'etlantic==0.25.0'
mkdir my-pipeline && cd my-pipeline
python -m etlantic init --with-toml
python -m etlantic validate pipeline.py:SamplePipeline --profile development
```

From a checkout, burn-in fixtures live under `tests/fixtures/burn_in/`.

## Upgrade

See [Migration 0.24 → 0.25](../11_DEVELOPMENT/MIGRATION_0_24_TO_0_25.md) and the
[Upgrade hub](UPGRADE.md).
