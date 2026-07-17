# DPCS

## Overview

ETLantic adopts the **Data Pipeline Contract Standard (DPCS)** as the
canonical portable representation of pipeline contracts.

DPCS defines the logical structure of a pipeline, including its public
interface, graph, steps, contract references, execution requirements, quality
gates, failure semantics, lineage, compatibility, and orchestrator bindings.
It remains independent of any workflow engine, runtime, storage system, or
programming language.

This document explains how ETLantic integrates with DPCS. The normative
specification remains in `docs/specifications/DPCS_SPEC.md`.

## Why ETLantic Uses DPCS

A pipeline definition should outlive the orchestrator that happens to execute it.

Without a portable pipeline contract, the logical workflow is often trapped
inside Airflow DAGs, Dagster assets, Prefect flows, custom Python scripts, or
vendor-specific deployment files.

DPCS provides an implementation-independent representation that allows a
pipeline to be:

- Authored in Python
- Validated before execution
- Reviewed independently of runtime code
- Compared across revisions
- Bound to multiple orchestrators
- Documented and visualized
- Exchanged between conforming implementations

ETLantic treats DPCS as the canonical artifact for a complete pipeline.

## Architectural Relationship

```text
Python Pipeline Class
        │
        ▼
ETLantic Introspection
        │
        ▼
Logical Pipeline Graph
        │
        ▼
DPCS Pipeline Contract
        │
        ▼
Validated Pipeline Plan
        │
        ▼
Orchestrator Binding
        │
        ▼
Execution Runtime
```

ETLantic owns the Python authoring experience, graph construction,
validation coordination, planning, and plugin integration.

DPCS owns the portable semantic representation.

## Relationship to ODCS and DTCS

The three standards divide responsibilities cleanly:

```text
ODCS
Defines what data is
        │
        ▼
DTCS
Defines what transformations mean
        │
        ▼
DPCS
Defines how contracts compose into pipelines
```

A DPCS contract references existing ODCS, DTCS, and DPCS contracts rather than
duplicating their semantics.

## Code-First Workflow

ETLantic recommends authoring pipelines with typed Python classes.

```python
from etlantic import Pipeline, Sink, Source


class CustomerPipeline(Pipeline):
    raw: Source[RawCustomer] = Source(
        binding="raw.customers",
    )

    normalized = NormalizeCustomers.step(
        customers=raw,
    )

    curated: Sink[Customer] = Sink(
        input=normalized.result,
        binding="curated.customers",
    )
```

From this definition, ETLantic can derive:

- Pipeline identity
- Public inputs and outputs
- Source, step, and sink nodes
- Dependency relationships
- Data flows
- ODCS references
- DTCS references
- DPCS subpipeline references
- Lineage
- Planning requirements

The Python class remains the preferred authoring surface.

The generated DPCS document is the portable artifact.

## Contract-First Workflow

ETLantic should also load existing DPCS artifacts.

Conceptually:

```python
CustomerPipeline = Pipeline.from_dpcs(
    "contracts/pipelines/customer-pipeline.dpcs.yaml",
)
```

A loaded pipeline should expose the same normalized ETLantic interface as
an authored pipeline, provided all referenced contracts can be resolved.

Contract-first loading should preserve:

- Pipeline identity
- Version
- Metadata
- Interfaces
- Graph topology
- Step identity
- Contract references
- Quality gates
- Failure semantics
- Scheduling intent
- Execution requirements
- Extensions

## Pipeline Identity

Every published pipeline should expose a stable logical identity.

Typical identity metadata includes:

- Identifier
- Name
- Version
- Description
- Owner
- Domain
- Lifecycle status
- Tags

Step identities should also remain stable across parsing, validation, planning,
binding, and execution.

Stable identities enable:

- Deterministic generated artifacts
- Lineage
- Diagnostics
- Compatibility analysis
- Execution tracking
- Registry publication

## Pipeline Interface

DPCS defines a public pipeline boundary.

ETLantic should represent that boundary through typed pipeline inputs and
outputs.

Conceptually:

```python
class CustomerCurationPipeline(Pipeline):
    raw_customers: PipelineInput[RawCustomer]
    curated_customers: PipelineOutput[Customer]
```

The public interface should describe the complete externally visible contract
of the pipeline.

Internal steps should not automatically become public API.

## Sources and Sinks

ETLantic sources and sinks map naturally to pipeline boundaries.

```python
raw: Source[RawCustomer] = Source(
    binding="raw.customers",
)
```

```python
curated: Sink[Customer] = Sink(
    input=normalized.result,
    binding="curated.customers",
)
```

