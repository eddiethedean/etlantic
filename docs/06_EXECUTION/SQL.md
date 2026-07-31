# SQL

SQL plugins execute eligible transformations inside a database while preserving
logical semantics from [DTCS](../04_TRANSFORMATIONS/DTCS.md) and the Pipeline Plan.

**Status: available in 0.40.0.** `etlantic-sql` treats SQLite and PostgreSQL
as live Tier A dialects. PostgreSQL alone advertises `sql_merge`.

Safe portable SQL lowering for kernel + `portable-relational/1` **shipped in
0.15** via the `etlantic-sql` transform compiler. Native
`@implementation("sql")` remains fully supported.

ETLantic does **not** depend on database drivers. Install the plugin
separately:

```bash
pip install 'etlantic[sql]==0.40.0'
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

## Portable SQL lowering (shipped in 0.15)

Portable kernel and `portable-relational/1` nodes lower into typed
`etlantic.sql/1` IR and then into dialect SQL (PostgreSQL via `etlantic-sql`
is the reference):

```text
dtcs.transform-plan/2
        ↓
SqlQuery / typed SQL expressions
        ↓
safe dialect compiler
```

```python
from etlantic.testing import run_portable_transform_conformance_suite
from etlantic_sql import create_transform_compiler

run_portable_transform_conformance_suite(create_transform_compiler())
```

Identifiers remain validated and values remain bound parameters. Portable
definitions cannot contain trusted SQL fragments or raw `F.expr()` strings.
Unsupported dialect functions, types, null behavior, or ordering fail during
planning with `PMXFORM*` diagnostics — never via raw SQL or UDF approximation.

Policy when portable SQL cannot claim the needed profile:

- `portable_transform_policy="require"` fails closed at planning;
- `prefer` may select an **explicit native** `@implementation("sql")` only —
  never silent portable emulation, and never an implicit fall-back to Polars
  or another dataframe engine;
- `native` prefers a registered SQL implementation.

SQL remains baseline-only in 0.17. Advanced families such as window,
conversion, complex types/values, and reshape fail closed under `require`;
use an explicit native SQL implementation where needed.

## SQL→SQL without Python fetch

When adjacent SQL steps and sinks share a database, ETLantic fuses execution
so intermediate rows are not materialized in Python.

## Capabilities

Plugins publish capabilities such as transactions, catalog inspection, and
atomic rename/swap. The current `etlantic-sql` reference plugin advertises
`sql_merge=True` for PostgreSQL and `sql_merge=False` for SQLite; requiring
merge on SQLite fails closed at planning.
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
