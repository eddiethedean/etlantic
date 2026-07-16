# Environment Variables

!!! warning "Future design—not a Pipelantic 0.6 API guide"
    This page describes a proposed 1.0 configuration surface. Pipelantic 0.5
    does not load `pipelantic.toml` or these environment variables. Configure
    profiles and bindings in Python.


Environment variables provide deployment-time overrides and references to
secrets. They should complement, not replace, explicit project configuration.

> Variable names in this chapter are proposed for Pipelantic 1.0.

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
| `PIPELANTIC_PROJECT` | Project root or configuration path |
| `PIPELANTIC_PROFILE` | Default execution profile |
| `PIPELANTIC_CONFIG` | Explicit `pipelantic.toml` path |
| `PIPELANTIC_LOG_LEVEL` | Runtime log level |
| `PIPELANTIC_LOG_FORMAT` | Console, JSON, or provider-defined format |
| `PIPELANTIC_LOG_PROVIDER` | Selected logging or observability provider |
| `PIPELANTIC_OUTPUT_FORMAT` | Default CLI output format |
| `PIPELANTIC_NO_COLOR` | Disable ANSI color when truthy |
| `PIPELANTIC_PLUGIN_DISCOVERY` | Enable or disable entry-point discovery |
| `PIPELANTIC_CACHE_DIR` | Cache directory |

## Example

```bash
export PIPELANTIC_PROFILE=production
export PIPELANTIC_LOG_LEVEL=INFO
pipelantic plan src/pipelines/customer.py:CustomerPipeline
```

## Profile Overrides

Structured profile overrides should use a documented prefix:

```text
PIPELANTIC_PROFILE__PRODUCTION__LIMITS__MAX_CONCURRENT_NODES=32
```

Double underscores delimit nested keys. Environment-based structured overrides
should be used sparingly because large configurations are easier to review in
files.

## Plugin Variables

Plugins should namespace their variables:

```text
PIPELANTIC_POLARS_STREAMING
PIPELANTIC_AIRFLOW_DAG_ID_PREFIX
PIPELANTIC_SPARK_MASTER
```

Plugin documentation must define parsing, defaults, and security behavior.

## Secrets

Environment variables are one possible Secret Provider, primarily for CI,
platform compatibility, and controlled local use:

```toml
[profiles.ci.secrets.ci-secrets]
provider = "environment"
prefix = "PIPELANTIC_SECRET_"
```

Production profiles should prefer a managed secret store and workload identity.
Pipelantic should read an environment-backed value only when the consuming
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
load `.env` files before constructing Pipelantic configuration, or an
optional integration may provide this behavior.

Production systems should prefer their platform's secret and environment
management.

## Testing

Tests should isolate environment changes:

```python
def test_production_profile(monkeypatch):
    monkeypatch.setenv("PIPELANTIC_PROFILE", "production")
    ...
```

Runtime construction should capture a configuration snapshot so later
environment mutations do not unpredictably alter an active run.

## See Also

- [Configuration](CONFIGURATION.md)
- [CLI](CLI.md)
- [Resource Provider](../07_PLUGIN_SDK/RESOURCE_PROVIDER.md)
- [Secrets Management](../06_EXECUTION/SECRETS_MANAGEMENT.md)
