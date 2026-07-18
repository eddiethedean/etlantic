# Execute Inside SQL

> **Status: Available in ETLantic 0.13.0.** SQLite is used only for this local
> demonstration; PostgreSQL is the reference backend.

## Install and run

```bash
python -m pip install 'etlantic==0.13.0' 'etlantic-sql==0.13.0'
git clone https://github.com/eddiethedean/etlantic.git
cd etlantic
python examples/sql_to_sql.py
```

Set `ETLANTIC_SQL_URL` to use PostgreSQL:

```bash
export ETLANTIC_SQL_URL='postgresql+psycopg://user:password@localhost/dbname'
```

Never commit a real URL. Prefer a runtime secret provider outside local demos.

## Define a typed SQL implementation

```python
@NormalizeCustomers.implementation("sql")
def normalize_sql(customers: RelationRef):
    return select(
        col("customer_id"),
        concat(col("first_name"), col("last_name"), as_="full_name"),
        source=customers,
    )
```

Select `Profile(name="sql", sql_engine="sql")` and register SQL bindings for
the source and sink tables. The example verifies that the fused region fetches
no intermediate rows into Python.

Complete source:
[`examples/sql_to_sql.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/sql_to_sql.py).

The reference plugin does not implement `MERGE`; requiring it fails closed.
See [SQL execution](SQL_EXECUTION.md) and [known limitations](../10_REFERENCE/KNOWN_ISSUES.md).
