# Design Decisions

This document records product and API decisions that shape the ETLantic
developer experience. Detailed architectural records belong in
[Architecture Decisions](ARCHITECTURE_DECISIONS.md).

## Decision Status

Each decision should be marked:

- Proposed
- Accepted
- Superseded
- Rejected

## DD-001: Type Annotations Are the Modeling Language

**Status:** Accepted

ETLantic uses Python annotations to declare transformation inputs, outputs,
parameters, sources, and sinks.

```python
class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    result: Output[Customer]
```

This supports editor assistance, validation, documentation, and contract
generation without repeating definitions.

## DD-002: Three Top-Level Contract Types

**Status:** Accepted

The ecosystem recognizes data, transformation, and pipeline contracts:

- ODCS describes data.
- DTCS describes transformations.
- DPCS describes pipelines.

Execution settings, resources, callbacks, artifacts, and profiles are
implementation concepts, not additional top-level contracts.

## DD-003: ContractModel Retains Its Identity

**Status:** Accepted

ContractModel remains focused on operationalizing data contracts. ETLantic
consumes ContractModel-compatible models but does not broaden ContractModel into
a universal contract framework.

## DD-004: Modeling Is Separate from Execution

**Status:** Accepted

Pipeline classes describe semantics and topology. Plugins perform reads,
transformations, writes, scheduling, and resource acquisition.

Importing a pipeline must not execute it.

## DD-005: External Engines Are First-Class

**Status:** Accepted

Pandas, Polars, SQL, PySpark, Airflow, and future systems are selected through
plugins and profiles. ETLantic does not require one runtime.

Polars may serve as the reference dataframe implementation while Pandas remains
fully supported.

## DD-006: Async Internals, Ambidextrous Boundaries

**Status:** Accepted

The runtime is async-first. Users and plugins may supply `def` or `async def`
callables. ETLantic normalizes invocation, concurrency, cancellation, and
cleanup.

Both `run()` and `arun()` are provided, but `run()` must not unsafely nest event
loops.

## DD-007: Transformation Contracts and Implementations Are Separate

**Status:** Accepted

A transformation defines a stable typed interface. It may have Pandas, Polars,
SQL, PySpark, or other implementations.

```python
@NormalizeCustomers.implementation("polars")
def normalize(...):
    ...
```

## DD-008: Callbacks Return Declarative Actions

**Status:** Accepted

Callbacks receive typed context and may return actions such as retry, fail,
skip, quarantine, or continue. The selected backend carries out the action.

## DD-009: DPCS Is the Portable Pipeline Representation

**Status:** Accepted

ETLantic's Python API is the primary code-first authoring experience.
DPCS is the canonical portable pipeline contract. Environment bindings remain
outside portable topology.

## DD-010: Pipeline Plans Are Resolved IR

**Status:** Accepted

Validation and planning produce an immutable `PipelinePlan` consumed by local
execution, compilation, visualization, and external orchestrators.

The plan is not the authoring model and should not contain unresolved names or
secret values.

## DD-010A: The Three Authoring Models Are Data, Transformation, and Pipeline

**Status:** Accepted for 0.3

ETLantic presents one coherent code-first authoring language:

```python
from etlantic import Data, Pipeline, Transformation
```

`Data` is a thin facade over ContractModel, not a new data-contract
implementation. ContractModel retains authority for data-contract semantics,
validation, and ODCS operationalization. Existing ContractModel subclasses
remain valid wherever ETLantic accepts `Data`.

Prefer a direct alias over subclassing unless a concrete integration hook
requires a subclass. Deprecate the ETLantic-facing `DataContractModel` name
before 1.0.

## DD-011: SQL and PySpark Are Backends, Not New Models

**Status:** Accepted

SQL-native and PySpark-native logic are implementations of ordinary
transformations. They do not introduce `SqlTransformation` or
`SparkPipeline` as separate top-level user models.

## DD-012: Prefer Explicit Wiring

**Status:** Accepted

The foundational API avoids hidden context-manager state and ambiguous operator
overloading. Named ports and step construction make fan-in, fan-out, and
multiple outputs explicit.

## DD-013: Generate Derived Artifacts

**Status:** Accepted

Contracts, diagrams, documentation, and backend artifacts are generated from
validated models or plans. Users should not maintain duplicate representations
by hand.

## DD-014: Configuration Does Not Change Meaning

**Status:** Accepted

Profiles bind a portable pipeline to implementations and environments. They may
not silently rewrite contract semantics or pipeline topology.

## DD-015: Logical and Physical Graphs Are Different Models

**Status:** Accepted

