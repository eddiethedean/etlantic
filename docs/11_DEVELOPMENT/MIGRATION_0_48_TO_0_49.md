# Migration: 0.48 → 0.49

## Optional DuckDB installation

DuckDB is an optional package. Install it only for profiles that explicitly
select the DuckDB SQL engine:

```bash
uv sync --locked --group duckdb
# The current development checkout remains lockstep version 0.48.x until the
# 0.49 release tag is cut.
# or: pip install 'etlantic-duckdb==0.48.*'
```

Core installations remain driver-free and continue to use the existing SQL,
dataframe, and local engines.

## Profile and plan behavior

Set `Profile(sql_engine="duckdb")` when a SQL region should use DuckDB. The
portable compiler accepts only the qualified actions advertised by the
capability matrix. Requirement, type, column, and join-collision validation is
performed before staging input rows or executing SQL; update plans that relied
on unsupported operations or undeclared columns accordingly.

Unknown engines and unsupported requirements remain fail-closed. Third-party
SQL engines route by their advertised capabilities rather than by a privileged
engine-name list.

## Evidence and release checks

Run the evidence generator and the public example in CI or before packaging:

```bash
uv run python scripts/check_duckdb_0_49.py
uv run python examples/duckdb_portable.py
```

No database files, source rows, credentials, or executable backend objects are
part of plans or evidence artifacts. Roll back by removing the optional package
and selecting the previous SQL engine; no core migration is required.
