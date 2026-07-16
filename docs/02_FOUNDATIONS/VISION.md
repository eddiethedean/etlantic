# Vision

## Our Mission

Pipelantic exists to make data engineering as approachable,
expressive, and reliable as modern Python web development.

Just as FastAPI transformed API development by placing Python type
annotations at the center of the developer experience, Pipelantic
applies that philosophy to ETL and data pipelines.

Our goal is simple:

> Model pipelines with typed Python classes. Let the framework derive
> everything else.

## The Problem

Modern data platforms often separate:

-   Data models
-   Transformation logic
-   Pipeline topology
-   Validation
-   Documentation
-   Execution
-   Governance

Developers frequently duplicate the same information across Python code,
YAML files, orchestration systems, and documentation. This duplication
increases maintenance costs and allows implementations to drift away
from their intended design.

Pipelantic aims to eliminate that duplication by making Python's type
system the primary source of truth.

## Our Vision

Pipelantic is a modeling framework---not an execution engine.

Developers define:

-   Data Contracts
-   Transformation Contracts
-   Pipeline Contracts

Pipelantic then:

-   validates the model
-   generates portable contracts
-   produces documentation and diagrams
-   plans execution
-   delegates execution to interchangeable plugins

The framework models *what* a pipeline is. Execution plugins determine
*how* it runs.

## Design Goals

### Type-Driven Development

Python type annotations should describe pipeline interfaces with minimal
additional configuration.

### Contract-First Without the Burden

Portable contracts are essential, but they should be generated from code
whenever practical rather than maintained by hand.

### Execution Independence

Business logic should remain stable while execution technologies evolve.
The same pipeline should be capable of running locally, on Airflow, or
through future orchestration systems simply by changing runtime
bindings.

### Validation Before Execution

Pipeline mistakes should be discovered during development and planning,
not after expensive jobs have started.

### Open Standards

Pipelantic embraces open standards wherever possible.

-   ODCS for data contracts
-   DTCS for transformation contracts
-   DPCS for pipeline contracts

### Excellent Developer Experience

Pipeline authors should enjoy:

-   rich editor support
-   static analysis
-   autocomplete
-   generated documentation
-   clear diagnostics
-   minimal boilerplate

## What Success Looks Like

A successful Pipelantic project allows a developer to understand an
entire data pipeline by reading a small number of well-typed Python
classes.

Those classes become the foundation for:

-   validation
-   contract generation
-   execution planning
-   documentation
-   visualization
-   runtime execution

without rewriting the same information in multiple places.

Success also means Pipelantic remains small enough to explain:

```text
Types define interfaces.
Contracts define portable meaning.
Pipelines define topology.
Profiles bind environments.
Plans resolve execution.
Plugins perform adaptation.
External engines do the work.
```

The framework should make sophisticated planning possible without making the
basic authoring experience feel sophisticated.

## Long-Term Vision

We envision an ecosystem where contracts, transformations, and pipelines
are portable across organizations and execution environments.

Pipelantic should become the reference authoring experience for
contract-driven data engineering, enabling developers to focus on
business logic while relying on open standards and interchangeable
execution engines.

That vision includes:

- Code-first and contract-first interoperability
- Static lineage before execution
- Capability-aware backend selection
- SQL and Spark execution regions
- Local execution and external orchestration from one plan
- A stable Plugin SDK for community integrations
- Reproducible contracts, plans, diagrams, and documentation

## Relationship to the Manifesto

The Pipelantic Manifesto defines the project's guiding philosophy.

This Vision document explains the destination.

Subsequent chapters describe the architecture, principles, and
implementation decisions that move the project toward that vision.

Because later milestones are still design-led, the
[Documentation Status](DOCUMENTATION_STATUS.md) chapter explains how to read
accepted designs, proposals, examples, and normative requirements.
