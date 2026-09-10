# Engine selection

> **Status: Available in ETLantic 0.50.1 (published Beta).**

!!! tip "PyPI vs clone"
    Recommended path below is **PyPI-only**. Rows marked clone-assisted need a
    git checkout and `uv sync`.

## Recommended next step

After Quickstart succeeds on **local** Python with its generated portable
transformation:

1. `python -m pip install 'etlantic[polars]==0.50.1'`
2. Set `dataframe_engine` to `"polars"`; keep
   `portable_transform_policy="require"` and the transformation body unchanged
   as shown in the
   [Polars tutorial (PyPI path)](../06_EXECUTION/POLARS_TUTORIAL.md)
3. Re-run `validate` → `plan` → `run` on the same project

Stay on local until that path is green. Add SQL or Spark only after one
dataframe engine works.

## Choose a path

| Goal | Install | Profile hint | Guide |
|---|---|---|---|
| Learn the model with JSON files | `etlantic==0.50.1` | `development` | [Quickstart](QUICKSTART.md) |
| JSON / CSV files | core only | file storage bindings | [File storage](../06_EXECUTION/FILE_STORAGE_TUTORIAL.md) (PyPI) |
| Fast local dataframes | `etlantic[polars]==0.50.1` | `dataframe_engine="polars"`, portable policy `"require"` | [Polars tutorial (PyPI path)](../06_EXECUTION/POLARS_TUTORIAL.md) |
| Pandas compatibility | `etlantic[pandas]==0.50.1` | `dataframe_engine="pandas"`, portable policy `"require"` | [Pandas tutorial (PyPI path)](../06_EXECUTION/PANDAS_TUTORIAL.md) |
| Cross-engine Polars↔Pandas | `etlantic[dataframes]==0.50.1` | both plugins allowlisted | [Interchange example](../09_EXAMPLES/INTERCHANGE_POLARS_PANDAS.md) (clone) |
| Keep work in SQL | `etlantic[sql]==0.50.1` | `sql_engine="sql"` | [SQL hello (PyPI)](../06_EXECUTION/SQL_HELLO_PYPI.md) → [SQL tutorial (clone)](../06_EXECUTION/SQL_TUTORIAL.md) |
| Local Spark batch | `etlantic[pyspark]==0.50.1` | `spark_engine="pyspark"` (needs Java) | [PySpark tutorial](../06_EXECUTION/PYSPARK_TUTORIAL.md) (clone-assisted) |
| Emit Airflow DAGs | `etlantic[airflow]==0.50.1` | `orchestrator="airflow"` | [Airflow tutorial](../06_EXECUTION/AIRFLOW_TUTORIAL.md) |
| Prefect local scheduler | `etlantic[prefect]==0.50.1` | `orchestrator="prefect"` | [Prefect example](../09_EXAMPLES/PREFECT_RUN.md) (clone) |
| Portable transforms (recommended) | matching engine plugin | `portable_transform_policy="require"` | [Portable transforms](../04_TRANSFORMATIONS/PORTABLE_TRANSFORMATIONS.md) |

## Rules of thumb

1. **One engine first.** Do not combine SQL + Spark + dataframes until a single
   engine path works under `validate` and `plan`.
2. **Pin the minor in 0.x.** Keep core and every official plugin on the same
   release (for example `etlantic==0.50.1` with `etlantic-polars==0.50.1`).
3. **Production profiles need allowlists.** Create `profiles/prod.json` from the
   embedded JSON in [Capabilities → CI starter](CAPABILITIES.md#ci-starter).
   Trim the allowlist to engines you install.
4. **Airflow is compile-only.** `etlantic-airflow` writes DAG artifacts; install
   Apache Airflow separately where DAGs load.
5. **Memory demos need Python seeding.** CLI `run` does not share process-local
   memory from a previous Python session.
6. **Author logic once.** Use `@Transformation.portable` within the qualified
   baseline. Native bodies pin a step to an engine and are not eligible for
   adaptive execution.

## Capability matrix

See [Capabilities](CAPABILITIES.md) and the
[Portable Compiler Matrix](../10_REFERENCE/PORTABLE_COMPILER_MATRIX.md).
