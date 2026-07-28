# Migrating from 0.5 to 0.6

## Core remains driver-free

Installing `etlantic` alone does not install database drivers or SQLAlchemy.
Add the SQL backend explicitly:

```bash
pip install etlantic-sql
# or: pip install 'etlantic[sql]'
```

Configure a connection URL (PostgreSQL is the reference; SQLite works for
local demos):

```bash
export ETLANTIC_SQL_URL=postgresql+psycopg://user:pass@localhost:5432/etlantic
# or for a local demo:
export ETLANTIC_SQL_URL=sqlite+pysqlite:///:memory:
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
from etlantic import Profile
from etlantic.sql import RelationRef, col, concat, select

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

Keep `dataframe_engine` for Polars/Pandas; do not set it to `"sql"`.
Missing plugins fail during validation/planning, not mid-run.

## SQL→SQL fusion

When sources, transforms, and sinks stay in SQL, the runtime prefers
database-native publication (`INSERT … SELECT`, and so on) and does **not**
fetch intermediate rows into Python. Intermediate SQL results use durable
run-scoped staging tables (not session TEMP) so handoffs work across
connection pools.

## Capability fail-closed

The 0.6 reference plugin advertises `sql_merge=False`. Requiring
`sql_merge` (or any other unsupported capability) fails at planning. Invalid
`write_intent` values and failed writes fail closed; unknown commit outcomes
are never retried blindly. There is no silent emulation of MERGE or
unsupported publication strategies.

## Hybrid boundaries

- SQL → Python/dataframe: planned fetch + contract validation at the region
  boundary.
- Python/dataframe → SQL: records are loaded into the sink relation via
  `load_records` when the sink binding provider is `"sql"`.

Compiled SQL artifacts stay secret-free (parameter values are redacted;
live binds never appear in `CompiledSql.to_dict()`).

## Runnable examples

- `examples/sql_to_sql.py` — SQL→SQL normalize with no Python row fetch
- `examples/sql_boundary_hybrid.py` — SQL → Python boundary
- `examples/sql_transactional_write.py` — insert-select publication
- `examples/sql_failure_recovery.py` — unsupported merge fails before mutation
