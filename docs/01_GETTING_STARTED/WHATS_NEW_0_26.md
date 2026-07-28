# What's New in ETLantic 0.26

> **Status: Available in ETLantic 0.26.0.** Compatibility Burn-In (second slice):
> prove **two consecutive** minor upgrade paths (0.24→0.25 and 0.25→0.26) without
> a wire-schema reset.

## Highlights

- Dual-minor burn-in: golden **0.25 → 0.26** fixtures alongside existing `v0_24/`
  trees for pipeline, plan, run_report, profile, capabilities, and interchange
- CI gates extended: `check_pipeline_codec_burn_in.py` and
  `check_codec_burn_in_matrix.py` cover both `v0_24/` and `v0_25/`
- [Wire schema ranges](../10_REFERENCE/WIRE_SCHEMA_RANGES.md) documents the
  dual-minor window and authoring-catalog N/A rationale
- Plugin SDK `/1` freeze **owned by 0.27** (external feedback blocker remains
  open; not frozen in 0.26)
- **First-wave root alias removals** (0.26): protocol consts, exceptions, storage,
  runtime, interchange helpers removed from `import etlantic` — use owning modules
- [Migration 0.25 → 0.26](../11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md) and
  [Exit gate 0.26](../11_DEVELOPMENT/EXIT_GATE_0_26.md)

## Not in 0.26

- Freezing Plugin SDK `/1` (**0.27**)
- Complete 1.0 removal list (later burn-in / 0.99)
- Production FastAPI control plane / GUI / new engines / DataFusion graduation

## Try it (pip-only)

```bash
python -m pip install 'etlantic==0.26.0'
mkdir my-pipeline && cd my-pipeline
python -m etlantic init --with-toml
python -m etlantic validate pipeline.py:SamplePipeline --profile development
```

From a checkout, burn-in fixtures live under `tests/fixtures/burn_in/`.

## Upgrade

See [Migration 0.25 → 0.26](../11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md) and the
[Upgrade hub](UPGRADE.md).
