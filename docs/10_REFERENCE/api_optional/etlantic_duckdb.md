# etlantic-duckdb API

Optional DuckDB SQL engine and portable transform compiler for ETLantic.

```bash
pip install 'etlantic-duckdb==0.48.0'
```

Select it explicitly with `Profile(sql_engine="duckdb")`. The package keeps
connections run-scoped, disables extension and external-access defaults, and
executes only compiler-sealed SQL artifacts.

```python
import etlantic_duckdb

plugin = etlantic_duckdb.create_plugin()
print(plugin.info.engine)
```

The plugin implements `etlantic.sql/1` and
`etlantic.transform-compiler/1`; connector capabilities remain individually
qualified by the phase evidence gate.

::: etlantic_duckdb
