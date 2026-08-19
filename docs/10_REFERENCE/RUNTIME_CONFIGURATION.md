# Runtime configuration (shipped)

> **Status: Available in ETLantic 0.48.0.** Configure profiles, bindings, and
> engines in Python or JSON. Optional `etlantic.toml` may set `default_profile`
> and named profile references. Only the environment variables listed here are
> read by shipped code.

## Profiles in Python

```python
from etlantic import Profile

profile = Profile(
    name="production",
    security_mode="production",
    orchestrator="local",
    dataframe_engine="polars",  # or None / "pandas"
    sql_engine="sql",           # requires etlantic-sql
    spark_engine="pyspark",     # requires etlantic-pyspark
    validation_policy="strict",
    plugin_allowlist={
        "etlantic-polars": "==0.48.0",
        "etlantic-sql": "==0.48.0",
    },
    assets={"customer_source": "customers"},
)
```

Pass `profile=` to `validate`, `plan`, `run`, and `compile_plan`. Production
fail-closed trust uses `security_mode="production"` only (not the profile name).

## Optional project file

When `etlantic.toml` exists at the project root, ETLantic loads
`default_profile` and optional `[profiles]` entries. See
[Configuration today](CONFIGURATION_TODAY.md). Absent that file, profiles
resolve from `profiles/{name}.json`, built-ins, or explicit JSON paths.

## Environment variables

| Variable | Used by | Meaning |
|---|---|---|
| `ETLANTIC_SQL_URL` | `etlantic-sql` | SQLAlchemy URL (SQLite/PostgreSQL Tier A; merge is PostgreSQL-only) |
| `ETLANTIC_SPARK_BACKEND` | `etlantic-pyspark` tests | Set to `sparkless` for JVM-free Spark tests |

Secrets: follow the [Secrets decision tree](SECRETS_DECISION.md). The default
`EnvSecretProvider` maps `SecretRef(name="database_password")` to
`DATABASE_PASSWORD`. `ETLANTIC_SECRET_*` applies **only** when you register
`EnvSecretProvider(prefix="ETLANTIC_SECRET_")` yourself — it is not ambient.

Example:

```bash
export ETLANTIC_SQL_URL=postgresql+psycopg://user:pass@localhost:5432/etlantic
# or local SQLite:
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

Do not configure these as if they exist in 0.37:

- `ETLANTIC_CONFIG` / `ETLANTIC_PROFILE` / `ETLANTIC_PROJECT` auto-loading
- AWS Secrets Manager / Vault providers (OS keyring is optional via
  `etlantic-keyring`; cloud providers are planned for 0.51)

Proposed 0.37 names beyond the optional project toml live under Future Design:
[Configuration](CONFIGURATION.md) and
[Environment Variables](ENVIRONMENT_VARIABLES.md). Normative secret mapping:
[Secrets decision tree](SECRETS_DECISION.md).

## See also

- [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md)
- [Secrets Management](../06_EXECUTION/SECRETS_MANAGEMENT.md)
- [Secrets decision tree](SECRETS_DECISION.md)
- [Compatibility](COMPATIBILITY.md)