The logical graph preserves the user's sources, steps, sinks, ports, and
contracts. The physical graph contains backend tasks, statements, stages, and
materialization boundaries.

Backends may optimize the physical graph only when mappings to logical
identities remain available.

## DD-016: PipelinePlan Is Resolved and Secret-Free

**Status:** Accepted

`PipelinePlan` is immutable after construction and records implementation,
binding, capability, resource-reference, and execution-region decisions.

Credentials and live runtime objects are resolved only during execution.

## DD-017: Execution Regions Are a Planner Concern

**Status:** Accepted

SQL fusion, Polars lazy regions, Spark logical plans, and similar grouping are
formed by planning and backend compilation. Transformation and pipeline classes
remain backend-neutral.

## DD-018: Resource Provider Is the Preferred Term

**Status:** Accepted

Components that acquire, scope, inject, and clean up runtime dependencies are
called resource providers. They participate in the Plugin SDK but are not
described as another execution plugin category in user-facing APIs.

## DD-019: Documentation Distinguishes Design from Implementation

**Status:** Accepted

Until implementation catches up, examples define intended UX, reference
chapters define proposed 1.0 surfaces, and DTCS/DPCS specifications define
normative semantics. Chapter detail alone does not imply implementation status.

## DD-020: Lifecycle Extension Mechanisms Remain Distinct

**Status:** Accepted

ETLantic provides separate runtime lifespan, execution middleware,
resource injection, lifecycle callbacks, and outbound event declarations.

- Lifespan owns paired setup and cleanup.
- Middleware wraps matching run or step invocations.
- Resource injection resolves typed callable requirements.
- Callbacks respond to specific lifecycle outcomes.
- Outbound events describe external notifications.

ETLantic adopts this separation from FastAPI's architecture without
adopting HTTP request semantics.

## DD-021: Resource Injection Is Not Pipeline Dependency Wiring

**Status:** Accepted

The resource resolver builds a hierarchical provider graph that is independent
from the data-flow graph. The public term is resource injection, not dependency
injection, to avoid confusing services with upstream pipeline steps.

Yield-based providers and async context managers provide deterministic cleanup.

## DD-022: Middleware Cannot Change Portable Meaning

**Status:** Accepted

Middleware may observe, time, trace, log, enforce policy, and normalize
failures. It may not mutate contracts, topology, port compatibility, or a
resolved plan after planning.

Semantic replacement requires an explicit planned extension point.

## DD-023: Outbound Events Are Interface Metadata

**Status:** Accepted

Typed outbound events document notifications a pipeline may emit. Providers
handle HTTP webhooks, Kafka, queues, or other transports.

Outbound events remain pipeline metadata and runtime behavior; they are not a
fourth top-level contract family.

## DD-024: Planning Is an Unprivileged Analysis Boundary

**Status:** Accepted

Loading, validation, inspection, documentation, and planning must not execute
user code, resolve secrets, acquire resources, or materialize data. Static
discovery is preferred over importing user modules.

## DD-025: Executable Serialization Is Prohibited

**Status:** Accepted

Untrusted `pickle`, `dill`, `cloudpickle`, marshal data, arbitrary YAML object
constructors, and similar executable formats are prohibited for contracts,
plans, reports, caches, and plugin interchange.

## DD-026: Plugin Discovery Is a Trust Decision

**Status:** Accepted

Python plugins execute with host-process privileges. Production configuration
must support allowlists, pinned versions, provenance recording, and refusal of
silent fallback to unapproved plugins.

## DD-027: Security Boundaries Constrain Optimization

**Status:** Accepted

SQL fusion, Spark regions, caching, artifact reuse, and other optimizations may
not cross authorization, tenant, residency, masking, or security-domain
boundaries.

## DD-028: Portable Transformations Use a Closed Relational Language

**Status:** Accepted for 0.11+

Portable transformation authoring uses a PySpark-inspired DataFrame and Column
surface. The versioned `etlantic.transform/1` authoring profile normalizes to
the published DTCS 3.0 `dtcs.transform-plan/2` (v1 readable); it is not a
competing semantic IR. ETLantic does not trace arbitrary Python or adopt a
backend's expression objects as its semantic model.

Plugins compile only the operations they advertise and must preserve normative
semantics or fail during planning. Native transformation implementations remain
explicit escape hatches. See
[ADR-013](adr/ADR-013-PORTABLE-TRANSFORMATION-IR.md).

## Adding a Decision

New decisions should include:

1. Context
2. Decision
3. User impact
4. Alternatives considered
5. Compatibility implications
6. Status and date
