# ETLantic Manifesto

> **Status: Available in ETLantic 0.36.0.**


## Data Engineering Deserves a Typed Interface

Modern data systems are assembled from capable tools, yet their meaning is
often scattered across dataframe code, SQL, scheduler configuration, schema
files, runtime settings, and hand-maintained documentation.

ETLantic exists to give that system one portable, typed model without
replacing the tools that perform the work.

> ETLantic models the promises, transformations, and topology of a data
> pipeline. External engines execute the resulting plan.

## Types Should Carry Meaning

Python type annotations should do more than assist an editor.

They should declare:

- The data a transformation accepts
- The data it produces
- The parameters that control it
- The ports a pipeline can connect
- The contracts a boundary must preserve

From those declarations, ETLantic should derive validation,
documentation, contracts, lineage, and planning metadata.

Information should be stated once and reused everywhere.

## Three Contracts Are Enough

ETLantic recognizes three top-level contract families:

```text
Data Contract
What valid data means

Transformation Contract
How data is expected to change

Pipeline Contract
How data and transformations are composed
```

[ODCS](03_DATA_CONTRACTS/ODCS.md), [DTCS](04_TRANSFORMATIONS/DTCS.md), and [DPCS](05_PIPELINES/DPCS.md) own those meanings.

Profiles, plugins, resources, callbacks, artifacts, deployment settings, and
execution plans are important, but they are not new public contract standards.
They are implementations and runtime configuration built beneath the three
contract authorities.

## Model First, Execute Second

Pipeline code should answer:

- What are the inputs and outputs?
- Which contracts govern them?
- Which transformations connect them?
- What dependencies and guarantees exist?

It should not need to answer:

- Which thread pool runs a function?
- Which scheduler owns a retry?
- Which dataframe engine stores an intermediate value?
- Which cloud SDK creates a client?

Those choices belong to profiles, plugins, and external runtimes.

## One Transformation, Many Implementations

A transformation is a stable, typed interface.

Its implementation may use:

- Polars
- Pandas
- SQL
- PySpark
- A remote service
- A future engine

Changing the implementation must not change the transformation's declared
meaning.

## One Pipeline, Many Runtimes

A pipeline should run locally, compile to Airflow, execute SQL in a database,
or submit work to Spark by changing bindings and capabilities—not by rewriting
its logical graph.

Portability does not mean pretending every runtime is identical. ETLantic
must detect when a backend cannot preserve requested semantics and fail during
planning with an actionable diagnostic.

## Validation Should Precede Cost

ETLantic should reject invalid models before expensive work begins.

Validation includes:

- Contract compatibility
- Typed port wiring
- Parameter correctness
- Graph topology
- Implementation signatures
- Plugin capabilities
- Backend semantic support

Runtime validation still matters for actual data, but structural mistakes
should not survive into execution.

## Async Should Be an Implementation Detail

Users may write `def` or `async def`.

ETLantic should normalize invocation, concurrency, cancellation, timeouts,
and cleanup through one async-first internal model. Users should not need to
wire event loops or worker pools to participate safely.

## Plans Should Be Inspectable

Planning should produce an immutable, deterministic `PipelinePlan`.

The plan is the resolved intermediate representation between modeling and
execution. It should be usable for:

- Execution
- Compilation
- Visualization
- Documentation
- Static analysis
- Lineage
- Reproducibility

It must contain resolved references and capabilities, but never resolved
secrets.

## Generated Artifacts Should Not Drift

ODCS, DTCS, DPCS, diagrams, documentation, and backend artifacts should be
generated from validated models or plans.

Generated output should be deterministic, reviewable, and verifiable in CI.

## The Core Should Stay Small

ETLantic owns:

- Typed authoring
- Introspection
- Validation
- Logical graph construction
- Planning
- Contract coordination
- Diagnostics
- Generation

Plugins own:

- Dataframe execution
- SQL and Spark execution
- Reading and writing
- Orchestration
- Runtime resources
- Backend compilation

ContractModel owns operational data-contract behavior.

ODCS, DTCS, and DPCS own contract semantics.

## The Project Constitution

A feature belongs in ETLantic when it strengthens portable modeling,
validation, planning, diagnostics, or plugin coordination.

A feature belongs in a plugin when it concerns how a particular technology
executes, stores, schedules, or provisions work.

A feature belongs in ContractModel when it operationalizes data contracts.

A feature belongs in ODCS, DTCS, or DPCS when it changes the meaning of a
contract standard.

## Success

ETLantic succeeds when a developer can understand a pipeline by reading
its types, validate it before execution, generate portable contracts and
documentation from it, and run it through an appropriate backend without
allowing that backend to become the source of truth.