Sources introduce data into the graph.

Sinks publish observable pipeline results.

Their physical systems remain binding and plugin concerns rather than DPCS
semantics.

## Pipeline Steps

Each ETLantic step becomes a DPCS Pipeline Step.

A step may represent:

- A DTCS transformation
- A nested DPCS pipeline
- Data ingress
- Data egress
- An approved extension operation

Example:

```python
normalized = NormalizeCustomers.step(
    customers=raw,
    minimum_age=18,
)
```

The generated DPCS step should contain or reference:

- Stable step identity
- Step type
- DTCS contract reference
- Input bindings
- Output bindings
- Parameter values
- Dependencies
- Relevant metadata

The DTCS transformation contract remains independently versioned and reusable.

## Pipeline Graph

ETLantic derives a directed graph from typed connections.

```text
Source[RawCustomer]
        │
        ▼
NormalizeCustomers
        │
        ▼
Sink[Customer]
```

DPCS records logical dependencies, not a particular scheduling algorithm.

ETLantic should validate:

- Unique node identities
- Valid edges
- Required input satisfaction
- Duplicate edges
- Unreachable steps
- Prohibited cycles
- Public entry and exit points

Independent branches may execute concurrently, but concurrency strategy belongs
to the orchestrator or local execution plugin.

## Data Flow

DPCS distinguishes logical data movement from physical transport.

ETLantic should represent every data flow with:

- Source endpoint
- Destination endpoint
- Dataset identity
- Contract reference
- Optional flow metadata

Whether intermediate data is held in memory, written to disk, transmitted over
a network, or materialized in a table is an execution decision unless the
pipeline contract explicitly requires materialization.

## Control Flow

Where supported by DPCS, ETLantic may model control-flow semantics such
as:

- Conditional branches
- Quality-gate decisions
- Approval steps
- Failure branches
- Compensation paths
- Event-driven triggers

Control flow must remain explicit and portable.

It should not be inferred from arbitrary Python branching that cannot be
represented faithfully in DPCS.

## Contract References

DPCS composes contracts through references.

A generated pipeline contract may reference:

- ODCS data contracts
- DTCS transformation contracts
- DPCS subpipeline contracts
- Extension-defined contract types

References should include:

- Contract type
- Stable identifier
- Version requirements
- Resolution information
- Compatibility requirements

ETLantic should resolve required references before constructing a final
Pipeline Plan.

## Subpipelines

A ETLantic subpipeline maps to a Pipeline Step that references another DPCS
contract.

```python
customers = CustomerCurationPipeline.subpipeline(
    raw_customers=source,
)
```

The child pipeline retains its own:

- Identity
- Version
- Public interface
- Internal graph
- Compatibility rules
- Lineage boundary

The parent should bind to the child's public interface, not its private internal
steps.

## Scheduling Intent

DPCS may express scheduling intent while remaining independent of scheduler
implementation.

ETLantic may model portable concepts such as:

- Manual execution
- Time-based intent
- Event-based intent
- Dependency-triggered execution
- Backfill intent
- Catch-up policy
- Timezone
- Concurrency requirements

Vendor-specific schedule configuration should remain in bindings or profiles.

A DPCS contract should state what scheduling behavior is required without
embedding one orchestrator's syntax.

## Execution Requirements

Pipelines may declare runtime requirements that must be satisfied by a target
orchestrator or execution environment.

Examples include:

- Parallel branch support
- Retry support
- Timeout support
- Checkpoint support
- Compensation support
- Approval workflows
- Event processing
- Streaming support
- Resource isolation
- Required plugin capabilities

ETLantic should validate these requirements against declared plugin and
orchestrator capabilities before binding.

## Quality Gates

Quality gates determine whether execution may proceed based on explicit
conditions.

Examples include:

- Data contract validation
- Row-count thresholds
- Data-quality rules
- Approval requirements
- Upstream freshness
- Required diagnostics severity

Quality gates belong to the pipeline semantic model when they affect observable
control flow.

The execution plugin or orchestrator performs the check, but it must preserve
the declared behavior.

## Failure Semantics

DPCS can describe portable failure behavior.

ETLantic should map its callbacks and declarative actions into DPCS where
those behaviors are standardized.

Examples include:

- Fail step
- Fail pipeline
- Retry
- Skip an optional step
- Continue a permitted branch
- Run compensation
- Invoke a nested recovery pipeline
- Quarantine invalid data

Backend-specific exception classes and operational details remain outside the
portable contract.

## Callbacks

Callbacks may enrich ETLantic runtime behavior.

Only callback behavior with defined portable semantics should be emitted into
DPCS.

