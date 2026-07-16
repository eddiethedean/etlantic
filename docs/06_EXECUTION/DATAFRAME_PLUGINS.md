# Dataframe Plugins

Dataframe plugins implement physical transformation execution using a
specific dataframe library while preserving logical semantics from DTCS and
the Pipeline Plan.

**Status: shipped in 0.5.0** for Polars and Pandas.

Pipelantic does **not** depend on a dataframe library. Install plugins
separately:

```bash
pip install pipelantic-polars
pip install pipelantic-pandas
```

## Protocol

The versioned protocol is `pipelantic.dataframe/1`. Plugins implement
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

## Further reading

- [Polars](POLARS.md)
- [Pandas](PANDAS.md)
- [Dataframe Plugin SDK](../07_PLUGIN_SDK/DATAFRAME_PLUGIN.md)
- [Known limitations](../10_REFERENCE/KNOWN_ISSUES.md)
