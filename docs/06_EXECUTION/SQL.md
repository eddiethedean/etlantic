# SQL

SQL plugins execute eligible transformations inside a database while preserving
logical semantics from DTCS and the Pipeline Plan.

**Status: shipped in 0.6.0** via the `pipelantic-sql` PostgreSQL reference
plugin. SQLite is supported for local demos only.

Pipelantic does **not** depend on database drivers. Install the plugin
separately:

```bash
pip install pipelantic-sql
export PIPELANTIC_SQL_URL=postgresql+psycopg://user:pass@localhost:5432/pipelantic
```

## Protocol

The versioned protocol is `pipelantic.sql/1`. Plugins compile typed expressions
and write intents, execute against relations, and report capabilities. The local
orchestrator consumes the resolved `PipelinePlan` without reselecting an
engine.

## Profile and implementations

```python
from pipelantic import Profile
from pipelantic.sql import RelationRef, col, concat, select

Profile(name="sql-prod", sql_engine="sql")

@NormalizeCustomers.implementation("sql")
def normalize_sql(customers: RelationRef):
    return select(
        col("customer_id"),
        concat(col("first_name"), col("last_name"), as_="full_name"),
        source=customers,
    )
```

Select the engine with `Profile.sql_engine = "sql"`. Plugins are discovered
through the `pipelantic.sql_plugins` entry point.

## SQL→SQL without Python fetch

When adjacent SQL steps and sinks share a database, Pipelantic fuses execution
so intermediate rows are not materialized in Python.

## Capabilities

Plugins publish capabilities such as transactions, `MERGE`, and temporary
tables. Unsupported requirements fail at validation or planning (fail closed).

## Further reading

- [SQL Execution](SQL_EXECUTION.md)
- [SQL Pushdown](SQL_PUSHDOWN.md)
- [SQL Plugin SDK](../07_PLUGIN_SDK/SQL_PLUGIN.md)
- [SQL Dialect](../07_PLUGIN_SDK/SQL_DIALECT.md)
- [Migration 0.5 → 0.6](../11_DEVELOPMENT/MIGRATION_0_5_TO_0_6.md)
- [Known limitations](../10_REFERENCE/KNOWN_ISSUES.md)
- Runnable example: `examples/sql_to_sql.py`
