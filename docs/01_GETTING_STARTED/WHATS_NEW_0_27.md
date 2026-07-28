# What's New in ETLantic 0.27

> **Status: Available in ETLantic 0.27.0.** Compatibility Burn-In (third slice):
> prove **0.25 → 0.26 → 0.27** without a wire-schema reset; second-wave root
> removals; Plugin SDK `/1` freeze re-scoped to 0.28+.

## Highlights

- Triple-minor burn-in: golden **`v0_26/`** fixtures alongside `v0_24/` and
  `v0_25/` for pipeline, plan, run_report, profile, capabilities, and interchange
- CI gates extended: `check_pipeline_codec_burn_in.py` and
  `check_codec_burn_in_matrix.py` cover `v0_24/`, `v0_25/`, and `v0_26/`
- [Wire schema ranges](../10_REFERENCE/WIRE_SCHEMA_RANGES.md) documents the
  triple-minor window
- Plugin SDK `/1` freeze **re-scoped to 0.28+** (external feedback blocker
  remains open; not frozen in 0.27)
- **Second-wave root alias removals** (0.27): reliability declarations,
  schema_drift helpers, and registry descriptors removed from `import etlantic`
  — use owning modules
- [Migration 0.26 → 0.27](../11_DEVELOPMENT/MIGRATION_0_26_TO_0_27.md) and
  [Exit gate 0.27](../11_DEVELOPMENT/EXIT_GATE_0_27.md)

## Not in 0.27

- Freezing Plugin SDK `/1` (0.28+)
- Complete 1.0 removal list (later burn-in / 0.99)
- Production FastAPI control plane / GUI / new engines / DataFusion graduation

## Try it (pip-only)

```bash
python -m pip install 'etlantic==0.27.0'
mkdir my-pipeline && cd my-pipeline
python -m etlantic init --with-toml
python -m etlantic validate pipeline.py:SamplePipeline --profile development
```

From a checkout, burn-in fixtures live under `tests/fixtures/burn_in/`.

## Upgrade

See [Migration 0.26 → 0.27](../11_DEVELOPMENT/MIGRATION_0_26_TO_0_27.md) and the
[Upgrade hub](UPGRADE.md).
