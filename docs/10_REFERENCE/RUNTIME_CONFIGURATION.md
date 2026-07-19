# Runtime configuration (shipped)

> **Status: Available in ETLantic 0.18.0.** ETLantic does **not** load
> `etlantic.toml` today. Configure profiles, bindings, and engines in Python.
> Only the environment variables listed here are read by shipped code.

## Profiles in Python

```python
from etlantic import Profile

profile = Profile(
    name="production",
    orchestrator="local",
    dataframe_engine="polars",  # or None / "pandas"
    sql_engine="sql",           # requires etlantic-sql
    spark_engine="pyspark",     # requires etlantic-pyspark
    validation_policy="strict",
    plugin_allowlist={
        "etlantic-polars": "==0.18.0",
        "etlantic-sql": "==0.18.0",
    },
    assets={"customer_source": "customers"},
)
```

Pass `profile=` to `validate`, `plan`, `run`, and `compile_plan`.

## Environment variables

| Variable | Used by | Meaning |
|---|---|---|
| `ETLANTIC_SQL_URL` | `etlantic-sql` | SQLAlchemy URL (PostgreSQL reference; SQLite demo-only) |
| `ETLANTIC_SPARK_BACKEND` | `etlantic-pyspark` tests | Set to `sparkless` for JVM-free Spark tests |
| `ETLANTIC_SECRET_*` | `EnvSecretProvider` | Secret values when using the env provider with that prefix |

Example:

```bash
export ETLANTIC_SQL_URL=postgresql+psycopg://user:pass@localhost:5432/etlantic
# demo only:
export ETLANTIC_SQL_URL=sqlite+pysqlite:///:memory:
```

## Observability (optional)

Install the optional OpenTelemetry extra when available:

```bash
pip install 'etlantic[otel]'
```

Wire an observability provider through the public `etlantic.observability`
protocol. JSON console logging is available without OTel. See
[Logging](../06_EXECUTION/LOGGING.md) and the API reference.

## Not shipped

Do not configure these as if they exist in 0.18:

- `etlantic.toml` / `ETLANTIC_CONFIG`
- `ETLANTIC_PROFILE` auto-loading
- AWS Secrets Manager / Vault providers (OS keyring is optional via
  `etlantic-keyring`)

Proposed names live under Future Design:
[Configuration](CONFIGURATION.md) and
[Environment Variables](ENVIRONMENT_VARIABLES.md).

## See also

- [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md)
- [Secrets Management](../06_EXECUTION/SECRETS_MANAGEMENT.md)
- [Compatibility](COMPATIBILITY.md)
