# etlantic-polars

Polars dataframe plugin **and** Polars portable transform compiler for
[ETLantic](https://github.com/eddiethedean/etlantic) 0.14.

```bash
pip install 'etlantic==0.14.0' 'etlantic-polars==0.14.0'
# optional Arrow interchange
pip install 'etlantic-polars[arrow]==0.14.0'
```

## Dataframe plugin

Supports eager `DataFrame` execution and `LazyFrame` preservation until an
explicit collection boundary declared in the `PipelinePlan`.

Entry point: `etlantic.dataframe_plugins` → `etlantic_polars:create_plugin`.

## Portable transform compiler (0.14)

Claims `dtcs:profile/portable-relational-kernel/1` and
`dtcs:profile/portable-relational/1`. Executes kernel actions plus join, union,
aggregate, sort, distinct, deduplicate, and limit without a native
`@implementation("polars")`.

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

Windows, complex-values, conversion, and Rich Portable Analytics compiler
claims remain later (0.15 continuation after the SQL exit gate). See the
[compiler protocol](https://etlantic.readthedocs.io/en/latest/07_PLUGIN_SDK/PORTABLE_TRANSFORM_COMPILER/)
and [compatibility matrix](https://etlantic.readthedocs.io/en/latest/10_REFERENCE/COMPATIBILITY/).
