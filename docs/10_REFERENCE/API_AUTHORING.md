# API — Authoring

> Generated from package source. Hub: [Python API Reference](API_REFERENCE.md).

## Authoring

!!! note "Portable authoring and compilers"
    `etlantic.transform`, `@Transformation.portable`, symbolic DataFrame and
    Column objects, and `functions as F` normalize to published DTCS 3.0
    `dtcs.transform-plan/2` models. Official compilers ship in optional
    packages. See
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
not Polars/Pandas/Spark objects. Polars and PySpark relational compilation
shipped in 0.13; eager Pandas relational compilation shipped in 0.14.

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

