# Python API Reference

> **Status: Available in ETLantic 0.10.0.** Signatures and docstrings below
> are generated from the package source.

The package root is the supported convenience import surface for common
authoring, planning, runtime, storage, report, secret, and interchange types:

```python
from etlantic import (
    Data,
    Input,
    Output,
    Parameter,
    Pipeline,
    PipelineRuntime,
    Sink,
    Source,
    Transformation,
)
```

`DataContractModel` is a deprecated alias for `Data`.

## Authoring

!!! note "Proposed 0.11+ portable authoring API"
    `etlantic.transform`, `@Transformation.portable`, symbolic DataFrame and
    Column objects, and `functions as F` are accepted future design and are not
    importable in ETLantic 0.10. See
    [Portable Transformations](../04_TRANSFORMATIONS/PORTABLE_TRANSFORMATIONS.md).

### Data contracts

::: etlantic.contracts
    options:
      show_root_heading: true
      members_order: source

### Transformations

::: etlantic.transformation
    options:
      show_root_heading: true
      members_order: source

### Pipelines

::: etlantic.pipeline
    options:
      show_root_heading: true
      members_order: source

### Ports and references

::: etlantic.ports
    options:
      show_root_heading: true
      members_order: source

## Validation and diagnostics

::: etlantic.diagnostics
    options:
      show_root_heading: true
      members_order: source

::: etlantic.validation
    options:
      show_root_heading: true
      members_order: source

## Profiles, planning, and registries

::: etlantic.profile
    options:
      show_root_heading: true
      members_order: source

::: etlantic.plan
    options:
      show_root_heading: true
      members_order: source

::: etlantic.registry
    options:
      show_root_heading: true
      members_order: source

## Local runtime and reports

::: etlantic.runtime
    options:
      show_root_heading: true
      members_order: source

::: etlantic.lifecycle
    options:
      show_root_heading: true
      members_order: source

::: etlantic.reports
    options:
      show_root_heading: true
      members_order: source

## Storage and secrets

::: etlantic.storage
    options:
      show_root_heading: true
      members_order: source

::: etlantic.secrets
    options:
      show_root_heading: true
      members_order: source

## Contract interchange

::: etlantic.interchange
    options:
      show_root_heading: true
      members_order: source

## Dataframe protocol

::: etlantic.dataframe
    options:
      show_root_heading: true
      members_order: source

## SQL protocol

::: etlantic.sql
    options:
      show_root_heading: true
      members_order: source

## Spark protocol

::: etlantic.spark
    options:
      show_root_heading: true
      members_order: source

## Orchestration protocol

::: etlantic.orchestration
    options:
      show_root_heading: true
      members_order: source

## Visualization

::: etlantic.viz
    options:
      show_root_heading: true
      members_order: source

## Agents, IDE, and notebooks

::: etlantic.agents
    options:
      show_root_heading: true
      members_order: source

::: etlantic.ide
    options:
      show_root_heading: true
      members_order: source

::: etlantic.notebook
    options:
      show_root_heading: true
      members_order: source

## Observability

::: etlantic.observability
    options:
      show_root_heading: true
      members_order: source

## Schema history

::: etlantic.schema_history
    options:
      show_root_heading: true
      members_order: source

## Capabilities

::: etlantic.capabilities
    options:
      show_root_heading: true
      members_order: source

## Reliability and schema drift

::: etlantic.reliability
    options:
      show_root_heading: true
      members_order: source

::: etlantic.schema_drift
    options:
      show_root_heading: true
      members_order: source

::: etlantic.schema_policy
    options:
      show_root_heading: true
      members_order: source

## Testing helpers

::: etlantic.testing
    options:
      show_root_heading: true
      members_order: source

## Exceptions

::: etlantic.exceptions
    options:
      show_root_heading: true
      members_order: source

## Stability

ETLantic is alpha. A root export is public in the current release, but 0.x
releases may change APIs. Review the changelog and
[compatibility matrix](COMPATIBILITY.md) before upgrading.
