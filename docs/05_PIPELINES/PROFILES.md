# Profiles

A **Profile** defines how a validated Pipeline Plan is bound to a specific
execution environment.

Profiles supply environment-specific configuration without changing the logical
meaning of a pipeline. They bridge the gap between portable pipeline contracts
and concrete runtime infrastructure.

ETLantic separates **what a pipeline does** from **how and where it
executes**.

## Goals

Profiles should:

- Keep pipelines environment-independent.
- Bind logical resources to physical resources.
- Select execution implementations.
- Configure runtime behavior.
- Support multiple deployment environments.
- Preserve pipeline semantics.

## Philosophy

A pipeline should execute in different environments without modification.

```text
CustomerPipeline
        │
        ├── Development Profile
        ├── Testing Profile
        ├── Staging Profile
        └── Production Profile
```

Each profile produces a different `PipelinePlan` while preserving identical
logical behavior.

## What a Profile Defines

A profile may define:

- Execution engine
- Orchestrator
- Dataframe backend
- Resource bindings
- Source bindings
- Sink bindings
- Secret providers
- Validation mode
- Logging configuration
- Retry policies
- Concurrency limits
- Timeouts
- Deployment metadata
- SQL dialect or Spark provider
- Artifact and checkpoint locations
- Plugin-specific compiler options

Profiles never redefine pipeline contracts.

Profiles also must not:

- Add or remove logical nodes
- Change contract identities
- Change transformation semantics
- Resolve secret values during planning

## Example

```python
from etlantic import Profile

production = Profile(
    name="production",
    dataframe_engine="polars",
)

sql_prod = Profile(
    name="sql-prod",
    sql_engine="sql",
)
```

Use `dataframe_engine` for Polars/Pandas/local implementations. Use
`sql_engine="sql"` when SQL implementations and bindings should run through a
SQL plugin (`etlantic-sql`). Do not set `dataframe_engine` to `"sql"`.

Planning uses the selected profile when generating a Pipeline Plan.

## Resource Bindings

Profiles resolve logical bindings into physical resources.

Pipeline:

```python
customers = Source[Customer](
    binding="customers",
)
```

Development profile:

```text
customers -> ./data/customers.csv
```

Production profile:

```text
customers -> warehouse.customer_table
```

The pipeline definition remains unchanged.

## Implementation Selection

Profiles choose execution implementations.

```text
NormalizeCustomers
        │
        ▼
polars implementation
```

or, with `Profile(sql_engine="sql")`:

```text
NormalizeCustomers
        │
        ▼
sql implementation (RelationRef / SqlQuery)
```

A different profile might instead select:

- pandas
- sql
- spark / pyspark
- remote service

The transformation contract does not change.

## Orchestrator Selection

Profiles determine where Pipeline Plans execute.

Examples include:

- Local Python
- Airflow (`etlantic-airflow`)
- Future orchestrators (Dagster, Prefect)

Planning verifies that the selected orchestrator satisfies all mandatory
pipeline capabilities.

## Validation Configuration

Profiles may configure validation behavior.

Examples:

- Strict validation
- Warning thresholds
- Contract registry resolution
- Compatibility enforcement

These settings influence planning but never alter pipeline semantics.

## Secrets

Profiles reference external secret providers.

Examples:

- Environment variables
- Cloud secret managers
- Vault systems
- Organization-specific providers

Secrets should never be embedded in pipeline contracts or generated DPCS
artifacts.

## Environment Overrides

Profiles may override operational values such as:

- Batch size
- Parallelism
- Retry counts
- Timeouts
- Logging destinations

Overrides should affect runtime behavior only.

## Relationship to Planning

Planning combines:

- Pipeline
- Contracts
- Profile
- Plugin registry

to generate a Pipeline Plan.

Changing profiles should change the `PipelinePlan`—not the pipeline itself.

More precisely, changing profiles produces a different `PipelinePlan` and
possibly a different physical graph while preserving the same logical graph.

## Resolution Precedence

Recommended precedence is:

```text
Explicit Python or CLI override
        ↓
Selected profile
        ↓
Inherited profile
        ↓
Project defaults
        ↓
Plugin defaults
```

The effective plan should retain configuration provenance so users can explain
why a binding or implementation was selected.

## Plan Safety

A profile may reference a secret provider or environment variable name, but the
resolved value must not be serialized into a `PipelinePlan`.

Profile validation should occur before resource acquisition.

## Relationship to DPCS

Profiles are not part of the portable pipeline contract.

DPCS records execution requirements.

Profiles provide environment-specific bindings that satisfy those requirements.

## Best Practices

- Keep profiles small and focused.
- Store secrets externally.
- Use stable logical bindings.
- Maintain separate profiles for development and production.
- Validate profiles before planning.

## Anti-Patterns

Avoid:

- Embedding credentials in profiles.
- Encoding business logic in profiles.
- Modifying pipeline contracts through profile configuration.
- Creating orchestrator-specific pipeline definitions.

## Key Principle

> A Profile describes **where and how** a pipeline executes. A Pipeline
describes **what** the workflow means. Profiles bind pipelines to environments
without changing their semantics.

## Next Step

Continue with [Contract Generation](CONTRACT_GENERATION.md) to learn how
ETLantic generates portable ODCS, DTCS, and DPCS artifacts.
