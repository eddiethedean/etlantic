# Dataframe Plugins

Dataframe plugins implement physical transformation execution using a
specific dataframe library while preserving logical semantics from DTCS and
the Pipeline Plan.

**Status: shipped in 0.5.0** for Polars and Pandas.

Portable transformation compilation is a separate accepted 0.11+ design. The
current 0.10 plugins invoke engine-specific `@implementation()` callables.

ETLantic does **not** depend on a dataframe library. Install plugins
separately:

```bash
pip install etlantic-polars
pip install etlantic-pandas
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

## Portable compilation (0.11+)

Dataframe plugins will additionally analyze and compile
DTCS Transformation Plans produced by portable definitions:

```python
@NormalizeCustomers.portable
def normalize(customers):
    return customers.select("customer_id", "full_name")
```

The plugin converts symbolic inputs into native expressions, preserves
portable semantics, validates native frames at contract boundaries, and
normalizes named outputs. Operation support is advertised individually and
unsupported expressions fail during planning.

## Further reading

- [Polars](POLARS.md)
- [Pandas](PANDAS.md)
- [Dataframe Plugin SDK](../07_PLUGIN_SDK/DATAFRAME_PLUGIN.md)
- [Portable Compiler SDK](../07_PLUGIN_SDK/PORTABLE_TRANSFORM_COMPILER.md)
- [Known limitations](../10_REFERENCE/KNOWN_ISSUES.md)
