# Migrating from 0.5 to 0.6

## Core remains driver-free

Installing `pipelantic` alone does not install database drivers or SQLAlchemy.
Add the SQL backend explicitly:

```bash
pip install pipelantic-sql
```

Configure a connection URL (PostgreSQL is the reference; SQLite works for
local demos):

```bash
export PIPELANTIC_SQL_URL=postgresql+psycopg://user:pass@localhost:5432/pipelantic
# or for a local demo:
export PIPELANTIC_SQL_URL=sqlite+pysqlite:///:memory:
```

## Implementation engines

Local record and dataframe implementations are unchanged:

```python
@Normalize.implementation("local")
def normalize_local(rows: list[Row]) -> list[Row]: ...

@Normalize.implementation("polars")
def normalize_polars(rows: pl.DataFrame) -> pl.DataFrame: ...
```

SQL implementations use `"sql"` and receive `RelationRef` inputs:

```python
from pipelantic.sql import RelationRef, col, concat, select

@Normalize.implementation("sql")
def normalize_sql(customers: RelationRef):
    return select(
        col("customer_id"),
        concat(col("first_name"), col("last_name"), as_="full_name"),
        source=customers,
    )
```

## Profile selection

```python
Profile(name="prod", sql_engine="sql")
```

Missing plugins fail during validation/planning, not mid-run.

## SQL→SQL fusion

When sources, transforms, and sinks stay in SQL, the runtime prefers
database-native publication (`INSERT … SELECT`, and so on) and does **not**
fetch intermediate rows into Python.

## Capability fail-closed

Unsupported features such as `MERGE` without required keys, or dialects that
cannot honor a declared write intent, fail at planning. There is no silent
emulation.

## Runnable example

See `examples/sql_to_sql.py` for a minimal end-to-end SQL pipeline.
