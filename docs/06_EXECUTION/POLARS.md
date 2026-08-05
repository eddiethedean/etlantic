# Polars Plugin

**Status: shipped in 0.5.0** as the reference dataframe backend
(`etlantic-polars`).

The portable transformation compiler shipped kernel claims in 0.12, full
`portable-relational/1` claims in 0.13, and the graduated 0.17 advanced
families listed in the portable compiler matrix.

## Install

```bash
pip install 'etlantic[polars]==0.45.0'
pip install 'etlantic-polars[arrow]==0.45.0'  # optional Arrow interchange
```

## Behavior

- Eager `DataFrame` execution is the baseline
- `LazyFrame` values are preserved across adjacent Polars steps
- Collection happens only at plan-declared boundaries (sink publication,
  cross-engine conversion, explicit collection points)
- Contract ↔ Polars dtype mapping with structured diagnostics for unsupported
  types
- Sync and async implementation callables are supported
- Portable kernel IR compiles via `etlantic.transform_compilers` without a
  native `@implementation("polars")` callable

## Portable compiler

The Polars compiler is the first executable lowering for
`dtcs.transform-plan/2` (v1 readable). It claims
`dtcs:profile/portable-relational-kernel/1` and, from **0.13**,
`dtcs:profile/portable-relational/1` (plan-v2 `/2` profile requirements are
metadata aliases — no candidate `/2` extensions). It:

- lowers portable columns to native `pl.Expr` values
- lowers kernel and relational nodes (join, union, aggregate, sort, distinct,
  deduplicate, limit) to `DataFrame` / `LazyFrame` operations
- preserves `LazyFrame` across compatible portable steps
- rejects unsupported modes during planning with action/expression paths
- retains logical expression and output mappings
- collects only at plan-declared boundaries

It must not fall back to Python row functions or collect data to emulate an
unsupported operation. In 0.17 it also claims string-advanced, conversion,
statistics, window `/1`, complex-types, complex-values, and reshape `/1`.
Explicit window frames and continuation families remain unsupported.

## Example

See `examples/dataframe_parity.py` in the repository:

```bash
uv run --group dataframes python examples/dataframe_parity.py polars
```
