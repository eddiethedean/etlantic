# SQL hello (PyPI path)

> **Status: Available in ETLantic 0.35.0.** Paste-ready SQLite demo — no
> git clone. PostgreSQL is the reference backend for production; MERGE
> (`sql_merge`) is PostgreSQL-only.

!!! tip "PyPI vs clone"
    Body below is **PyPI-only**. The companion under `examples/` is optional
    for contributors with a checkout.

After [Quickstart](../01_GETTING_STARTED/QUICKSTART.md) success on local
Python, use this page to prove `etlantic-sql` installs and runs.

Companion script (clone):
[`examples/sql_hello_pypi.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/sql_hello_pypi.py).

## 1. Install

```bash
python -m pip install 'etlantic[sql]==0.35.0'
```

SQLite is the default when `ETLANTIC_SQL_URL` is unset. For PostgreSQL later:

```bash
export ETLANTIC_SQL_URL='postgresql+psycopg://user:password@localhost/dbname'
```

Never commit real credentials. Prefer [SecretRef](../10_REFERENCE/SECRETS_DECISION.md).

## 2. Run the companion (clone) or paste the script

```bash
# from a matching checkout:
python examples/sql_hello_pypi.py
```

Or save the same script locally as `sql_hello.py` and run `python sql_hello.py`.
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
