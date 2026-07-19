# Environment Variables

!!! warning "Future design—not a ETLantic 0.18 API guide"
    This page describes a proposed 1.0 configuration surface. ETLantic 0.18
    does not load `etlantic.toml` or most of these environment variables.
    Configure profiles and bindings in Python.

    **Shipped today:** see [Runtime configuration](RUNTIME_CONFIGURATION.md)
    for `ETLANTIC_SQL_URL`, secret prefixes, and related vars.


Environment variables provide deployment-time overrides and references to
secrets. They should complement, not replace, explicit project configuration.

> Variable names in this chapter (except `ETLANTIC_SQL_URL`) are proposed
> for ETLantic 1.0.

## Precedence

From lowest to highest priority:

1. Built-in defaults
2. Project configuration
3. Selected profile
4. Environment variables
5. CLI options or explicit Python arguments

## Core Variables

| Variable | Purpose |
|---|---|
| `ETLANTIC_PROJECT` | Project root or configuration path |
| `ETLANTIC_PROFILE` | Default execution profile |
| `ETLANTIC_CONFIG` | Explicit `etlantic.toml` path |
| `ETLANTIC_LOG_LEVEL` | Runtime log level |
| `ETLANTIC_LOG_FORMAT` | Console, JSON, or provider-defined format |
| `ETLANTIC_LOG_PROVIDER` | Selected logging or observability provider |
| `ETLANTIC_OUTPUT_FORMAT` | Default CLI output format |
| `ETLANTIC_NO_COLOR` | Disable ANSI color when truthy |
| `ETLANTIC_PLUGIN_DISCOVERY` | Enable or disable entry-point discovery |
| `ETLANTIC_CACHE_DIR` | Cache directory |

## Example

```bash
export ETLANTIC_PROFILE=production
export ETLANTIC_LOG_LEVEL=INFO
etlantic plan src/pipelines/customer.py:CustomerPipeline
```

## Profile Overrides

Structured profile overrides should use a documented prefix:

```text
ETLANTIC_PROFILE__PRODUCTION__LIMITS__MAX_CONCURRENT_NODES=32
```

Double underscores delimit nested keys. Environment-based structured overrides
should be used sparingly because large configurations are easier to review in
files.

## Plugin Variables

Plugins should namespace their variables:

```text
ETLANTIC_SQL_URL              # shipped: SQLAlchemy URL for etlantic-sql
ETLANTIC_POLARS_STREAMING
ETLANTIC_AIRFLOW_DAG_ID_PREFIX
ETLANTIC_SPARK_MASTER
```

Plugin documentation must define parsing, defaults, and security behavior.
Never log resolved DSNs with credentials; ETLantic redacts connection
secrets in diagnostics where possible.

## Secrets

Environment variables are one possible Secret Provider, primarily for CI,
platform compatibility, and controlled local use:

```toml
[profiles.ci.secrets.ci-secrets]
provider = "environment"
prefix = "ETLANTIC_SECRET_"
```

Production profiles should prefer a managed secret store and workload identity.
ETLantic should read an environment-backed value only when the consuming
resource is acquired.

Never:

- Include secret values in generated contracts
- Print them in `config show`
- Attach them to diagnostics
- Put them in a `PipelinePlan` intended for serialization
- Persist them in cache keys

## Boolean Values

Accepted truthy values should be predictable:

```text
1, true, yes, on
```

Accepted false values:

```text
0, false, no, off
```

Invalid values should produce configuration diagnostics rather than silently
choosing a default.

## `.env` Files

Automatic `.env` loading should not be required by the core. Applications may
load `.env` files before constructing ETLantic configuration, or an
optional integration may provide this behavior.

Production systems should prefer their platform's secret and environment
management.

## Testing

Tests should isolate environment changes:

```python
def test_production_profile(monkeypatch):
    monkeypatch.setenv("ETLANTIC_PROFILE", "production")
    ...
```

Runtime construction should capture a configuration snapshot so later
environment mutations do not unpredictably alter an active run.

## See Also

- [Configuration](CONFIGURATION.md)
- [CLI](CLI.md)
- [Resource Provider](../07_PLUGIN_SDK/RESOURCE_PROVIDER.md)
- [Secrets Management](../06_EXECUTION/SECRETS_MANAGEMENT.md)
