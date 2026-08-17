# Execute Inside SQL

> **Status: Available in ETLantic 0.47.0.** Prefer the
> [SQL hello (PyPI path)](SQL_HELLO_PYPI.md) first (SQLite, no clone).
> This page is the deeper clone companion. PostgreSQL is the reference
> backend for production; MERGE is PostgreSQL-only.

!!! tip "PyPI first"
    Paste [SQL hello](SQL_HELLO_PYPI.md) after Quickstart. Come here only when
    you want the repository `examples/sql_to_sql.py` fusion demo.

## Install and run (clone companion)

```bash
python -m pip install 'etlantic==0.47.0' 'etlantic-sql==0.47.0'
git clone --branch v0.47.0 https://github.com/eddiethedean/etlantic.git
cd etlantic
python examples/sql_to_sql.py
```

Set `ETLANTIC_SQL_URL` to use PostgreSQL:

```bash
export ETLANTIC_SQL_URL='postgresql+psycopg://user:password@localhost/dbname'
```

Never commit a real URL. Prefer a runtime secret provider outside local demos.

## Typed SQL implementation excerpt

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

## Expected output

The first line is plan evidence for one fused SQL region. Run identifiers and
durations vary; the invariant is that the run succeeds, no intermediate rows
are fetched into Python, and the sink contains the normalized row:

```text
[{'region': 'region:default:sql', 'engine': 'sql',
  'nodes': ['raw', 'normalized', 'curated'], ...}]
status:   succeeded
summary:  total=3 ok=3 failed=0 skipped=0 cancelled=0
rows_fetched 0
[(1, 'Ada Lovelace')]
```

PostgreSQL advertises `sql_merge=True` (`INSERT … ON CONFLICT`). SQLite
remains `sql_merge=False` and fails closed if merge is required.
See [SQL execution](SQL_EXECUTION.md) and [known limitations](../10_REFERENCE/KNOWN_ISSUES.md).
