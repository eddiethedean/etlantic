# etlantic-sql

SQLite and PostgreSQL reference SQL execution plugin for
[ETLantic](https://github.com/eddiethedean/etlantic) 0.37.

> **Note:** This plugin and ETLantic core use Beta classifiers for documented
> single-tenant pilots. Classifiers are not an enterprise SLA.

## Install

```bash
pip install etlantic-sql
export ETLANTIC_SQL_URL=postgresql+psycopg://user:pass@localhost:5432/etlantic
# Or use SQLite:
# export ETLANTIC_SQL_URL=sqlite+pysqlite:///:memory:
```

Uses SQLAlchemy Core. Driver dependencies stay out of `etlantic` core.

## Wiring

```python
from etlantic import Profile

Profile(name="sql-prod", sql_engine="sql")
```

The `etlantic.sql_plugins` entry point named `sql` registers
`etlantic_sql:create_plugin`. Profiles select it with `sql_engine="sql"`;
keep connection URLs in environment-backed configuration or secret providers,
not in plans.

Register `@Transformation.implementation("sql")` handlers that take
`RelationRef` inputs and return SQL query handles (not fetched rows).

## Capabilities

- SQL→SQL fusion without intermediate Python row fetch
- Durable run-scoped staging tables (not session TEMP)
- Insert-select / CTAS-style publication
- Fail-closed planning when required capabilities are missing

SQLite and PostgreSQL are Tier A in 0.33. **MERGE / upsert** is advertised only
for PostgreSQL (`sql_merge=True`, `INSERT … ON CONFLICT`); SQLite remains
`sql_merge=False` and fails closed when merge is required.

## Examples

```bash
python examples/sql_to_sql.py
python examples/sql_boundary_hybrid.py
python examples/sql_transactional_write.py
python examples/sql_failure_recovery.py
```

## Links

[SQL tutorial](https://etlantic.readthedocs.io/en/v0.37.0/06_EXECUTION/SQL_TUTORIAL/) ·
[SQL hello](https://etlantic.readthedocs.io/en/v0.37.0/06_EXECUTION/SQL_HELLO_PYPI/) ·
[Source](https://github.com/eddiethedean/etlantic/tree/main/packages/etlantic-sql) ·
[Issues](https://github.com/eddiethedean/etlantic/issues)
