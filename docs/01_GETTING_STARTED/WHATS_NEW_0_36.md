# What's New in ETLantic 0.36

> **Status: Available in ETLantic 0.36.0.** Joint compatibility burn-in: prove
> that supported users can upgrade, load and regenerate durable artifacts, run
> representative pipelines across the advertised engine intersection, and
> consume first-party plugins without silent semantic change, unplanned
> wire-schema reset, secret disclosure, or unexplained Medallantic parity
> difference.

## Highlights

- **Joint compatibility burn-in** — quantified `0.34 → 0.35` and
  `0.35 → 0.36` upgrade evidence for core, first-party plugins, and
  Medallantic on matching minors
- **Isolated-wheel reader/writer evidence** — true old/new codec outcomes in
  addition to current-reader goldens (`v0_24`–`v0_27` and `v0_34`–`v0_36`)
- **Plugin wheel conformance** — first-party packages exercise public
  conformance from clean wheel installs, not monorepo path imports alone
- **Application-pipeline testing burn-in** — public `etlantic.testing`
  preview minimum contract frozen for burn-in (foundation graduation remains
  **0.37**)
- **Medallantic joint burn-in** — definition, migration-IR, semantic, and
  legacy differential corpora across the facade/core boundary
- **`etlantic.scheduler/1` stable MVP** — promoted onto the foundation path
  with Prefect-bounded direct-execution evidence
- **`etlantic.quality/1` remains provisional** — wire schema stays outside
  the full stable-foundation claim (no silent graduation)
- **Fail-closed hardening** — production allowlist version pins required;
  Safe I/O / outbound / schema-history / authoring secret denylists tightened;
  missing implementations fail at plan (`PMPLAN301`); soft-continued runs
  report `PARTIAL`

## Adopter actions

| Who | Action |
|---|---|
| Everyone on 0.35.x | Bump pins to `etlantic==0.36.0` and matching plugins / `medallantic==0.36.0` |
| Plugin authors | Raise the core floor to `etlantic>=0.36.0,<0.37` and re-run public conformance |
| Report consumers | Expect bare run-report metadata keys to migrate to namespaced keys |
| Production profiles | Use non-empty version pins in `plugin_allowlist` (null/empty pins fail closed) |
| Scheduler users | Treat `scheduler/1` as a stable MVP (Prefect bounds); keep Airflow as compile-only |
| Quality authors | Continue treating `quality/1` as provisional wire |
| Reliability CLI users | Pass `--observed` to `partition-check` and `--values` to `quality-trends` |

## Not in 0.36

- Stable foundation, including application-pipeline testing graduation and
  release rehearsal against exact artifacts (**0.37**)
- Multi-tenant control plane (**0.39+**)
- Removal of transitional SparkForge adapters (**major only**)

## See also

- [Migration 0.35 → 0.36](../11_DEVELOPMENT/MIGRATION_0_35_TO_0_36.md)
- [Exit gate 0.36](../11_DEVELOPMENT/EXIT_GATE_0_36.md)
- [Wire schema ranges](../10_REFERENCE/WIRE_SCHEMA_RANGES.md)
- [Compatibility](../10_REFERENCE/COMPATIBILITY.md)
