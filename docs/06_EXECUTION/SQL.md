# SQL

SQL plugins execute eligible transformations inside a database while preserving
logical semantics from DTCS and the Pipeline Plan.

**Status: shipped in 0.6.0** via the `etlantic-sql` PostgreSQL reference
plugin. SQLite is supported for local demos only.

Lowering the future portable transformation IR to the existing safe SQL IR is
planned for 0.15. Current 0.10 SQL transformations use native
`@implementation("sql")` definitions.

ETLantic does **not** depend on database drivers. Install the plugin
separately:

```bash
pip install etlantic-sql
export ETLANTIC_SQL_URL=postgresql+psycopg://user:pass@localhost:5432/etlantic
```

## Protocol

The versioned protocol is `etlantic.sql/1`. Plugins compile typed expressions
and write intents, execute against relations, and report capabilities. The local
orchestrator consumes the resolved `PipelinePlan` without reselecting an
engine.

## Profile and implementations

```python
from etlantic import Profile
from etlantic.sql import RelationRef, col, concat, select

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
through the `etlantic.sql_plugins` entry point.

## Portable SQL lowering (planned 0.15)

Portable relational and scalar nodes will lower first into ETLantic's typed
SQL IR and then into dialect SQL:

```text
dtcs.transform-plan/2
        ↓
SqlQuery / typed SQL expressions
        ↓
safe dialect compiler
```

Identifiers remain validated and values remain bound parameters. Portable
definitions cannot contain trusted SQL fragments or raw `F.expr()` strings.
Unsupported dialect functions, types, null behavior, or ordering fail during
planning.

Window and complex-type lowering follows the experimental
`dtcs:profile/portable-window/1` and
`dtcs:profile/portable-complex-types/1`. A SQL dialect compiler advertises only
the exact profile or capabilities it passes; syntactic SQL support alone is
not sufficient.

## SQL→SQL without Python fetch

When adjacent SQL steps and sinks share a database, ETLantic fuses execution
so intermediate rows are not materialized in Python.

## Capabilities

Plugins publish capabilities such as transactions, catalog inspection, and
atomic rename/swap. The 0.6 `etlantic-sql` reference plugin does **not**
advertise `MERGE` (`sql_merge=False`); requiring merge fails closed at planning.
Unsupported requirements fail at validation or planning (fail closed).

## Further reading

- [SQL Execution](SQL_EXECUTION.md)
- [SQL Pushdown](SQL_PUSHDOWN.md)
- [SQL Plugin SDK](../07_PLUGIN_SDK/SQL_PLUGIN.md)
- [SQL Dialect](../07_PLUGIN_SDK/SQL_DIALECT.md)
- [Portable Compiler SDK](../07_PLUGIN_SDK/PORTABLE_TRANSFORM_COMPILER.md)
- [Migration 0.5 → 0.6](../11_DEVELOPMENT/MIGRATION_0_5_TO_0_6.md)
- [Known limitations](../10_REFERENCE/KNOWN_ISSUES.md)
- Runnable examples: `examples/sql_to_sql.py`, `sql_boundary_hybrid.py`,
  `sql_transactional_write.py`, `sql_failure_recovery.py`
