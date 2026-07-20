# Configuration in 0.21.0

ETLantic 0.21.0 configures execution with a `Profile` object or a JSON profile
document. It does **not** load `etlantic.toml`.

## Profile fields

`Profile` has these shipped fields:

| Field | Default | Purpose |
|---|---|---|
| `name` | required | Profile identity |
| `orchestrator` | `"local"` | Orchestrator selection |
| `dataframe_engine` | `"local"` | Dataframe engine, or `None` |
| `sql_engine` | `None` | SQL engine selection |
| `spark_engine` | `None` | Spark engine selection |
| `allow_trusted_sql` | `False` | Permit explicitly trusted SQL |
| `spark_udf_policy` | `"warn"` | Spark UDF policy |
| `spark_streaming` | `False` | Require Spark streaming capabilities |
| `bindings` | `{}` | Logical binding names to provider or descriptor names |
| `implementation_overrides` | `{}` | Transformation implementation overrides |
| `secret_providers` | `{}` | Logical secret-provider bindings |
| `resources` | `{}` | Logical resource bindings |
| `secrets` | `{}` | `SecretRef` values, never resolved secret values |
| `security_domain` | `"default"` | Security domain label for artifacts/caches |
| `security_mode` | `"development"` | `development` \| `test` \| `production` trust posture |
| `validation_policy` | `"default"` | Validation policy name |
| `concurrency` | `None` | Optional concurrency limit |
| `timeout_seconds` | `None` | Optional timeout |
| `retry_max_attempts` | `None` | Optional retry limit |
| `schedule` | `{}` | Portable schedule intent |
| `execution` | `{}` | Portable execution settings |
| `required_sql_capabilities` | `()` | Required SQL capabilities |
| `required_spark_capabilities` | `()` | Required Spark capabilities |
| `required_orchestrator_capabilities` | `()` | Required orchestrator capabilities |
| `plugin_allowlist` | `{}` | Plugin names and optional version specifiers |
| `portable_transform_policy` | `"prefer"` | `"require"`, `"prefer"`, or `"native"` |
| `tenant` | `"default"` | Artifact/cache isolation tenant (0.20) |
| `environment` | `"default"` | Artifact/cache isolation environment (0.20) |
| `safe_io` | `{}` | SafeIoPolicy overrides (0.20) |
| `outbound` | `{}` | OutboundPolicy overrides (0.20) |
| `require_plugin_probe` | `False` | Optional isolated capability probe (0.20) |
| `metadata` | `{}` | User metadata |

## JSON profiles

Use `write_profile` and `load_profile` for the shipped JSON format:

```python
from etlantic import Profile, load_profile, write_profile

path = write_profile(
    Profile(
        name="pilot",
        dataframe_engine="polars",
        assets={"customer_source": "json", "customer_sink": "json"},
    ),
    "profiles/pilot.json",
)
profile = load_profile(path)
```

`write_profile` creates parent directories and writes deterministic,
human-readable JSON. `load_profile` requires a JSON object and applies current
field defaults for omitted values.

The CLI `--profile` option accepts either a built-in name or an existing
`.json` path:

```bash
etlantic validate package.pipeline:CustomerPipeline --profile development
etlantic plan package.pipeline:CustomerPipeline \
  --profile profiles/pilot.json --format json
```

Built-in names are `development`/`dev`, `local`, `test`, and
`production`/`prod`. Any other bare name creates a default `Profile` with that
name. A `.json` string is loaded as a file only when that file exists.

## Environment variables shipped today

| Variable | Scope | Behavior |
|---|---|---|
| `ETLANTIC_SQL_URL` | `etlantic-sql` | SQLAlchemy URL; defaults to in-memory SQLite in the reference plugin |
| `ETLANTIC_SPARK_BACKEND` | `etlantic-pyspark` | Selects the `sparkless` compatibility backend when set to `sparkless` |
| `SPARKLESS_TEST_MODE` | PySpark test/shim paths | Non-`pyspark` values select sparkless behavior; primarily a test switch |

The built-in `EnvSecretProvider` also reads environment variables, but there
is no automatic ETLantic-wide prefix. A `SecretRef` named `database_password`
is read from `DATABASE_PASSWORD`; a non-default key such as `token` is read
from `DATABASE_PASSWORD_TOKEN`. Applications may instantiate
`EnvSecretProvider(prefix="ETLANTIC_SECRET_")` themselves and register it on a
runtime, but `ETLANTIC_SECRET_*` is not an ambient core convention.

ETLantic 0.21.0 does not auto-read `ETLANTIC_PROFILE`, `ETLANTIC_CONFIG`,
`ETLANTIC_PROJECT`, logging overrides, or output-format overrides. Names on
[Environment Variables](ENVIRONMENT_VARIABLES.md) are proposed unless this
page lists them as shipped.

## No `etlantic.toml`

Do not create `etlantic.toml` expecting 0.20.0 to load it. The
[Configuration Reference](CONFIGURATION.md) describes a future design, not the
published runtime. Use explicit Python profiles or JSON profile files today.

See also [Production Profiles](../06_EXECUTION/PRODUCTION_PROFILES.md) and
[Runtime Configuration](RUNTIME_CONFIGURATION.md).
