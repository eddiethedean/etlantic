# Storage Plugin

A **Storage Plugin** implements the ETLantic Storage Plugin API for a
persistent storage technology.

Storage plugins translate the logical `Source` and `Sink` bindings contained in
a validated **Pipeline Plan** into concrete read and write operations for a
specific storage backend. They preserve the semantics defined by ODCS, DTCS,
and DPCS while hiding storage-specific implementation details from pipeline
authors.

## Purpose

A storage plugin is responsible for:

- Reading datasets from persistent storage
- Writing datasets to persistent storage
- Resolving logical bindings
- Managing storage connections
- Preserving data contract semantics
- Reporting structured storage diagnostics

It is **not** responsible for:

- Pipeline planning
- Graph execution
- Transformation execution
- Orchestration
- Contract generation

## Architecture

```text
Pipeline Plan
      │
      ▼
Storage Plugin API
      │
 ┌────┼────────────────────────────┐
 ▼    ▼            ▼              ▼
CSV PostgreSQL   Parquet      Object Storage
```

Execution plugins coordinate the pipeline. Storage plugins provide persistence.

## Responsibilities

Every storage plugin should:

- Resolve source and sink bindings
- Read typed datasets
- Write validated datasets
- Preserve metadata where supported
- Emit structured diagnostics
- Clean up resources

## Plugin Interface

Conceptually:

```python
class StoragePlugin:
    name: str
    version: str

    def read(self, binding, contract, context):
        ...

    def write(self, binding, contract, dataset, context):
        ...
```

The SDK API may evolve, but every storage plugin should expose equivalent read
and write behavior.

## Logical Bindings

Pipelines reference logical bindings rather than physical locations.

```python
customers = Extract[Customer](
    binding="customers",
)
```

A profile resolves that binding.

Development:

```text
customers -> ./data/customers.parquet
```

Production:

```text
customers -> s3://company/raw/customers/
```

The pipeline remains unchanged.

## Data Contracts

Every dataset read or written is governed by a `DataContractModel`.

Storage plugins should cooperate with validation to ensure persisted data
matches its declared contract.

## Capabilities

Plugins should advertise capabilities such as:

- Read support
- Write support
- Transactions
- Streaming
- Partitioning
- Versioning
- Compression
- Schema evolution

Planning verifies required capabilities before execution.

## Error Handling

Storage-specific exceptions should be translated into structured
ETLantic diagnostics.

Diagnostics should preserve:

- Pipeline identity
- Step identity
- Binding
- Backend details
- Original exception

## Best Practices

- Keep bindings logical.
- Preserve contract semantics.
- Validate data before publication.
- Keep credentials outside pipeline definitions.
- Declare capabilities explicitly.

## Anti-Patterns

Avoid:

- Hard-coding filesystem paths into pipeline models.
- Exposing backend SDK objects through public APIs.
- Bypassing contract validation.
- Embedding orchestration logic inside storage plugins.

## Key Principle

> A storage plugin provides persistence for ETLantic by translating logical
> source and sink bindings into backend-specific operations while preserving the
> portable semantics of pipeline contracts.

## Next Step

Continue with [Resource Provider](RESOURCE_PROVIDER.md) to learn how
infrastructure services are provided through the Plugin SDK.
