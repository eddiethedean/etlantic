# etlantic-sql

SQLite and PostgreSQL reference SQL execution plugin for
[ETLantic](https://github.com/eddiethedean/etlantic) **0.43**. Install when
pipelines need `Profile(sql_engine="sql")`, SQL→SQL fusion, or Experimental
`postgresql` source/sink/storage connectors. Keep the pin matched to core.

> **Note:** This plugin and ETLantic core use Beta classifiers for documented
> single-tenant pilots. Classifiers are not an enterprise SLA.

## Install

```bash
pip install 'etlantic-sql==0.55.0'
# pip install 'etlantic==0.55.0'
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

Prefer `@Transformation.portable` with
`portable_transform_policy="require"`; the compiler lowers the qualified
baseline to typed, parameterized SQL. Register
`@Transformation.implementation("sql")` only when dialect-specific behavior
outside that baseline is required. Native handlers take `RelationRef` inputs
and return SQL query handles (not fetched rows); they are tied to SQL and are
not eligible for adaptive execution.

## Capabilities

- SQL→SQL fusion without intermediate Python row fetch
- Durable run-scoped staging tables (not session TEMP)
- Insert-select / CTAS-style publication
- Fail-closed planning when required capabilities are missing

SQLite and PostgreSQL are Tier A in 0.33. **MERGE / upsert** is advertised only
for PostgreSQL (`sql_merge=True`, `INSERT … ON CONFLICT`); SQLite remains
`sql_merge=False` and fails closed when merge is required.

## Inference target mode reference (0.55)

`SQLiteTableTarget` is a separate, explicit reference adapter for an existing
SQLite table. It inspects declared columns, primary keys, and configured
partition columns without reading rows. Its transactional `write_records`
method executes append, overwrite, merge, upsert, and partition replacement
only when the table advertises the requested mode and its revision still
matches. This adapter does not change the SQL engine capability setting above.

```python
import sqlite3
import etlantic as etl
from etlantic_sql import SQLiteTableTarget

connection = sqlite3.connect("orders.db")
target = SQLiteTableTarget(
    connection, "orders", identity="orders", partitions=("order_day",)
)
observation = etl.inspect_target(target)
```

## PostgreSQL connectors (0.56 implementation; Experimental)

The `postgresql` source, sink and storage entry points use SQLAlchemy and
psycopg against a live PostgreSQL database. They require a runtime
`SecretValue` containing the connection URL, or a worker-level
`ETLANTIC_SQL_URL`. Put table and mode options in the public asset config; do
not put a URL or credential in that config. The source reads one repeatable
read snapshot, with configurable `row_limit`, `batch_size` and `max_bytes`
(bounded to 100,000 rows, 10,000 records per batch and 256 MiB). Schema
inspection reads catalog metadata and PostgreSQL's row estimate without
creating or changing a target.

The sink supports `append`, `replace`/`overwrite`, and `upsert`. Upsert
requires `key_columns` that match a primary or unique constraint. Commit
recovery relies on a provisioned durable effect ledger. Provision it once
through a database administrator or migration before enabling sink writes:

```sql
CREATE TABLE public.etlantic_connector_effects (
    effect_id text PRIMARY KEY,
    intent_fingerprint text NOT NULL,
    publication_id text NOT NULL UNIQUE,
    row_count bigint NOT NULL,
    committed_at timestamptz NOT NULL DEFAULT now()
);
```

The worker takes a transaction-scoped advisory lock for each stable run/node
effect ID, changes the target and inserts the ledger row in the same
transaction. Reconciliation consults that row; an unavailable ledger returns
`unknown`. An effect ID bound to different write intent fails closed. The
SQLite-backed fake remains available as `FakePostgresConnection` for fast
connector unit tests; it is not registered as the PostgreSQL provider.

During managed execution, PostgreSQL source and sink connectors also provide
opaque resource identities to the worker. Before opening a sink write session,
the runtime compares source and target identities, including the live server
address and normalized schema/table. A matching identity, or a same-provider
transfer whose identities cannot be verified, fails with `PMEXEC435` before
target mutation. The comparison tokens use a worker-process key and stay in
memory; credentials and raw database/resource names are not written to plans,
receipts or reports.

### Explicit action provisioning

For deployments that grant `connector.provision`, the package also provides
`etlantic_sql.create_action_handlers(resolve_engine)`. The callback receives
the action worker's trusted `ControlPlaneContext` and an opaque saved
connection ID, then returns an application-owned SQLAlchemy engine. The
factory registers PostgreSQL table create and cleanup handlers; connection
URLs and credentials stay inside the deployment callback.

Provisioning is create-only. The handler accepts only a typed table schema
with safe identifiers, refuses an existing unmanaged table, and records the
action ID, owner scope, schema fingerprint and effect ID in the same database.
Retries of one accepted action recover the recorded receipt instead of
recreating the table. Cleanup requires the worker-verified successful parent
provision receipt and removes only that exact effect; its tombstone makes a
cleanup retry idempotent. The action factory performs no database writes when
constructed, and the Foundry storage inspection handler remains read-only.
The SQLite-backed unit case and isolated PostgreSQL loopback qualification
exercise create-only conflict, receipt recovery and compensation.

| Capability | Source | Sink | Storage | Notes |
|---|:---:|:---:|:---:|---|
| `source.batch_snapshot` | ✓ | | | Bounded table read |
| `source.schema_discovery` | ✓ | | ✓ | Row-free field inspect |
| `source.statistics_bounded` | ✓ | | ✓ | PostgreSQL catalog estimate |
| `write.append` | | ✓ | | Transactional |
| `write.overwrite` | | ✓ | | DELETE + INSERT |
| `write.merge` | | ✓ | | `ON CONFLICT` with declared unique key |
| `publication.atomic` | | ✓ | | Commit / rollback |
| `transactions` | | ✓ | | Autocommit-off path |
| `reconciliation` | | ✓ | | Durable effect ledger |
| `idempotency` | | ✓ | | Sink effect ledger; PostgreSQL source reads are per-run snapshots |

Entry points: `etlantic.source_connectors` / `sink_connectors` /
`storage_connectors` → `postgresql`.

## Examples

```bash
python examples/sql_to_sql.py
python examples/sql_boundary_hybrid.py
python examples/sql_transactional_write.py
python examples/sql_failure_recovery.py
```

## Links

[SQL tutorial](https://etlantic.readthedocs.io/en/v0.55.0/06_EXECUTION/SQL_TUTORIAL/) ·
[SQL hello](https://etlantic.readthedocs.io/en/v0.55.0/06_EXECUTION/SQL_HELLO_PYPI/) ·
[Source](https://github.com/eddiethedean/etlantic/tree/main/packages/etlantic-sql) ·
[Issues](https://github.com/eddiethedean/etlantic/issues)
