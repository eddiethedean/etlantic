# Python API Reference

> **Status: Available in Pipelantic 0.6.0.** Signatures and docstrings below
> are generated from the package source.

The package root is the supported convenience import surface for common
authoring, planning, runtime, storage, report, secret, and interchange types:

```python
from pipelantic import (
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

### Data contracts

::: pipelantic.contracts
    options:
      show_root_heading: true
      members_order: source

### Transformations

::: pipelantic.transformation
    options:
      show_root_heading: true
      members_order: source

### Pipelines

::: pipelantic.pipeline
    options:
      show_root_heading: true
      members_order: source

### Ports and references

::: pipelantic.ports
    options:
      show_root_heading: true
      members_order: source

## Validation and diagnostics

::: pipelantic.diagnostics
    options:
      show_root_heading: true
      members_order: source

::: pipelantic.validation
    options:
      show_root_heading: true
      members_order: source

## Profiles, planning, and registries

::: pipelantic.profile
    options:
      show_root_heading: true
      members_order: source

::: pipelantic.plan
    options:
      show_root_heading: true
      members_order: source

::: pipelantic.registry
    options:
      show_root_heading: true
      members_order: source

## Local runtime and reports

::: pipelantic.runtime
    options:
      show_root_heading: true
      members_order: source

::: pipelantic.lifecycle
    options:
      show_root_heading: true
      members_order: source

::: pipelantic.reports
    options:
      show_root_heading: true
      members_order: source

## Storage and secrets

::: pipelantic.storage
    options:
      show_root_heading: true
      members_order: source

::: pipelantic.secrets
    options:
      show_root_heading: true
      members_order: source

## Contract interchange

::: pipelantic.interchange
    options:
      show_root_heading: true
      members_order: source

## Dataframe protocol

::: pipelantic.dataframe
    options:
      show_root_heading: true
      members_order: source

## Capabilities

::: pipelantic.capabilities
    options:
      show_root_heading: true
      members_order: source

## Reliability and schema drift

::: pipelantic.reliability
    options:
      show_root_heading: true
      members_order: source

::: pipelantic.schema_drift
    options:
      show_root_heading: true
      members_order: source

::: pipelantic.schema_policy
    options:
      show_root_heading: true
      members_order: source

## Testing helpers

::: pipelantic.testing
    options:
      show_root_heading: true
      members_order: source

## Exceptions

::: pipelantic.exceptions
    options:
      show_root_heading: true
      members_order: source

## Stability

Pipelantic is alpha. A root export is public in the current release, but 0.x
releases may change APIs. Review the changelog and
[compatibility matrix](COMPATIBILITY.md) before upgrading.
