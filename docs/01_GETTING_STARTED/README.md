# Getting Started

Welcome to Pipelantic!

> **Project status:** 0.5.0 provides the typed modeling kernel, contract
> interoperability (ODCS/DTCS/DPCS), multi-phase validation, profiles, an
> immutable secret-free `PipelinePlan`, a local async runtime with run
> reports, and Polars/Pandas dataframe plugins. Examples that require SQL,
> Spark, or external orchestrators describe later milestones. See
> [Documentation Status](../02_FOUNDATIONS/DOCUMENTATION_STATUS.md).

This section is designed to get you productive as quickly as possible.
Rather than starting with implementation details, you'll learn the core
ideas that make Pipelantic different from traditional ETL frameworks.

## What You'll Learn

By the end of this guide you will be able to:

-   Install Pipelantic
-   Define typed data contracts
-   Define typed transformations
-   Wire transformations into pipelines
-   Validate your pipeline before execution
-   Generate portable contract specifications
-   Understand how later milestones add execution plugins

## Prerequisites

You should be comfortable with:

-   Python 3.11+
-   Basic type annotations
-   Pydantic models
-   ETL concepts

No prior experience with orchestration frameworks is required.

## Documentation Roadmap

Read the Getting Started section in this order:

1. [Installation](INSTALLATION.md)
2. [Current Capabilities and Limitations](CAPABILITIES.md)
3. [Quickstart](QUICKSTART.md)
4. [Your First Pipeline](FIRST_PIPELINE.md)
5. [Project Structure](PROJECT_STRUCTURE.md)
6. [Troubleshooting](TROUBLESHOOTING.md)
7. [FAQ](FAQ.md)

## The Pipelantic Mental Model

Pipelantic separates **modeling** from **execution**.

You describe *what* the pipeline is:

-   Data Contracts
-   Transformation Contracts
-   Pipeline Contracts

Pipelantic validates and plans the pipeline.

Pipelantic 0.4 can execute registered Python implementations with its local
runtime. Future plugins will connect the same plans to dataframe, SQL, Spark,
and orchestration systems.

``` text
Python Classes
      │
      ▼
ODCS + DTCS + DPCS
      │
      ▼
Pipeline Validation
      │
      ▼
Execution Planning
      │
      ▼
Local Python Runtime (0.4)
Future External Plugins
```

## A Preview

``` python
from pipelantic import (
    Data,
    Pipeline,
    Transformation,
    Input,
    Output,
)

class Customer(Data):
    id: int
    name: str

class NormalizeCustomers(Transformation):
    customers: Input[Customer]
    result: Output[Customer]

class CustomerPipeline(Pipeline):
    ...
```

This should feel familiar if you've used FastAPI: Python type
annotations are the source of truth.

## Philosophy

Pipelantic is built around a few core ideas:

-   Types describe interfaces.
-   Contracts are generated from code.
-   Pipelines model intent, not execution.
-   Validation happens before execution.
-   Execution engines are replaceable.

## Next Step

Continue with [Installation](INSTALLATION.md), then check the
[current capability boundary](CAPABILITIES.md).
