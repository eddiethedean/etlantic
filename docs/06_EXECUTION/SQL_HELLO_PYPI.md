# SQL hello (PyPI path)

> **Status: Available in ETLantic 0.43.0.** Paste-ready SQLite demo — no
> git clone. PostgreSQL is the reference backend for production; MERGE
> (`sql_merge`) is PostgreSQL-only.

!!! tip "PyPI vs clone"
    Body below is **PyPI-only**. The companion under `examples/` matches this
    page for contributors with a checkout.

After [Quickstart](../01_GETTING_STARTED/QUICKSTART.md) success on local
Python, use this page to prove `etlantic-sql` installs and runs.

Companion script (clone / optional download):
[`examples/sql_hello_pypi.py`](https://github.com/eddiethedean/etlantic/blob/v0.43.0/examples/sql_hello_pypi.py).

## 1. Install

```bash
python -m pip install 'etlantic[sql]==0.43.0'
```

SQLite is the default when `ETLANTIC_SQL_URL` is unset. For PostgreSQL later:

```bash
export ETLANTIC_SQL_URL='postgresql+psycopg://user:password@localhost/dbname'
```

Never commit real credentials. Prefer [SecretRef](../10_REFERENCE/SECRETS_DECISION.md).

## 2. Create `sql_hello.py`

Copy the complete script below into `sql_hello.py`; no repository checkout is
required.

```python
"""Minimal SQL hello — PyPI path (SQLite in-memory by default).

Requires ``etlantic-sql``. Uses ``ETLANTIC_SQL_URL`` (defaults to in-memory SQLite).
"""

from __future__ import annotations

import os

from sqlalchemy import text

from etlantic import (
    Data,
    Extract,
    Input,
    Load,
    Output,
    Pipeline,
    PipelineRuntime,
    Profile,
    Transformation,
)
from etlantic.registry import (
    BindingDescriptor,
    PlanningContext,
    builtin_stub_registry,
)
from etlantic.sql import RelationRef, col, concat, select
from etlantic.sql.discovery import register_discovered_plugins


class RawCustomer(Data):
    customer_id: int
    first_name: str
    last_name: str


class Customer(Data):
    customer_id: int
    full_name: str


class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    result: Output[Customer]


@NormalizeCustomers.implementation("sql")
def normalize_sql(customers: RelationRef):
    return select(
        col("customer_id"),
        concat(col("first_name"), col("last_name"), as_="full_name"),
        source=customers,
    )


class CustomerSqlPipeline(Pipeline):
    raw: Extract[RawCustomer] = Extract(asset="raw_customers")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Load[Customer] = Load(input=normalized.result, asset="curated_customers")


def main() -> None:
    os.environ.setdefault("ETLANTIC_SQL_URL", "sqlite+pysqlite:///:memory:")
    from etlantic_sql import create_plugin

    plugin = create_plugin()
    engine = plugin.get_engine()
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS curated_customers"))
        conn.execute(text("DROP TABLE IF EXISTS raw_customers"))
        conn.execute(
            text(
                "CREATE TABLE raw_customers ("
                "customer_id INTEGER, first_name TEXT, last_name TEXT)"
            )
        )
        conn.execute(text("INSERT INTO raw_customers VALUES (1, 'Ada', 'Lovelace')"))
        conn.execute(
            text("CREATE TABLE curated_customers (customer_id INTEGER, full_name TEXT)")
        )

    registry = builtin_stub_registry()
    register_discovered_plugins(registry, plugins={"sql": plugin})
    registry.register_binding(
        BindingDescriptor(
            binding="raw_customers",
            provider="sql",
            location="raw_customers",
        )
    )
    registry.register_binding(
        BindingDescriptor(
            binding="curated_customers",
            provider="sql",
            location="curated_customers",
            metadata={"write_intent": "insert_select"},
        )
    )

    profile = Profile(name="sql-hello", sql_engine="sql")
    context = PlanningContext.create(profile, registry=registry)
    CustomerSqlPipeline.validate(profile=profile, context=context).raise_for_errors()

    runtime = PipelineRuntime(registry=registry)
    runtime.register_sql_plugin("sql", plugin)
    report = CustomerSqlPipeline.run(profile=profile, runtime=runtime, context=context)
    print(report.status.value)


if __name__ == "__main__":
    main()
```

Then run:

```bash
python sql_hello.py
```

Optional raw download from the tagged release (still no full clone):

```bash
curl -fsSL -o sql_hello.py \
  https://raw.githubusercontent.com/eddiethedean/etlantic/v0.43.0/examples/sql_hello_pypi.py
python sql_hello.py
```

The script creates tables on the SQLAlchemy engine returned by the plugin,
registers that plugin on the runtime/registry, then validates and runs so
execution reuses the same engine (empty second engines cause `PMEXEC433`).

## Expected output

```text
succeeded
```

Anything else is a failed smoke test; the deeper tutorial shows the plan,
zero-fetch fusion evidence, and result rows.

## What this is not

- Not the `init` → CLI `run` JSON-file path (SQL assets are table bindings).
- Not PostgreSQL MERGE — use PostgreSQL and advertise `sql_merge` for upsert.
- Deeper fusion / clone CI demos: [SQL tutorial (clone)](SQL_TUTORIAL.md).

## Related

- [Engine selection](../01_GETTING_STARTED/ENGINE_SELECTION.md)
- [SQL execution](SQL_EXECUTION.md)
- [Known issues](../10_REFERENCE/KNOWN_ISSUES.md)
