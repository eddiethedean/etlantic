# What's New in ETLantic 0.30

> **Status: Available in ETLantic 0.30.0.** Portable Quality and Rule Semantics
> (Medallantic **M2**): provisional `etlantic.quality/1`, plan-time fail-closed
> rule capabilities, Polars/Pandas live portable core, and Medallantic rule DSL
> enforcement (replacing `MDL110` passthrough).

## Highlights

- Provisional **`etlantic.quality/1`** AST (ContractModel remains semantic
  authority): `not_null`, compare, membership, range, regex, length,
  uniqueness, `custom_contract`
- Quality-gate Transformations with accepted / rejected ports
  (`make_quality_gate`) and plan metadata (cost, capabilities, fallback
  evidence, `validation_boundary`)
- Plan-time fail-closed diagnostics **`PMPLAN420` / `PMPLAN421`** for unsupported
  required quality capabilities
- Portable quality conformance suite:
  `etlantic.testing.run_quality_conformance_suite`
- Polars / Pandas advertise portable quality capabilities; SQL / PySpark
  classify as advertise + fail-closed for portable rules in 0.30
- Medallantic shorthand DSL → quality AST; bronze/silver rules lower to real
  gates; layer accept-rate helper `evaluate_accept_rates`
- [Migration 0.29 → 0.30](../11_DEVELOPMENT/MIGRATION_0_29_TO_0_30.md) and
  [Exit gate 0.30](../11_DEVELOPMENT/EXIT_GATE_0_30.md)

## Not in 0.30

- Validation-only runs and write/materialization lifecycle parity (**0.31 / M3**)
- Native PySpark Column / Moltres-only rules (**0.32 / 0.33**)
- Quality-trend analytics providers (**0.34**)
- Full live SQL / PySpark portable-core compilers (classified deferred)

## Upgrade

Pin core and plugins to the same minor:

```bash
python -m pip install --upgrade 'etlantic==0.30.0'
python -m pip install --upgrade 'medallantic==0.30.0'
```

See [Upgrade hub](UPGRADE.md) and [Roadmap summary](../11_DEVELOPMENT/ROADMAP_SUMMARY.md).
