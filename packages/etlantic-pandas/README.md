# etlantic-pandas

Pandas dataframe plugin **and** portable transform compiler for
[ETLantic](https://github.com/eddiethedean/etlantic) 0.20.

```bash
pip install 'etlantic==0.21.0' 'etlantic-pandas==0.21.0'
pip install 'etlantic-pandas[arrow]==0.21.0'  # optional Arrow interchange
```

## Dataframe plugin

The plugin provides eager, index-neutral `DataFrame` execution. It copies
frames at ownership boundaries so Pandas index state and in-place mutation do
not leak into portable pipeline semantics. Planning fails closed when a
pipeline requires unsupported lazy or zero-copy behavior.

Select it with `Profile(dataframe_engine="pandas")`; the
`etlantic.dataframe_plugins` entry point named `pandas` registers the plugin.

## Portable transform compiler

The `etlantic.transform_compilers` entry point named `pandas` exposes
`etlantic_pandas:create_transform_compiler`. The eager compiler claims
`dtcs:profile/portable-relational-kernel/1` and
`dtcs:profile/portable-relational/1`, including joins, unions, grouping,
aggregation, ordering, deduplication, and limits without requiring a native
`@implementation("pandas")`.

```python
from etlantic import Profile

profile = Profile(
    name="pandas-portable",
    dataframe_engine="pandas",
    portable_transform_policy="require",
)
```

Plugin authors can verify the advertised portable behavior with the public
conformance suite:

```python
from etlantic.testing import run_portable_transform_conformance_suite
from etlantic_pandas import create_transform_compiler

run_portable_transform_conformance_suite(create_transform_compiler())
```