For example, a declarative retry or fail-pipeline action may be portable, while
a callback that calls a specific internal notification service is an
implementation binding.

ETLantic should distinguish:

- Contractual callback semantics
- Environment-specific operational callbacks

## Execution Profiles

Execution profiles bind a logical pipeline to an environment.

A profile may select:

- Orchestrator
- Dataframe engine
- Storage bindings
- Resource providers
- Validation mode
- Concurrency limits
- Runtime credentials
- Deployment targets

Profiles should not redefine the DPCS pipeline meaning.

They provide implementation-specific bindings and operational configuration.

## Pipeline Plan

After loading or introspecting a pipeline, ETLantic should construct a
validated, implementation-independent Pipeline Plan.

The Pipeline Plan should preserve:

- Pipeline identity
- Public interfaces
- Graph topology
- Step definitions
- Data and control flows
- Contract references
- Scheduling intent
- Execution requirements
- Quality gates
- Failure semantics
- Lineage
- Extensions

The Pipeline Plan acts as ETLantic's semantic intermediate representation.

It is target-agnostic until bound: Local Python, Airflow (`etlantic-airflow`),
or a future orchestrator (Dagster/Prefect) consume the same plan.

## Orchestrator Capabilities

Every orchestrator plugin should declare its capabilities.

Conceptually:

```python
OrchestratorCapabilities(
    scheduling={"manual", "cron", "event"},
    parallel_execution=True,
    retries=True,
    checkpoints=False,
    compensation=False,
    approval_workflows=False,
)
```

ETLantic compares the Pipeline Plan requirements against these capabilities.

Unsupported mandatory capabilities should fail planning or binding rather than
being silently discarded.

## Orchestrator Binding

An orchestrator binding translates a validated Pipeline Plan into a
platform-specific artifact.

Possible outputs include:

- Airflow DAGs
- Dagster definitions
- Prefect deployments
- Local execution graphs
- Deployment manifests
- Orchestration API requests

Bindings must preserve:

- Pipeline and step identities
- Graph topology
- Data and control flows
- Scheduling intent
- Execution requirements
- Quality gates
- Failure semantics
- Lineage
- Contract references

When a target cannot preserve mandatory semantics, binding must fail with
structured diagnostics.

## Local Execution

Local Python execution should still operate through the same Pipeline Plan and
capability model.

Local execution is a backend, not a bypass around DPCS.

This ensures that local tests and external orchestration share the same logical
pipeline semantics.

## Validation

ETLantic should validate DPCS semantics in phases.

### Definition validation

Checks Python declarations:

- Valid pipeline metadata
- Valid source, step, sink, and subpipeline definitions
- Resolved annotations
- Unique identifiers

### Graph validation

Checks:

- Topology
- Dependency integrity
- Required inputs
- Prohibited cycles
- Reachability
- Duplicate edges

### Contract validation

Checks:

- ODCS references
- DTCS references
- Nested DPCS references
- Version and compatibility requirements

### Semantic validation

Checks:

- Scheduling intent
- Execution requirements
- Quality gates
- Failure semantics
- Lineage
- Extension semantics

### Capability validation

Checks whether the selected orchestrator and execution plugins can preserve all
mandatory semantics.

Successful validation does not guarantee successful execution, but invalid
pipelines must not advance to binding.

## Diagnostics

DPCS validation and binding failures should produce structured diagnostics.

A diagnostic may include:

- Stable code
- Severity
- Pipeline identity
- Step identity
- Contract reference
- Graph path
- Validation phase
- Message
- Suggested remediation
- Related locations

Example:

```text
PMDPCS204

Pipeline: customer-pipeline@1.2.0
Step: publish-customers
Phase: orchestrator-binding

The selected orchestrator does not support the mandatory compensation behavior
declared by this pipeline.
```

## Compatibility

Pipeline compatibility should be based on semantics rather than version strings
alone.

Compatibility analysis may consider:

- Public interface changes
- Graph topology
- Step identity and behavior
- Contract references
- Scheduling intent
- Execution requirements
- Quality gates
- Failure semantics
- Lineage
- Extensions

Possible classifications include:

- Fully compatible
- Backward compatible
- Forward compatible
- Conditionally compatible
- Incompatible

ETLantic should use the normative DPCS compatibility model rather than
inventing an unrelated rule system.

## Versioning

Pipeline and specification versions are distinct.

### DPCS specification version

Identifies the version of DPCS used to interpret the document.

### Pipeline contract version

Identifies a revision of one logical pipeline.

Supporting a DPCS specification version does not imply that arbitrary pipeline
revisions are compatible.

