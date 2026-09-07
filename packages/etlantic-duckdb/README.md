# etlantic-duckdb

Optional DuckDB support for ETLantic 0.49. The package is driver-free from core and
is selected explicitly with `Profile(sql_engine="duckdb")`.

The plugin uses one explicit DuckDB connection per run, keeps backend relation
objects private to that run, and rejects unbounded external access, extension
installation/loading, trusted SQL fragments, and caller-constructed compiled
statements by default.
