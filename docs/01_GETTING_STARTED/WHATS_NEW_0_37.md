# What's New in ETLantic 0.37

> **Status: Gate-ready for tag/publish rehearsal toward ETLantic 0.37.0.**
> Stable foundation graduation: scheduled removals executed, public
> application-pipeline testing graduated, acceptance scenarios 1–21 proven,
> security verification matrix published, and in-repo release rehearsal
> prepared. This page describes adopter outcomes; it does not claim PyPI
> publication yet.

## Highlights

- **Stable foundation** — typed authoring, planning, execution evidence, Plugin
  SDK `/1`, and production trust controls graduate as one freeze envelope
- **Application-pipeline testing graduates** — public `etlantic.testing`
  is the stable foundation for deterministic, bounded pipeline cases
  (replacing the 0.36 preview freeze)
- **Acceptance suite 1–21** — end-to-end proof across contracts, engines,
  Airflow compile, security boundaries, third-party plugins, and public testing
- **Scheduled removals** — remaining demoted root aliases and
  `DataContractModel` removed; prefer owning modules and `ContractModel` /
  `Data`
- **Arrow Gate A only** — Polars↔Pandas interchange remains the supported
  cross-plugin Arrow claim; DataFusion stays experimental
- **`etlantic.quality/1` remains provisional** — no silent foundation claim
- **`etlantic.scheduler/1` stable MVP** — unchanged from 0.36 (Prefect bounds)
- **Beta classifier retained** — PyPI maturity stays Beta through the
  foundation release
- **Security verification matrix** — every mandatory Security Model control
  maps to an owner and automated check

## Adopter actions

| Who | Action |
|---|---|
| Everyone on 0.36.x | Plan the pin bump to `etlantic==0.37.0` and matching plugins / `medallantic==0.37.0` when published |
| Root-alias consumers | Switch demoted root imports to owning modules or curated `import etlantic as etl` symbols |
| `DataContractModel` users | Switch to `ContractModel` / `Data` |
| Plugin authors | Raise the core floor to `etlantic>=0.37.0,<0.38` and re-run public conformance |
| Pipeline test authors | Prefer graduated public `etlantic.testing` helpers |
| Quality authors | Continue treating `quality/1` as provisional wire |
| DataFusion experimenters | Keep treating `etlantic-datafusion` as experimental |

## Not in 0.37

- Multi-tenant control plane (**0.39+**)
- First-class data connectivity / connector SDK (**0.38**)
- DataFusion Gate B graduation
- Full foundation claim for `etlantic.quality/1`
- Removal of transitional SparkForge adapters (**major only**)
- Dropping the PyPI Beta classifier

## See also

- [Migration 0.36 → 0.37](../11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md)
- [Exit gate 0.37](../11_DEVELOPMENT/EXIT_GATE_0_37.md)
- [Findings ledger 0.37](../11_DEVELOPMENT/FINDINGS_0_37.md)
- [Wire schema ranges](../10_REFERENCE/WIRE_SCHEMA_RANGES.md)
- [Compatibility](../10_REFERENCE/COMPATIBILITY.md)
