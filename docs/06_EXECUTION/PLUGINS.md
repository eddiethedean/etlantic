# Plugins

!!! warning "Future design overview—not a 0.10 operator manual"
    This page sketches a broad plugin catalog (including unshipped backends such
    as Dagster/Prefect/Kafka). For shipped protocols, use the Execution and
    Plugin SDK pages for dataframe, SQL, Spark, orchestrator, secrets, and
    testing. See [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md).

Plugins are the extension mechanism that allows ETLantic to execute
portable pipeline plans on different technologies without changing pipeline
definitions.

Beginning with the planned 0.11+ work, engine plugins may also implement a
compiler for the closed, published DTCS 3.0 Transformation Plan. This
additional capability does not permit plugins to redefine portable operation
semantics.

The core ETLantic library is intentionally small. It models, validates,
plans, generates contracts, and loads contracts. Plugins provide concrete
runtime behavior.

## Goals

Plugins should:

- Preserve pipeline semantics.
- Be independently installable.
- Support multiple execution technologies.
- Be discoverable.
- Be strongly typed.
- Remain loosely coupled to the core.

## Philosophy

ETLantic defines **what** a pipeline means.

Plugins define **how** that meaning is realized.

Portable compilers declare exact DTCS profile, Semantic Action, Function,
Operator, type, and semantic-mode versions. A broad claim such as
`portable_transform=True` is insufficient.

```text
ETLantic Core
        │
        ▼
Plugin Interface
        │
        ├── Local Execution
        ├── Polars
        ├── Pandas
        ├── Airflow
        ├── Dagster
        ├── Prefect
        ├── Spark
        └── Future Plugins
```

## Plugin Categories

ETLantic may support several plugin types.

### Execution Plugins

Execute Pipeline Plans.

Examples:

- Local Python
- Airflow
- Dagster
- Prefect

### Dataframe Plugins

Implement DTCS transformations using dataframe engines.

Examples:

- Polars
- Pandas
- DuckDB
- Spark

### Source Plugins

Read data from external systems.

Examples:

- CSV
- Parquet
- PostgreSQL
- S3
- Kafka
- REST APIs

### Sink Plugins

Publish data to external systems.

Examples:

- SQL
- Delta Lake
- Object Storage
- Message Queues
- HTTP Services

### Registry Plugins

Resolve and publish contracts.

Examples:

- Local filesystem
- Git
- Organization registries

## Plugin Discovery

Plugins are discoverable through Python packaging entry points. Use the
domain-specific helpers—there is no global `PluginRegistry`:

```python
from etlantic.dataframe import discover_dataframe_plugins
from etlantic.orchestration import discover_orchestrator_plugins
from etlantic.spark import discover_spark_plugins, discover_spark_providers
from etlantic.sql import discover_sql_plugins

dataframe_plugins = discover_dataframe_plugins()
sql_plugins = discover_sql_plugins()
spark_plugins = discover_spark_plugins()
spark_providers = discover_spark_providers()
orchestrators = discover_orchestrator_plugins()
```

CLI: `etlantic plugin list`. Secret providers are registered on the runtime /
profile rather than discovered through a global registry helper.

## Capabilities

Every plugin should declare its capabilities.

Examples:

- Async support
- Streaming support
- Parallel execution
- Retry support
- Checkpoints
- Transactions
- Batch execution

Planning compares required capabilities against those provided by installed
plugins.

## Selection

Profiles determine which plugins are used.

```python
production = Profile(
    orchestrator="airflow",
    dataframe_engine="polars",
)
```

Changing the profile changes plugin selection—not the pipeline.

## Lifecycle

Typical lifecycle:

```text
Discover
    │
    ▼
Validate
    │
    ▼
Register
    │
    ▼
Capability Evaluation
    │
    ▼
Planning
    │
    ▼
Execution
```

## Versioning

Plugins should publish:

- Plugin name
- Version
- Supported ETLantic version
- Supported ODCS version
- Supported DTCS version
- Supported DPCS version
- Capability metadata

Planning should reject incompatible plugins.

## Best Practices

- Keep plugins focused.
- Preserve pipeline semantics.
- Declare capabilities explicitly.
- Avoid hidden side effects.
- Fail clearly when requirements cannot be met.

## Anti-Patterns

Avoid:

- Embedding plugin logic into ETLantic core.
- Changing pipeline semantics.
- Relying on global mutable state.
- Silently ignoring unsupported capabilities.

## Key Principle

> ETLantic provides the portable modeling framework. Plugins provide the
runtime-specific behavior needed to execute, integrate, and extend that model
without altering its meaning.

## Next Step

Continue with [Resource Providers](RESOURCE_PLUGINS.md) to learn how plugins
acquire and manage runtime resources during execution.
