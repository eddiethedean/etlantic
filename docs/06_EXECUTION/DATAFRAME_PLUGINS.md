# Dataframe Plugins

Dataframe plugins implement physical transformation execution using a
specific dataframe library while preserving logical semantics from DTCS and
the Pipeline Plan.

**Status: shipped in 0.5.0** for Polars and Pandas dataframe execution.
**0.13** adds Polars **kernel** portable compilation via the same
`etlantic-polars` package (`etlantic.transform_compilers`).

Native `@implementation()` callables remain available for both engines.
Portable execution without a native Polars callable works for the kernel claim
set when `Profile.portable_transform_policy` is `prefer` or `require`.

ETLantic does **not** depend on a dataframe library. Install plugins
separately:

```bash
pip install 'etlantic-polars==0.13.0'
pip install 'etlantic-pandas==0.13.0'
```

## Protocol

The versioned protocol is `etlantic.dataframe/1`. Plugins implement
materialize → invoke → normalize → validate → metrics → cleanup. The local
orchestrator consumes the resolved `PipelinePlan` without reselecting an
engine.

## Capabilities

Plugins publish capabilities such as eager/lazy execution, Arrow import and
export, schema inspection, invalid-row separation, cancellation, and
thread-safety. Unsupported requirements fail at validation or planning.

## Implementations

```python
@NormalizeCustomers.implementation("polars")
def normalize_polars(customers: pl.DataFrame) -> pl.DataFrame: ...

@NormalizeCustomers.implementation("pandas")
def normalize_pandas(customers: pd.DataFrame) -> pd.DataFrame: ...
```

Select the engine with `Profile.dataframe_engine = "polars"` or `"pandas"`.

## Portable compilation (0.13 Polars kernel)

Transform compilers analyze and compile DTCS Transformation Plans produced by
portable definitions:

```python
@NormalizeCustomers.portable
def normalize(customers):
    return customers.select("customer_id", "full_name")
```

`etlantic-polars` converts supported kernel IR into native expressions,
preserves portable semantics, validates frames at contract boundaries, and
normalizes named outputs. Unsupported expressions fail during planning
(`PMXFORM301`). See `examples/portable_polars_kernel.py`.

## Further reading

- [Polars](POLARS.md)
- [Pandas](PANDAS.md)
- [Dataframe Plugin SDK](../07_PLUGIN_SDK/DATAFRAME_PLUGIN.md)
- [Portable Compiler SDK](../07_PLUGIN_SDK/PORTABLE_TRANSFORM_COMPILER.md)
- [Known limitations](../10_REFERENCE/KNOWN_ISSUES.md)
