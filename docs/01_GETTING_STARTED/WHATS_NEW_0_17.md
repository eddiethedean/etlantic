# What's New in 0.17

> **Status: Historical release notes for ETLantic 0.17.0.** Current line is
> **0.18.0** — see [What's new in 0.18](WHATS_NEW_0_18.md).

ETLantic 0.17.0 expanded portable transform coverage with platform
discoverability and multi-family graduation on Polars and PySpark. It is
**stable** for documented single-tenant reference deployments (see
[Capabilities](CAPABILITIES.md)).

## Gate A — Platform

- `etlantic plugin list --kind transform_compiler` inventories installed
  compilers with exact capability summaries
- Plan explain surfaces compiler capabilities and selection metadata
- Guide/packaging drift checks verify runtime↔compiler entry-point pairing
- Profile allowlists apply to transform-compiler discovery on validate, plan,
  and run paths (no unfiltered bypass)
- Distinct `missing`/`invalid` literals fail closed unless a compiler claims
  `three_state_distinct`

## Gate B — Wave 1 (Polars + PySpark)

Graduated profiles:

- `portable-string-advanced/1`
- `portable-conversion/1`
- `portable-statistics/1`
- `portable-window/1` (not `/2`)

## Gate C — Wave 2 (Polars + PySpark)

Graduated profiles:

- `portable-complex-types/1`
- `portable-complex-values/1`
- `portable-reshape/1` (`explode`)

Pandas and SQL remain kernel + `portable-relational/1` only. Unsupported
graduated requirements fail during planning under `require`.

## Continuation (not in 0.17 exit)

`portable-relational-extended/1`, `portable-temporal-iana/1`,
`portable-nondeterministic/1`, and `portable-window/2` stay authorable but
unclaimed.

## Upgrade

See [Migration 0.16 → 0.17](../11_DEVELOPMENT/MIGRATION_0_16_TO_0_17.md) and the
[portable compiler matrix](../10_REFERENCE/PORTABLE_COMPILER_MATRIX.md).
