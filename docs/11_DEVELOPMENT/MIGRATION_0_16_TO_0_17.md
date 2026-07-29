# Migration 0.16 → 0.17

**Status:** required for consumers adopting graduated portable families in
ETLantic 0.17.

## Summary

0.17 graduates richer portable families on **Polars** and **PySpark**, adds
transform-compiler CLI inventory, and hardens discovery/trust. Baseline kernel
+ relational `/1` claims remain on all four first-party compilers.

## Install

```bash
pip install -U "etlantic[polars,pyspark]==0.17.0"
# or pandas/sql for baseline portable only
pip install -U "etlantic[pandas,sql]==0.17.0"
```

Official plugins require `etlantic>=0.17.0,<0.18`.

## Native → portable mapping

| Native-style need | Portable profile (Polars/PySpark) |
|---|---|
| `trim` / regex replace | `portable-string-advanced/1` |
| casts / `to_string` | `portable-conversion/1` |
| `variance` / `stddev` / `corr` | `portable-statistics/1` |
| `row_number` / rank / lag / lead | `portable-window/1` |
| arrays / structs / size | `portable-complex-values/1` + types accessors |
| `explode` | `portable-reshape/1` |

Keep `@implementation(...)` for backend-specific behavior and for continuation
families that remain unclaimed.

## Policy behavior

| Policy | Behavior |
|---|---|
| `prefer` (default) | Use portable when the engine compiler supports requirements |
| `require` | Fail closed during planning if any requirement is unsupported |
| `native` | Prefer registered native implementations |

Unsupported graduated families on Pandas/SQL fail before resource acquisition
when policy is `require`.

## Compatibility notes

- Window V1 authoring no longer emits `portable-window/2` for V1 functions
- Complex-type accessors emit `portable-complex-types/1` without forcing
  complex-values; `explode` emits reshape only (constructors still require
  complex-values)
- Plans with distinct `missing`/`invalid` literals fail analyze unless the
  compiler claims `three_state_distinct` (not shipped in 0.17)
- Transform-compiler discovery uses entry-point names as stable engine keys;
  validate, plan, and run all respect profile allowlists
- Explicit window frames fail closed until frame lowering ships

## Unchanged

- Kernel + relational `/1` baseline semantics
- Plan/[DPCS](../05_PIPELINES/DPCS.md) wire names
- Airflow compile and Prefect scheduler plugins

## Checklist

- [ ] Bump to `etlantic==0.17.0` and matching official plugins
- [ ] Inspect claims: `etlantic plugin list --kind transform_compiler --format json`
- [ ] For graduated families, target Polars or PySpark (or keep native)
- [ ] Run public conformance / differentials for any third-party compilers
- [ ] Review [What's New in 0.17](../01_GETTING_STARTED/WHATS_NEW_0_17.md)
