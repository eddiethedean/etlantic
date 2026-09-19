# etlantic-polars

Polars dataframe plugin **and** Polars portable transform compiler for
[ETLantic](https://github.com/eddiethedean/etlantic) **0.43**. Install when
you select `Profile(dataframe_engine="polars")` or need portable DTCS
compilation on Polars. Keep the pin matched to core.

> **Note:** This plugin and ETLantic core use Beta classifiers for documented
> single-tenant pilots. Classifiers are not an enterprise SLA.

## Install

```bash
pip install 'etlantic-polars==0.54.0'
# Optional Arrow interchange:
pip install 'etlantic-polars[arrow]==0.54.0'
# pip install 'etlantic==0.54.0'
```

## Dataframe plugin

Supports eager `DataFrame` execution and `LazyFrame` preservation until an
explicit collection boundary declared in the `PipelinePlan`.

Entry point: `etlantic.dataframe_plugins` → `etlantic_polars:create_plugin`.

## Portable transform compiler

Claims `dtcs:profile/portable-relational-kernel/1` and
`dtcs:profile/portable-relational/1`. Executes kernel actions plus join, union,
aggregate, sort, distinct, deduplicate, and limit without a native
`@implementation("polars")`.
This is the recommended transformation path and remains eligible for adaptive
execution; a native Polars body pins its step to Polars.

```python
from etlantic import Profile
from etlantic_polars import create_transform_compiler

Profile(
    name="polars-portable",
    dataframe_engine="polars",
    portable_transform_policy="require",  # or prefer / native
)
compiler = create_transform_compiler()
print(compiler.info.name, sorted(compiler.info.capabilities.profiles))
```

Entry point: `etlantic.transform_compilers` →
`etlantic_polars:create_transform_compiler`.

Runnable example: `examples/portable_polars_kernel.py` in the ETLantic repo.

Window V1, complex-type/value, and conversion profiles are available in the
current compiler; explicit window frames and Window V2 remain capability-gated.
See the
[compiler protocol](https://etlantic.readthedocs.io/en/v0.54.0/07_PLUGIN_SDK/PORTABLE_TRANSFORM_COMPILER/)
and [compatibility matrix](https://etlantic.readthedocs.io/en/v0.54.0/10_REFERENCE/COMPATIBILITY/).

## Bounded Parquet snapshots

`create_parquet_storage()` reads a single policy-approved source through a
verified handle into bounded immutable bytes. Native scans use those bytes,
so replacing or renaming the source or its parent cannot replace the snapshot.
No filesystem artifact or additional approved root is required. Keep scans
inside `open_scan()` until all native work has drained; cancellation of an
ordinary read waits for that work.

A bounded Compact-Thrift footer pass removes optional file key/value metadata,
including `ARROW:schema`, before PyArrow or Polars constructs a reader. Custom
Arrow extension semantics are discarded without invoking deserializers; every
physical column must still pass the primitive int64/boolean gate. PyArrow 14
and later are supported without the newer `arrow_extensions_enabled` keyword.
The snapshot uses memory proportional to the configured byte budget, including
bounded copies during footer sanitization and native scan construction.

The cleanup inspection methods remain available for compatibility. Buffer
snapshots create no disk cleanup obligations; unknown cleanup tokens reject.

## Links

[Polars tutorial](https://etlantic.readthedocs.io/en/v0.54.0/06_EXECUTION/POLARS_TUTORIAL/) ·
[Source](https://github.com/eddiethedean/etlantic/tree/main/packages/etlantic-polars) ·
[Issues](https://github.com/eddiethedean/etlantic/issues)
