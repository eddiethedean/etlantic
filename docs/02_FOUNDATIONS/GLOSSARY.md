# Glossary

> **Status: Available in ETLantic 0.36.0.**

This glossary defines the core terminology used throughout the
ETLantic documentation. Unless otherwise noted, these definitions
reflect ETLantic's architecture and may differ from how similar
terms are used in other ETL frameworks.

## Artifact

A generated file or runtime data value/reference. Generated artifacts include
[ODCS](../03_DATA_CONTRACTS/ODCS.md), [DTCS](../04_TRANSFORMATIONS/DTCS.md), [DPCS](../05_PIPELINES/DPCS.md), documentation, diagrams, and compiled backend output. Runtime
artifacts include dataframes, database relations, files, and external
references passed between physical execution units.

## Binding

A configuration that connects a logical pipeline component to a concrete
runtime implementation, such as a Polars transformation, an Airflow
orchestrator, or a storage provider.

## Callback

A user-defined function invoked in response to a lifecycle event, such
as invalid data, execution failure, or pipeline completion.

## Contract

A portable, declarative description of part of a data pipeline.
ETLantic recognizes three primary contract types:

-   Data Contract
-   Transformation Contract
-   Pipeline Contract

## ContractModel

The companion library responsible for operationalizing data contracts.
Prefer ETLantic's `Data` base class for typed datasets; ContractModel
remains the interchange/runtime companion for ODCS documents.

## DPCS

**Data Pipeline Contract Standard.**

A portable specification describing the logical topology of a pipeline:
extracts, transformations, loads, and their relationships. Wire formats may
still say sources/sinks; authoring uses `Extract` / `Load`.

## DTCS

**Data Transformation Contract Standard.**

A portable specification describing the interface of a transformation,
including its inputs, outputs, parameters, and metadata.

## Data

The primary authoring type for a typed dataset in ETLantic. Subclass
`Data` (from `etlantic`) to declare schema and constraints; pipelines
and transformations reference these classes at ports.

`DataContractModel` remains a deprecated compatibility alias for `Data`.

## Data Contract

A typed description of a dataset. In ETLantic, data contracts are
authored as `Data` subclasses (ContractModel-compatible Pydantic models)
and can be represented as ODCS documents.

## Data Contract Model

Deprecated name for a `Data` subclass. Prefer `Data`; `DataContractModel`
is kept only as a compatibility alias.

## Execution Engine

The technology that performs actual work, such as Polars, Pandas, Spark,
or a remote processing service.

## Execution Plan

A resolved representation of a logical pipeline that identifies
dependencies, runtime bindings, and the order of execution. An execution
plan is produced by ETLantic but executed by plugins.

The preferred public term is `PipelinePlan`.

## PipelinePlan

The immutable, secret-free resolved IR produced by planning. Contains
resolved assets, capability decisions, validation phases, and a fingerprint.
Plans are inspectable before any write and are the input to `run` / `compile`.

## Plugin allowlist

`Profile.plugin_allowlist` — the map of trusted plugin distribution names to
version constraints. Required and fail-closed when `security_mode="production"`.
The allowlist selects discovered plugins; it does not install packages.

## security_mode

`Profile.security_mode`: `development` | `test` | `production`. Production
mode enables fail-closed plugin trust and related Safe I/O expectations.
Detection is by this field only—not by profile name or `security_domain`.

## SafeIoPolicy

The policy that constrains filesystem and outbound I/O for reports, schema
history, caches, and artifact roots. World-writable or undeclared paths fail
closed under production expectations.

## Fingerprint

A deterministic digest over the secret-free plan (or related artifact).
Verified on deserialize and again before compile/run trust boundaries.
Regenerate plans after upgrades that change participation rules.

## Gate A / tabular interchange

Versioned Polars↔Pandas tabular interchange using wire schema
`etlantic.interchange/1`. Plans may carry interchange evidence references;
runtime reports may record observed interchange evidence for reconciliation.

## Execution Region

A group of compatible logical nodes that a backend may realize together, such
as a fused SQL query or one lazy Spark plan.

## Hook

A specialized callback associated with a pipeline lifecycle event.

## Input

A typed input port declared by a transformation using `Input[T]`.

## Intermediate Representation (IR)

A model between authoring and backend execution. ETLantic distinguishes
the typed logical graph from the resolved `PipelinePlan`; the latter is the
primary execution-facing IR.

## Logical Graph

The portable, user-visible graph of sources, steps, sinks, ports, and
dependencies.

## Node

