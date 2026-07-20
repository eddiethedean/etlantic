# Portable Compiler Matrix

This matrix records the portable transformation claims shipped in ETLantic
0.20.0. It is narrower than each backend's native capabilities.

## Compiler claims

| Package | Engine | Claimed profiles | Execution mode | Join collision policy |
|---|---|---|---|---|
| `etlantic-polars==0.21.0` | Polars | kernel `/1`, relational `/1`, `portable-string-advanced/1`, `portable-conversion/1`, `portable-statistics/1`, `portable-window/1`, `portable-complex-values/1`, `portable-complex-types/1`, `portable-reshape/1` | Eager and lazy | `fail` only |
| `etlantic-pyspark==0.21.0` | PySpark | kernel `/1`, relational `/1`, `portable-string-advanced/1`, `portable-conversion/1`, `portable-statistics/1`, `portable-window/1`, `portable-complex-values/1`, `portable-complex-types/1`, `portable-reshape/1` | Eager and lazy | `fail` only |
| `etlantic-pandas==0.21.0` | Pandas | kernel `/1`, relational `/1` | Eager only (`lazy=False`) | `fail` only |
| `etlantic-sql==0.21.0` | SQL | kernel `/1`, relational `/1` | Eager (relation/SQL) | `fail` only |

Full profile identifiers use the `dtcs:profile/` prefix (for example
`dtcs:profile/portable-window/1`). Compilers read `dtcs.transform-plan/2` and
readable v1 plans. Candidate `/2` kernel/relational metadata is treated as an
alias of the corresponding `/1` claim.

## Graduated 0.17 families (Polars + PySpark)

| Profile | Representative claims |
|---|---|
| `portable-string-advanced/1` | `trim`, `ltrim`, `rtrim`, `regex_extract`, `regex_replace`, `split` |
| `portable-conversion/1` | `to_string`, `try_cast`, `cast`, `to_integer` |
| `portable-statistics/1` | `variance`, `stddev`, `corr` (sample semantics) |
| `portable-window/1` | `row_number`, `rank`, `dense_rank`, `lag`, `lead`, `first_value`, `last_value` |
| `portable-complex-values/1` | `array`, `object`, `size` (`map` on PySpark; Polars rejects `map`) |
| `portable-complex-types/1` | `field`, `index`, `element_at` |
| `portable-reshape/1` | `explode` |

Pandas and SQL remain baseline-only in 0.17 (kernel + relational `/1`). Plans
that require graduated families under `portable_transform_policy=require` fail
closed during planning on those engines.

## Claimed baseline operations

All four compilers advertise the same baseline action surface:

| Profile group | Actions |
|---|---|
| Kernel | `filter`, `project`, `with_fields`, `drop_fields`, `rename_fields` |
| Relational | `join`, `union`, `aggregate`, `sort`, `distinct`, `deduplicate`, `limit` |

Exact claims are available at runtime from `compiler.info.capabilities` and via
`etlantic plugin list --kind transform_compiler --format json`.

Supported join types are `inner`, `left`, `right`, `full`, `outer`, `semi`,
`anti`, and `cross`. For portable plans, `collisionPolicy` must be `fail`.

## Boundaries

- Pandas portable execution is eager. A plan requiring lazy execution is
  rejected.
- Polars and PySpark preserve backend-visible lazy operations where supported.
- SQL portable lowering targets typed `etlantic.sql/1` with bound parameters
  only. Trusted SQL fragments are forbidden in portable definitions.
- Distinct `missing` / `invalid` three-state literals fail closed unless a
  compiler advertises `semantic_mode:three_state_distinct` (not claimed in
  0.17).
- Explicit window frames fail closed until frame lowering ships; omit
  `rowsBetween` / `rangeBetween` in portable Window V1 plans.
- Continuation families remain unclaimed: `portable-relational-extended/1`,
  `portable-temporal-iana/1`, `portable-nondeterministic/1`, `portable-window/2`.
- Unsupported actions, functions, modes, and profiles must fail closed during
  support analysis. Compilers do not silently fall back to UDFs or raw SQL.

## Verify claims

```python
from etlantic.testing import run_portable_transform_conformance_suite
from etlantic_polars import create_transform_compiler

run_portable_transform_conformance_suite(create_transform_compiler())
```

Official Polars, PySpark, Pandas, and SQL compilers run this suite in CI,
along with cross-engine differential tests. Third-party compilers must run it
for every advertised profile and operation.

See [Portable Transformation Compiler Protocol](../07_PLUGIN_SDK/PORTABLE_TRANSFORM_COMPILER.md),
[Third-Party Compiler Tutorial](../07_PLUGIN_SDK/THIRD_PARTY_COMPILER_TUTORIAL.md),
and [Compatibility](COMPATIBILITY.md).
