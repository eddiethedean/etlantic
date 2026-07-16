# Migrating from 0.4 to 0.5

## Core remains engine-free

Installing `pipelantic` alone does not install Polars, Pandas, PyArrow, or
NumPy. Add dataframe backends explicitly:

```bash
pip install pipelantic-polars
pip install pipelantic-pandas
```

## Implementation engines

Local record implementations continue to use `"local"`:

```python
@Normalize.implementation("local")
def normalize_local(rows: list[Row]) -> list[Row]: ...
```

Dataframe implementations use `"polars"` or `"pandas"` and receive native
frames:

```python
@Normalize.implementation("polars")
def normalize_polars(rows: pl.DataFrame) -> pl.DataFrame: ...
```

## Profile selection

```python
Profile(name="prod", dataframe_engine="polars")
```

Missing plugins fail during validation/planning (`PMPLAN401` / `PMPLAN410`),
not mid-run.

## Registry semantics

The built-in `local` plugin is a runtime/records path (`dataframe=False`).
It is not a Polars/Pandas substitute.

## Reports

Dataframe step metrics (collection, conversion, ownership, row counts) appear
under `StepRunReport.metadata["dataframe"]`.
