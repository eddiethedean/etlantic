# Python API Reference

> **Status: Available in ETLantic 0.14.0.** Signatures and docstrings below
> are generated from the package source.

## Start here by persona

| Persona | Start with | Then |
|---|---|---|
| Pipeline author | Root imports below, [CLI](CLI.md) | `etlantic.pipeline`, `etlantic.plan`, `etlantic.reports` |
| Plugin author | `etlantic.dataframe` / `.sql` / `.spark` / `.orchestration` / `.secrets` | [Testing](#testing-helpers), [Plugin SDK](../07_PLUGIN_SDK/README.md) |
| CI / ops | [CLI](CLI.md), [Runtime configuration](RUNTIME_CONFIGURATION.md) | `etlantic.plugin_trust`, SARIF validate |

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

!!! note "Portable authoring (0.11) and Polars kernel compiler (0.12)"
    `etlantic.transform`, `@Transformation.portable`, symbolic DataFrame and
    Column objects, and `functions as F` normalize to published DTCS 3.0
    `dtcs.transform-plan/2` models. `etlantic.transform.compiler` defines the
    `etlantic.transform-compiler/1` protocol; `etlantic-polars` provides
    `create_transform_compiler()` for kernel execution. See
    [Portable Transformations](../04_TRANSFORMATIONS/PORTABLE_TRANSFORMATIONS.md)
    and [Portable Transform Compiler](../07_PLUGIN_SDK/PORTABLE_TRANSFORM_COMPILER.md).

### Core behavioral contracts

The generated signatures below are supplemented by these current guarantees:

| API | Returns | Important failures / side effects |
|---|---|---|
| `Transformation.step(**bindings)` | A symbolic `Step`; no user code runs | Unknown bindings raise `ModelDefinitionError`; required ports are validated before execution |
| `Transformation.implementation(engine)` | A decorator returning the original callable | Registration replaces the implementation for the same class/engine in the current process |
| `Transformation.portable` | Decorator registering a symbolic definition | Authoring errors raise `ModelDefinitionError` (`PMXFORM*`) at registration; does not execute |
| `Transformation.to_transform_plan()` | Deep-copied `dtcs.transform-plan/2` dict | Raises `ModelDefinitionError` if no portable definition is registered |
| `Transformation.portable_fingerprint()` | Hex fingerprint string | Same failure mode as `to_transform_plan` |
| `Pipeline.validate(...)` | `ValidationReport` | Does not execute transformation implementations; production empty allowlist fails closed (`PMPLUG401`) |
| `Pipeline.plan(...)` | Immutable, secret-free `PipelinePlan` | Missing plugins, bindings, trust, or capabilities produce planning/validation failure |
| `Pipeline.run(...)` | `PipelineRunReport` | Executes in-process; storage and plugin side effects follow the resolved plan |
| `Pipeline.arun(...)` | Awaitable `PipelineRunReport` | Uses the same validation and planning path as `run` |
| `Pipeline.to_mermaid()` | Mermaid flowchart string | Builds the logical graph but does not plan or execute |

Minimal validation pattern:

```python
report = CustomerPipeline.validate(profile="development")
report.raise_for_errors()
plan = CustomerPipeline.plan(profile="development")
```

Minimal execution pattern:

```python
runtime = PipelineRuntime()
runtime.memory.seed("customer_source", records)
run_report = CustomerPipeline.run(
    profile="development",
    runtime=runtime,
)
if run_report.status.value != "succeeded":
    raise RuntimeError(run_report.to_text())
```

`PipelineRuntime` is application-owned. A new Python or CLI process receives a
new process-local memory store and report store unless durable providers are
configured.

### Data contracts

::: etlantic.contracts
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

### Transformations

::: etlantic.transformation
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

### Portable transform authoring (`etlantic.transform`)

::: etlantic.transform
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

Symbolic only: `FrameExpr` / `ColumnExpr` trees lower to DTCS plans. They are
not Polars/Pandas/Spark objects. Polars + PySpark + Pandas relational
compilation ships in 0.13–0.14.

### Portable transform compiler protocol (`etlantic.transform.compiler`)

::: etlantic.transform.compiler
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

Discovery helpers:

::: etlantic.transform.discovery
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

Optional package factories (install `etlantic-polars`):
`etlantic_polars.create_plugin`, `etlantic_polars.create_transform_compiler`,
`etlantic_polars.PolarsTransformCompiler`.

### Pipelines

::: etlantic.pipeline
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

### Ports and references

::: etlantic.ports
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

::: etlantic.refs
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

## Validation and diagnostics

::: etlantic.diagnostics
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

::: etlantic.validation
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

::: etlantic.policy
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

## Profiles, planning, and registries

::: etlantic.profile
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

::: etlantic.plan
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

::: etlantic.registry
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

::: etlantic.plugin_trust
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

::: etlantic.model
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

## Local runtime and reports

::: etlantic.runtime
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

::: etlantic.lifecycle
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

::: etlantic.reports
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

## Storage and secrets

::: etlantic.storage
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

::: etlantic.secrets
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

## Contract interchange

::: etlantic.interchange
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

## Dataframe protocol

::: etlantic.dataframe
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

## SQL protocol

::: etlantic.sql
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

## Spark protocol

::: etlantic.spark
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

## Orchestration protocol

::: etlantic.orchestration
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

## Visualization

::: etlantic.viz
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

::: etlantic.mermaid
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

## Agents, IDE, and notebooks

::: etlantic.agents
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

::: etlantic.ide
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

::: etlantic.notebook
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

## Observability

::: etlantic.observability
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

## Schema history

::: etlantic.schema_history
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

## Capabilities

::: etlantic.capabilities
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

## Reliability and schema drift

::: etlantic.reliability
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

::: etlantic.schema_drift
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

::: etlantic.schema_policy
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

## Testing helpers

::: etlantic.testing
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

## Exceptions

::: etlantic.exceptions
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

## Stability

ETLantic is alpha. A root export is public in the current release, but 0.x
releases may change APIs. Review the changelog and
[compatibility matrix](COMPATIBILITY.md) before upgrading. Narrative CLI docs:
[CLI](CLI.md).
