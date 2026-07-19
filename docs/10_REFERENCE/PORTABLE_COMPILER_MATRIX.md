# Portable Compiler Matrix

This matrix records the portable transformation claims shipped in ETLantic
0.14.0. It is narrower than each backend's native capabilities.

## Compiler claims

| Package | Engine | Claimed profiles | Execution mode | Join collision policy |
|---|---|---|---|---|
| `etlantic-polars==0.14.0` | Polars | `portable-relational-kernel/1`, `portable-relational/1` | Eager and lazy | `fail` only |
| `etlantic-pyspark==0.14.0` | PySpark | `portable-relational-kernel/1`, `portable-relational/1` | Eager and lazy | `fail` only |
| `etlantic-pandas==0.14.0` | Pandas | `portable-relational-kernel/1`, `portable-relational/1` | Eager only (`lazy=False`) | `fail` only |

The full profile identifiers are
`dtcs:profile/portable-relational-kernel/1` and
`dtcs:profile/portable-relational/1`. The compilers read
`dtcs.transform-plan/2` and readable v1 plans. Candidate `/2` profile metadata
is treated as an alias of the corresponding `/1` claim; this does not add
candidate extensions.

## Claimed operations

All three compilers advertise the same 0.14.0 action surface:

| Profile group | Actions |
|---|---|
| Kernel | `filter`, `project`, `with_fields`, `drop_fields`, `rename_fields` |
| Relational | `join`, `union`, `aggregate`, `sort`, `distinct`, `deduplicate`, `limit` |

The shared scalar function claim includes lower/upper, concatenation, substring
and replacement, length and string predicates, conditional/null functions, and
common numeric functions. Relational aggregates include sum, average, min,
max, count, count-all, and count-distinct. Exact claims are available at
runtime from `compiler.info.capabilities`; use those records instead of
assuming backend-wide compatibility.

Supported join types are `inner`, `left`, `right`, `full`, `outer`, `semi`,
`anti`, and `cross`. For portable plans, `collisionPolicy` must be `fail`.
Suffixing or coalescing colliding non-key columns is outside the 0.14.0 claim
and fails during analysis.

## Boundaries

- Pandas portable execution is eager. A plan requiring lazy execution is
  rejected.
- Polars and PySpark preserve backend-visible lazy operations where supported.
- Windows, complex values/types, reshape, advanced conversion/statistics, and
  extended relational profiles are not claimed (0.15 continuation backlog).
- There is no portable SQL compiler in 0.14.0. `etlantic-sql` implements the
  separate `etlantic.sql/1` execution protocol; safe portable SQL lowering for
  kernel + `portable-relational/1` is the **0.15** exit gate (SQL column to be
  added when that slice ships). Until then, use native
  `@implementation("sql")`.
- Unsupported actions, functions, modes, and profiles must fail closed during
  support analysis. Compilers do not silently fall back to UDFs or raw SQL.

## Verify claims

The public conformance suite selects fixtures from the advertised capability
record:

```python
from etlantic.testing import run_portable_transform_conformance_suite
from etlantic_polars import create_transform_compiler

run_portable_transform_conformance_suite(create_transform_compiler())
```

Official Polars, PySpark, and Pandas compilers run this suite in CI, along with
cross-engine differential tests. Third-party compilers must run it for every
advertised profile and operation.

See [Portable Transformation Compiler Protocol](../07_PLUGIN_SDK/PORTABLE_TRANSFORM_COMPILER.md),
[Third-Party Compiler Tutorial](../07_PLUGIN_SDK/THIRD_PARTY_COMPILER_TUTORIAL.md),
and [Compatibility](COMPATIBILITY.md).
