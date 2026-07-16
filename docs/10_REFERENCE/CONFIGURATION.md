# Configuration Reference

!!! warning "Future design—not a Pipelantic 0.6 API guide"
    This page describes a proposed 1.0 configuration surface. Pipelantic 0.5
    does not load `pipelantic.toml` or these environment variables. Configure
    profiles and bindings in Python.


Pipelantic configuration binds portable pipeline models to concrete
environments without embedding execution details in `Pipeline`,
`Transformation`, or data-contract classes.

> This chapter defines the proposed configuration model for Pipelantic 1.0.

## Configuration Sources

Configuration may come from:

1. Built-in defaults
2. Project configuration
3. Included configuration files
4. Selected profile
5. Environment variables
6. CLI options or explicit Python arguments

Later sources take precedence over earlier sources.

## Project File

The preferred project file is:

```text
pipelantic.toml
```

Example:

```toml
[project]
name = "customer-platform"
pipeline_paths = ["src/pipelines"]
contract_paths = ["contracts"]
generated_dir = "build/generated"

[defaults]
profile = "local"
strict = true

[plugins]
orchestrator = "local"
dataframe = "polars"

[profiles.local]
orchestrator = "local"
dataframe = "polars"

[profiles.production]
orchestrator = "airflow"
dataframe = "pyspark"

[profiles.production.settings]
max_concurrent_nodes = 32

[logging]
level = "INFO"
format = "console"
include_context = true
```

YAML may be supported by an optional loader, but one canonical project format
reduces ambiguity.

## Profiles

Profiles supply environment-specific bindings:

```toml
[profiles.local]
orchestrator = "local"
dataframe = "pandas"

[profiles.production]
extends = "base-production"
orchestrator = "airflow"
dataframe = "polars"
```

A profile may define:

- Orchestration backend
- Transformation engine defaults
- Source and sink bindings
- Resource providers
- Concurrency limits
- Retry and timeout policy
- Artifact and checkpoint locations
- Observability configuration
- Compiler target options

Profiles do not redefine pipeline topology or transformation semantics.

## Bindings

Bindings connect logical names to concrete implementations.

```toml
[profiles.production.bindings.customer_source]
plugin = "postgres"
resource = "analytics_database"
table = "raw.customers"

[profiles.production.bindings.customer_sink]
plugin = "postgres"
resource = "analytics_database"
table = "curated.customers"
write_mode = "merge"
```

Pipeline code refers only to the logical name:

```python
customers: Source[RawCustomer] = Source(binding="customer_source")
```

## Plugin Configuration

Plugins own validation of plugin-specific settings.

```toml
[profiles.production.plugin.airflow]
dag_id_prefix = "data_"
default_pool = "etl"

[profiles.production.plugin.polars]
streaming = true
```

Pipelantic preserves the settings as typed plugin configuration; it should
not silently accept unknown fields.

## Resource Providers

Resource providers supply managed runtime dependencies:

```toml
[profiles.production.resources.analytics_database]
provider = "sqlalchemy"
url = "postgresql+psycopg://analytics@warehouse.internal/analytics"
password = { secret = "production-secrets:analytics/warehouse#password" }
pool_size = 10

[profiles.production.resources.alert_client]
provider = "http"
base_url = "https://alerts.example.test"
token = { secret = "production-secrets:alerts/api-token" }

[profiles.production.secrets.production-secrets]
provider = "aws-secrets-manager"
region = "us-east-1"
cache_ttl = "5m"
```

Secrets should be referenced, not stored directly in committed configuration.

Secret references contain provider and identifier metadata, never resolved
values. Planning validates their structure and provider capabilities without
contacting the backing store.

```toml
[profiles.local.secrets.production-secrets]
provider = "keyring"
service = "pipelantic.customer-platform"
```

See [Secrets Management](../06_EXECUTION/SECRETS_MANAGEMENT.md).

## Execution Limits

```toml
[profiles.local.limits]
max_concurrent_nodes = 4
max_worker_threads = 8
max_worker_processes = 2

[profiles.production.limits]
max_concurrent_nodes = 32
```

Backend plugins may impose stricter limits.

## Contract Paths

```toml
[contracts]
data = ["contracts/data"]
transformations = ["contracts/transformations"]
pipelines = ["contracts/pipelines"]
```

Remote registries should be opt-in and explicitly configured.

## Generation

```toml
[generation]
output = "build/generated"
canonical = true
include_docs = true
include_diagrams = true
```

Generated output should be deterministic and suitable for `--check` in CI.

## Validation

```toml
[validation]
strict = true
warnings_as_errors = false
validate_inputs = true
validate_outputs = true
```

Profile configuration may select validation behavior but may not weaken a
mandatory contract guarantee without an explicit, visible policy.

## Logging

```toml
[logging]
level = "INFO"
format = "console"
include_context = true

[logging.redaction]
enabled = true
keys = ["password", "token", "secret", "authorization"]

[profiles.production.logging]
provider = "opentelemetry"
level = "INFO"
json = true
```

Logging configuration may change verbosity, formatting, routing, and redaction.
It must not change pipeline semantics or the canonical plan hash.

Plugin-specific logger configuration should use a namespace:

```toml
[logging.loggers."pipelantic.plugin.airflow"]
level = "DEBUG"
```

## Configuration Provenance

The effective configuration model should retain the origin of every value:

```text
profiles.production.orchestrator
value: airflow
source: pipelantic.toml:24
```

This makes overrides diagnosable.

## Python Configuration

Applications may construct configuration explicitly:

```python
from pipelantic import PipelineRuntime, Profile

runtime = PipelineRuntime(
    profile=Profile(
        name="local",
        orchestrator="local",
        dataframe="polars",
    )
)
```

Explicit Python arguments take precedence over ambient configuration.

## Unknown and Deprecated Keys

Unknown keys should produce diagnostics. Deprecated keys should include:

- The replacement key
- The planned removal version
- A migration example

## Security Rules

- Never print secret values.
- Do not execute Python expressions from configuration.
- Disable remote includes by default.
- Restrict file references to configured project roots.
- Validate plugin configuration before execution.

The complete threat model and mandatory controls are defined in the
[Security Model](../02_FOUNDATIONS/SECURITY.md).

## See Also

- [Profiles](../05_PIPELINES/PROFILES.md)
- [Environment Variables](ENVIRONMENT_VARIABLES.md)
- [CLI](CLI.md)
- [Resource Provider](../07_PLUGIN_SDK/RESOURCE_PROVIDER.md)
- [Logging](../06_EXECUTION/LOGGING.md)
