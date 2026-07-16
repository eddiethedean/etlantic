# Examples

## Runnable now (0.6)

These scripts live in the repository `examples/` directory and are exercised by
tests:

### In-memory quickstart

```bash
python examples/quickstart.py
```

Typed contracts, a local Python implementation, validation, planning,
execution, a run report, and output inspection.

### JSON and CSV storage

```bash
python examples/file_storage.py
```

Runs built-in JSON and CSV storage bindings end-to-end.

### Dataframe parity (Polars / Pandas)

```bash
# requires pipelantic-polars / pipelantic-pandas
python examples/dataframe_parity.py polars
python examples/dataframe_parity.py pandas
```

### SQL to SQL

```bash
# requires pipelantic-sql
python examples/sql_to_sql.py
```

## Design studies (not installable)

The remaining pages in this section explore intended integrations. Each page
opens with a Future design warning. They may contain APIs, packages, or
commands that do not exist yet (or that go beyond the shipped surface).

| Topic | 0.6 status |
|---|---|
| CSV and JSON through built-in storage | Use `examples/file_storage.py` |
| Pandas and Polars pipelines | Use `examples/dataframe_parity.py` |
| SQL execution and pushdown | Use `examples/sql_to_sql.py` (+ SQL docs) |
| PySpark and streaming | Future plugin design |
| Airflow compilation | Future plugin design |
| Generated Graphviz/HTML documentation | Future design |

Do not use a design study as an installation or API reference. The
[capabilities page](../01_GETTING_STARTED/CAPABILITIES.md) and
[API reference](../10_REFERENCE/API_REFERENCE.md) define the current boundary.
