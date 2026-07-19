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
- Resource / logical asset maps (`assets`, preferred over legacy `bindings`)
- Extract asset resolution
- Load asset resolution
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
- Portable transformation policy (`require`, `prefer`, or `native`)

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
    security_domain="production",
    dataframe_engine="polars",
    plugin_allowlist={
        "etlantic-polars": ">=0.10.0,<1.0",
    },
)

sql_prod = Profile(
    name="sql-prod",
    sql_engine="sql",
    plugin_allowlist={
        "etlantic-sql": ">=0.10.0,<1.0",
    },
)
```

Production and staging profiles fail closed when `plugin_allowlist` is empty.
Development profiles may omit the allowlist. See
[Runtime configuration](../10_REFERENCE/RUNTIME_CONFIGURATION.md).

Use `dataframe_engine` for Polars/Pandas/local implementations. Use
`sql_engine="sql"` when SQL implementations and bindings should run through a
SQL plugin (`etlantic-sql`). Do not set `dataframe_engine` to `"sql"`.

Planning uses the selected profile when generating a Pipeline Plan.

## Logical assets

Profiles resolve logical asset names into physical resources. Prefer
`Profile(assets=...)` in 0.15; `bindings=` remains a warned alias until 0.16.
Public profile JSON may emit both `assets` and mirrored `bindings`; plan
`profile_snapshot` keeps the fingerprint-stable bindings-only shape.

Pipeline:

```python
from etlantic import Extract

customers = Extract[Customer](
    asset="customers",
)
```

Development profile:

```python
Profile(name="development", assets={"customers": "./data/customers.csv"})
```

Production profile:

```python
Profile(name="production", assets={"customers": "warehouse.customer_table"})
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

Beginning with the 0.11 portable authoring surface (compiler selection in
0.12+), profiles also decide whether an eligible step is compiled from its
portable definition or executed through a native implementation. Default
policy in 0.12 is `prefer`:

```python
Profile(
    name="portable-polars",
    dataframe_engine="polars",
    portable_transform_policy="prefer",  # or "require" / "native"
)
```

`require` forbids native fallback, `prefer` permits an explicit diagnosed
native fallback, and `native` prefers a registered backend implementation.
The choice must be retained in `plan explain` and run reports. Prefer never
silently emulates portable semantics (including under SQL: no implicit Polars
or other engine switch). Polars and PySpark shipped **kernel** +
**relational `/1`** claims in 0.13; eager Pandas shipped the same claims in
0.14. Safe SQL lowering for that claim set is the **0.15** exit gate. Richer
profiles such as windows and reshape still need native implementations until
they graduate under the 0.15 continuation backlog.

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

Profiles reference external secret providers. Secrets must never be embedded in
pipeline contracts, plans, or generated DPCS artifacts.

**Shipped in 0.10:**

- Environment variables (`EnvSecretProvider`)
- Mounted files (`MountedFileSecretProvider`)
- Optional OS keyring via `etlantic-keyring`

!!! warning "Future design—not shipped"
    Cloud secret managers (AWS Secrets Manager, HashiCorp Vault, and peers)
    are **not** available in 0.10. Do not configure them yet. See
    [Secrets Management](../06_EXECUTION/SECRETS_MANAGEMENT.md).

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

Profiles provide environment-specific assets that satisfy those requirements.

## Best Practices

- Keep profiles small and focused.
- Store secrets externally.
- Use stable logical asset names.
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
