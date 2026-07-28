# What's New in ETLantic 0.28

> **Status: Available in ETLantic 0.28.0.** Compatibility Burn-In (fourth slice):
> prove **0.26 → 0.27 → 0.28** without a wire-schema reset; Plugin SDK `/1`
> **frozen**; third-wave root removals; Medallantic M0 closeout.

## Highlights

- Quadruple-minor burn-in: golden **`v0_27/`** fixtures alongside `v0_24/` through
  `v0_26/` for pipeline, plan, run_report, profile, capabilities, and interchange
- Plugin SDK `/1` **frozen** for core families (`dataframe`, `sql`, `spark`,
  `orchestration`, `transform-compiler`) — see
  [Protocol evolution](../07_PLUGIN_SDK/PROTOCOL_EVOLUTION.md) and
  [External plugin feedback](../11_DEVELOPMENT/EXTERNAL_PLUGIN_FEEDBACK.md)
- **Third-wave root alias removals** (0.28): `sql`, `profile`, and `lifecycle`
  clusters removed from `import etlantic` — use owning modules
- **`etlantic-sparkforge`** final compatibility redirect wheel (depends on
  `medallantic`, emits deprecation warning)
- **Facade package** release category codified for `medallantic` — see
  [Facade packages](../11_DEVELOPMENT/FACADE_PACKAGES.md)
- [Migration 0.27 → 0.28](../11_DEVELOPMENT/MIGRATION_0_27_TO_0_28.md) and
  [Exit gate 0.28](../11_DEVELOPMENT/EXIT_GATE_0_28.md)

## Not in 0.28

- Native `MedallionPipeline` authoring (**0.29 / M1**)
- Remaining demoted root aliases beyond the priority 17
- Production FastAPI control plane / GUI / new engines

## Upgrade

Pin core and plugins to the same minor:

```bash
python -m pip install --upgrade 'etlantic==0.28.0'
```

See [Upgrade hub](UPGRADE.md) and [Wire schema ranges](../10_REFERENCE/WIRE_SCHEMA_RANGES.md).