Published pipeline identities should remain stable across revisions unless a
new logical pipeline is intentionally created.

## Evolution

Compatible pipeline evolution may include:

- Documentation improvements
- Optional metadata
- Compatible optional outputs
- Backward-compatible subpipeline updates
- Non-semantic extension additions

Breaking changes may include:

- Removing required public inputs or outputs
- Replacing a contract reference incompatibly
- Changing mandatory graph dependencies
- Weakening required quality gates
- Changing failure semantics
- Introducing unsupported mandatory execution requirements

ETLantic should generate compatibility diagnostics and migration guidance
where practical.

## Lineage

DPCS lineage describes logical provenance across the pipeline.

ETLantic can derive lineage from:

- Source contracts
- Step inputs and outputs
- DTCS transformation lineage
- Data-flow edges
- Subpipeline interface mappings
- Sink contracts

Lineage should remain independent of the physical execution history.

Runtime lineage events may supplement, but must not replace, contractual
lineage.

## Generated Artifacts

A pipeline may generate a bundle such as:

```text
contracts/
├── data/
│   ├── raw-customer.odcs.yaml
│   └── customer.odcs.yaml
├── transformations/
│   └── normalize-customers.dtcs.yaml
└── pipelines/
    └── customer-pipeline.dpcs.yaml
```

DPCS generation should be deterministic.

The same validated pipeline model should produce semantically equivalent output
regardless of formatting or serialization.

## Extensions

ETLantic and organizations may define namespaced DPCS extensions.

Extensions may add metadata or behavior not yet standardized, but they must not
redefine mandatory DPCS semantics.

Unknown extensions should be preserved where possible.

Unsupported mandatory extensions should prevent successful validation or
binding.

## Registries

ETLantic may resolve DPCS artifacts through:

- Local files
- Python packages
- Git repositories
- Contract registries
- Network services
- Organization-specific resolvers

Registries should preserve:

- Artifact identity
- Version identity
- Compatibility metadata
- Extension metadata
- Integrity information

Registered artifacts should not be mutated silently.

## Security

Pipeline contracts should not embed secrets.

Runtime credentials should be supplied through external secret management,
resources, bindings, or profiles.

ETLantic should support:

- Artifact integrity verification
- Safe extension processing
- Authorization hooks
- Sensitive diagnostic redaction
- Auditable generation and binding
- Restricted reference resolution

Security policy should protect DPCS artifacts without changing their semantic
meaning.

## Conformance

ETLantic may eventually declare conformance across several DPCS roles:

- Parser
- Validator
- Planner
- Capability evaluator
- Orchestrator binder
- Registry
- Complete implementation

Plugin conformance may be narrower.

For example, an Airflow plugin may conform as an orchestrator binder without
being a DPCS parser or registry.

Conformance claims should identify the supported DPCS specification version and
be verified through shared test suites.

## Recommended Practices

- Author pipelines with typed Python classes.
- Give pipelines and published steps stable identities.
- Reference ODCS, DTCS, and nested DPCS contracts rather than duplicating them.
- Keep public pipeline interfaces explicit.
- Validate the graph before planning.
- Build an implementation-independent Pipeline Plan before binding.
- Require plugins to declare capabilities.
- Fail binding when mandatory semantics cannot be preserved.
- Keep runtime credentials and vendor settings out of DPCS.
- Generate deterministic DPCS artifacts in CI.
- Run compatibility checks before publishing new pipeline revisions.

## Anti-Patterns

### Encoding the pipeline only as an Airflow DAG

An orchestrator artifact is a backend representation, not the portable pipeline
contract.

### Duplicating transformation semantics

DPCS steps should reference DTCS contracts rather than restating transformation
logic.

### Duplicating data schemas

DPCS interfaces and flows should reference ODCS contracts.

### Treating dependency order as serialization order

All graph relationships must be explicit.

### Silently dropping unsupported behavior

Orchestrator bindings must report unsupported mandatory quality gates, failure
semantics, scheduling intent, or execution requirements.

### Exposing private subpipeline nodes

Parent pipelines should bind to the child's public interface.

### Embedding secrets

DPCS artifacts should reference external secret and resource providers.

## Key Principle

> ETLantic authors and plans pipelines in Python. DPCS preserves their
> logical meaning as portable contracts. Orchestrator plugins translate those
> plans into runtime-specific artifacts without changing observable semantics.

## Further Reading

For the normative definition of DPCS, see the
[DPCS 1.0 Specification](../specifications/DPCS_SPEC.md).

This document describes **how ETLantic integrates with DPCS**. It does not
replace or restate the full normative specification.
