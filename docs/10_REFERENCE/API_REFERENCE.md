# API Reference

This chapter describes Pipelantic's public Python API. Surfaces marked
**shipped** are available in the current release. Other entries remain design
references for later milestones.

## Stable Import Surface

Common authoring and interchange APIs are available from the package root:

```python
from pipelantic import (
    Pipeline,
    Transformation,
    Input,
    Output,
    Parameter,
    Source,
    Step,
    Sink,
    DataContractModel,
    ContractBundle,
    load_data_contract,
    write_odcs,
    write_contracts,
    load_bundle,
    diff_data_contracts,
)
```

Data-contract authoring remains owned by ContractModel:

```python
from contractmodel import ContractModel as DataContractModel
# or
from pipelantic import DataContractModel
```

Plugin-author interfaces should live under `pipelantic.sdk`, not the root.

## `Transformation`

Base class for a typed transformation contract.

```python
class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    minimum_age: Parameter[int] = 18
    result: Output[Customer]
```

Proposed class methods:

```python
NormalizeCustomers.inputs()
NormalizeCustomers.outputs()
NormalizeCustomers.parameters()
NormalizeCustomers.implementations()
NormalizeCustomers.validate_definition()
NormalizeCustomers.to_dtcs()          # shipped in 0.2
NormalizeCustomers.from_dtcs(...)     # shipped in 0.2
NormalizeCustomers.step(...)
```

### `implementation`

Register an execution implementation:

```python
@NormalizeCustomers.implementation("polars")
def normalize(customers, minimum_age):
    ...
```

Registration should record implementation identity, callable signature,
capabilities, and optional execution hints.

## Port Annotations

### `Input[T]`

Declares data consumed under contract `T`.

### `Output[T]`

Declares data produced under contract `T`.

### `Parameter[T]`

Declares typed configuration that influences a transformation without becoming
a graph edge.

Metadata may be added through `typing.Annotated`.

## `Pipeline`

Base class for a declarative pipeline graph.

```python
class CustomerPipeline(Pipeline):
    raw: Source[RawCustomer] = Source(binding="customer_source")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Sink[Customer] = Sink(
        input=normalized.result,
        binding="customer_sink",
    )
```

Proposed class methods:

```python
CustomerPipeline.inspect()
CustomerPipeline.validate()
CustomerPipeline.plan(profile="local")       # 0.3+
CustomerPipeline.run(profile="local")        # 0.4+
await CustomerPipeline.arun(profile="local") # 0.4+
CustomerPipeline.compile(target="airflow", profile="production")  # later
CustomerPipeline.to_dpcs()                   # shipped in 0.2
CustomerPipeline.from_dpcs(...)              # shipped in 0.2
CustomerPipeline.generate_contracts(...)     # shipped in 0.2
CustomerPipeline.write_contracts("contracts/")  # shipped in 0.2
CustomerPipeline.to_mermaid()
CustomerPipeline.to_graphviz()               # later
```

## Nodes

### `Source[T]`

Declares a logical data origin.

```python
source: Source[Customer] = Source(binding="customers")
```

### `Step[TTransformation]`

A concrete use of a transformation in a pipeline. Users usually create steps
through `Transformation.step(...)`.

### `Sink[T]`

Declares a logical data destination:

```python
sink: Sink[Customer] = Sink(input=step.result, binding="warehouse")
```

## Results and Reports

Public operations should return structured values:

```python
ValidationReport
PlanningReport
PipelinePlan
CompilationResult
PipelineRunReport
StepRunReport
ArtifactResult
ValidationResult
StateTransitionResult
ContractBundle
```

Convenience methods may raise exceptions, but the underlying structured report
must remain accessible.

`Pipeline.run()` and `Pipeline.arun()` return `PipelineRunReport`. Backend
plugins may use narrower internal result objects, but those are normalized
before reaching public application code.

## `Profile`

Represents environment-specific bindings and backend choices:

```python
profile = Profile(
    name="local",
    orchestrator="local",
    dataframe="polars",
)
```

Profiles may also be loaded from project configuration.

## Hooks

Hook decorators register typed lifecycle callbacks:

```python
@on_invalid_data(stage="input_validation")
def handle_invalid(context: InvalidDataContext) -> InvalidDataAction:
    ...

@on_failure(stage="transform")
async def handle_failure(context: ExecutionFailureContext) -> FailureAction:
    ...
```

Sync and async callables share the same lifecycle model.

## Runtime Entry Points

```python
result = CustomerPipeline.run(profile="local")
result = await CustomerPipeline.arun(profile="local")
```

The internal engine is async-first. `run()` is a synchronous boundary for code
that does not already have an active event loop.

## Loading

Proposed high-level loading APIs:

```python
Pipeline.from_contract("customer.dpcs.yaml")
Transformation.from_contract("normalize.dtcs.yaml")
load_pipeline("package.module:CustomerPipeline")
```

ContractModel remains responsible for ODCS data-contract loading.

## Plugin SDK

Advanced interfaces should live under explicit modules:

```python
from pipelantic.sdk import (
    DataframePlugin,
    OrchestratorPlugin,
    StoragePlugin,
    ResourceProvider,
    PluginCapabilities,
)
```

SDK protocols should be async at the orchestration boundary even when the
underlying library is synchronous.

## Internal APIs

Modules or names beginning with an underscore are not public. The planner's
mutable working state, metaclass internals, compiler passes, and plugin loader
implementation should not be imported by applications.

## Typing

Pipelantic should ship type information and prioritize:

- Generic port types
- Typed step outputs
- IDE completion
- Static plugin protocols
- Minimal reliance on untyped dictionaries

A mypy or pyright plugin may be considered only if standard Python typing
cannot express essential authoring behavior.

## See Also

- [Type Annotations](../04_TRANSFORMATIONS/TYPE_ANNOTATIONS.md)
- [Pipeline](../05_PIPELINES/PIPELINE.md)
- [Plugin SDK Overview](../07_PLUGIN_SDK/OVERVIEW.md)
- [Exceptions](EXCEPTIONS.md)
