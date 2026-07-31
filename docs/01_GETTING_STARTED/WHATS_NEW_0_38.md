# What's New in ETLantic 0.38

> **Status: Gate-ready for tag/publish rehearsal toward ETLantic 0.38.0.**
> Data connectivity and connector SDK: public source/sink/storage protocols,
> local landing-zone reference, CDK + conformance, and experimental cloud
> reference packages. This page describes adopter outcomes; it does not claim
> PyPI publication yet.

## Highlights

- **Connector protocol family** — public `etlantic.source/1`,
  `etlantic.sink/1`, and `etlantic.storage/1` with entry points
  `etlantic.source_connectors`, `etlantic.sink_connectors`, and
  `etlantic.storage_connectors`
- **Public package `etlantic.connectors`** — typed bindings, capability
  negotiation, secret-free plan snapshots, and maturity labels
- **Frozen capability vocabulary** — including `source.batch_snapshot`,
  `source.incremental_cursor`, `source.file_glob`, `format.csv`,
  `idempotency`, `cleanup`, partitioned/pushdown/schema discovery, `write.*`,
  `publication.atomic`, `transactions`, and `reconciliation`
- **Plan vs runtime evidence split** — static plans record identity
  **scheme** only; concrete file identities live in `LandingReadManifest` /
  run report
- **Landing-zone checkpoint** — schema id `etlantic.landing_checkpoint/1`
  with snapshot and incremental modes on built-in `local-files` (**Preview**)
- **Reference set** — `etlantic-s3`, `etlantic-iceberg`,
  `etlantic-snowflake` (Experimental / Alpha); PostgreSQL connectors via
  `etlantic-sql`
- **CDK + conformance** — `etlantic.connectors.cdk` helpers and public
  `etlantic.testing` connector suites (`scripts/check_connector_conformance.py --fake`)
- **StorageBinding compatibility** — existing bindings keep working without
  false connector capability claims
- **Continuous watch out of core** — file-drop submitters compose in **0.39+**

## Adopter actions

| Who | Action |
|---|---|
| Everyone on 0.37.x | Pin `etlantic==0.38.0` and matching plugins / `medallantic==0.38.0` together when published; see [migration](../11_DEVELOPMENT/MIGRATION_0_37_TO_0_38.md) |
| Landing-zone authors | Use binding-level `snapshot` / `incremental` modes (no `Extract` rewrite) |
| Connector authors | Target `etlantic.connectors`, declare frozen vocabulary, set `etlantic>=0.38.0,<0.39`, run public conformance |
| StorageBinding users | Expect a compatibility adapter; do not assume connector capabilities |
| Cloud connector users | Treat S3 / Iceberg / Snowflake as Experimental; fake/CI path is the supported proof today |
| Control-plane / watch authors | Defer continuous directory watching to 0.39+ |

## Not in 0.38

- Continuous directory-watch loops in core (**0.39+**)
- Multi-tenant control plane (**0.39–0.43**)
- Distributed checkpoint fencing / multi-worker recovery (**0.40–0.41**)
- Supported maturity for cloud reference packages (remain Experimental)
- Independent third-party connector on PyPI (`038-X-01` soft-continue via
  in-repo EP proof; echo plugin follow-up)
- TransformationModel incubation (**0.52**)
- DataFusion Gate B graduation
- Dropping the PyPI Beta classifier

## See also

- [Migration 0.37 → 0.38](../11_DEVELOPMENT/MIGRATION_0_37_TO_0_38.md)
- [Exit gate 0.38](../11_DEVELOPMENT/EXIT_GATE_0_38.md)
- [Findings ledger 0.38](../11_DEVELOPMENT/FINDINGS_0_38.md)
- [Capability matrix](../11_DEVELOPMENT/CONNECTOR_CAPABILITY_MATRIX_0_38.json)
- [Implementation plan 0.38](../11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_38.md)
- [ADR-015: Connector Protocols](../11_DEVELOPMENT/adr/ADR-015-CONNECTOR-PROTOCOLS.md)
- [Landing-zone file connector plan](../11_DEVELOPMENT/LANDING_ZONE_CONNECTOR_PLAN.md)
- [Connector SDK overview](../07_PLUGIN_SDK/CONNECTOR_SDK.md)
- [What's New in 0.37](WHATS_NEW_0_37.md)