A logical element within a pipeline graph, such as a source,
transformation step, or sink.

## ODCS

**Open Data Contract Standard.**

The open specification used to represent data contracts.

## Output

A typed output port declared by a transformation using `Output[T]`.

## Parameter

A typed configuration value declared by a transformation using
`Parameter[T]`. Parameters influence transformation behavior without
becoming part of the pipeline graph.

## Pipeline

A logical description of how transformations and data contracts are
connected. A pipeline models intent rather than execution.

## PipelineDefinition

The immutable, unresolved, authoring-complete representation of a pipeline
(Available in 0.24). Class declarations, functional builders, canonical JSON,
and visual edit operations normalize to this model. It is distinct from a
resolved `PipelinePlan`.

## Authoring Catalog

The machine-readable catalog of contracts, transformations, ports, parameters,
policies, providers, plugins, capabilities, and UI-safe metadata available to
programmatic and visual pipeline builders (Available in 0.24).

## Edit Command

An immutable operation that updates a `PipelineDefinition`, such as adding a
node, connecting ports, or changing a parameter (Available in 0.24). Commands
use stable document paths and support application-level undo, revision, and
concurrency workflows.

## ETLantic

The framework described by this documentation. ETLantic models,
validates, documents, and plans pipelines while delegating execution to
external plugins.

## Plugin

An extension that provides runtime functionality not implemented by the
ETLantic core, such as dataframe processing, orchestration,
storage, or compilation.

## Physical Graph

The backend-specific graph of tasks, statements, stages, and materialization
boundaries created from a `PipelinePlan`.

## Portable Transformation

A transformation whose relational behavior is represented by ETLantic's
closed, backend-independent transformation IR and compiled by an engine plugin.
The proposed authoring API resembles PySpark DataFrame and Column expressions.

## Portable Transformation Compiler

A plugin component that proves support for and compiles a portable
transformation IR into native Polars, Pandas, SQL, Spark, or other backend
expressions without changing its normative meaning.

## Profile

A named runtime configuration that selects logical assets (prefer
`assets=`), resources, and execution settings for a pipeline without
changing its logical definition.

## Resource

An external dependency provided at runtime, such as a database
connection, object storage client, or API client.

## Resource Provider

A Plugin SDK component that acquires, scopes, injects, and cleans up runtime
resources.

## Load

Typed pipeline publication boundary (`Load[T]`). Declares a logical **asset**
name resolved by a profile. Receives data from upstream transformations and
publishes it through an execution plugin. Deprecated alias: `Sink`. Wire/plan
field remains `binding`.

## Sink

Deprecated alias of [Load](#load) (removed in 0.16).

## Secret Provider

A Plugin SDK component that resolves a logical `SecretRef` into a protected
runtime value inside an authorized execution boundary.

## SecretRef

A serializable reference to a secret provider, identifier, optional field, and
version policy. It never contains the resolved secret value.

## SecretValue

A runtime-only sensitive wrapper whose display is redacted and whose ordinary
serialization is prohibited.

## Extract

Typed pipeline entry boundary (`Extract[T]`). Declares a logical **asset**
name resolved by a profile and introduces data from an external system.
Deprecated alias: `Source`. Graph kind remains `"source"`; DPCS retains
`etlantic:binding`.

## Asset

Public authoring name for a logical extract/load identifier (`asset=`).
Profiles prefer `Profile.assets`. Serialized plans and plugins still use
`binding` for stability.

## Source

Deprecated alias of [Extract](#extract) (removed in 0.16).

## Step

An instantiated transformation within a pipeline graph.

## Transformation

A typed, declarative description of a data operation. A transformation
specifies inputs, outputs, and parameters, but not a particular
execution technology.

## Transformation IR

The immutable, versioned DTCS Transformation Plan representation of portable
relational and scalar expressions, published as `dtcs.transform-plan/2` (v1 readable). Public
canonical models belong to the `dtcs` package. It contains no source rows,
resolved secrets, executable closures, or backend-native objects.

## Validation

The process of verifying contracts, pipeline wiring, parameters, and
implementation compatibility before execution.

## Visualization

A generated representation of a pipeline, such as Mermaid, Graphviz,
HTML, or lineage diagrams, derived from the logical model.

## Summary

ETLantic intentionally distinguishes between:

-   **Modeling** --- describing pipelines with typed Python classes.
-   **Planning** --- validating and preparing those models for
    execution.
-   **Execution** --- performing work through interchangeable plugins.

Keeping these concepts separate is fundamental to the architecture and
developer experience of ETLantic.
