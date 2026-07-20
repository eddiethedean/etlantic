# Engine selection

> **Status: Available in ETLantic 0.21.0.**

Start with core local Python. Add one engine at a time.

## Choose a path

| Goal | Install | Profile hint | Guide |
|---|---|---|---|
| Learn the model in memory | `etlantic==0.21.0` | `development` | [Quickstart](QUICKSTART.md) |
| JSON / CSV files | core only | file storage bindings | [File storage](../06_EXECUTION/FILE_STORAGE_TUTORIAL.md) |
| Fast local dataframes | `etlantic[polars]==0.21.0` | `dataframe_engine="polars"` | [Polars tutorial](../06_EXECUTION/POLARS_TUTORIAL.md) |
| Pandas compatibility | `etlantic[pandas]==0.21.0` | `dataframe_engine="pandas"` | [Pandas tutorial](../06_EXECUTION/PANDAS_TUTORIAL.md) |
| Cross-engine Polars↔Pandas | `etlantic[dataframes]==0.21.0` | both plugins allowlisted | [Interchange example](../09_EXAMPLES/INTERCHANGE_POLARS_PANDAS.md) |
| Keep work in SQL | `etlantic[sql]==0.21.0` | `sql_engine="sql"` | [SQL tutorial](../06_EXECUTION/SQL_TUTORIAL.md) |
| Local Spark batch | `etlantic[pyspark]==0.21.0` | `spark_engine="pyspark"` | [PySpark tutorial](../06_EXECUTION/PYSPARK_TUTORIAL.md) |
| Emit Airflow DAGs | `etlantic[airflow]==0.21.0` | `orchestrator="airflow"` | [Airflow tutorial](../06_EXECUTION/AIRFLOW_TUTORIAL.md) |
| Prefect local scheduler | `etlantic[prefect]==0.21.0` | `orchestrator="prefect"` | [Prefect example](../09_EXAMPLES/PREFECT_RUN.md) |
| Portable transforms (no native impl) | matching engine plugin | `portable_transform_policy="require"` | [Portable transforms](../04_TRANSFORMATIONS/PORTABLE_TRANSFORMATIONS.md) |

## Rules of thumb

1. **One engine first.** Do not combine SQL + Spark + dataframes until a single
   engine path works under `validate` and `plan`.
2. **Pin the minor in 0.x.** For ETLantic 0.19, keep core and every official
   plugin on the same release (for example `etlantic==0.21.0` with
   `etlantic-polars==0.21.0`). Do not mix 0.18 plugins with 0.19 core.
3. **Production profiles need allowlists.** Create `profiles/prod.json` from the
   embedded JSON in [Capabilities → CI starter](CAPABILITIES.md#ci-starter), or
   from [prod.example.json](prod.example.json) in a checkout. Trim the allowlist
   to engines you install (not installed with the PyPI wheel).
4. **Airflow is compile-only.** `etlantic-airflow` writes DAG artifacts; install
   Apache Airflow separately where DAGs load.
5. **Memory demos need Python seeding.** CLI `run` does not share process-local
   memory from a previous Python session.

## Capability matrix

See [Capabilities](CAPABILITIES.md) and the
[Portable Compiler Matrix](../10_REFERENCE/PORTABLE_COMPILER_MATRIX.md).
