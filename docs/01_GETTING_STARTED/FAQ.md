# Frequently Asked Questions

## What is Pipelantic?

Pipelantic is a Python framework for defining typed, contract-driven data
pipelines. It validates them, generates portable contracts, creates
deterministic plans, and can execute registered Python implementations through
its local runtime.

------------------------------------------------------------------------

## Is Pipelantic an orchestration framework?

No.

Pipelantic models pipelines and produces resolved `PipelinePlan` objects. It intentionally
delegates scheduling and orchestration to external systems such as
Airflow or other orchestration plugins.

------------------------------------------------------------------------

## Is Pipelantic an ETL engine?

No.

Pipelantic does not implement a dataframe engine, database clients,
scheduling, or distributed execution. It includes an in-process local runtime
with memory, callable, JSON, CSV, and no-write storage, plus optional Polars,
Pandas, and SQL plugins that execute through versioned protocols.

Instead, it coordinates existing tools through a common typed model.

------------------------------------------------------------------------

## Why create Pipelantic instead of using Airflow or Dagster?

Airflow and Dagster are excellent orchestration systems.

Pipelantic solves a different problem.

Its focus is:

-   typed pipeline modeling
-   contract generation
-   validation
-   portability
-   execution abstraction

Pipelantic's architecture is designed so future plugins can consume the same
plans without changing pipeline definitions. External orchestrator compilation
is not included in 0.6.

------------------------------------------------------------------------

## Why is Pipelantic inspired by FastAPI?

FastAPI demonstrated that Python type annotations can become the
foundation for an outstanding developer experience.

Pipelantic applies the same philosophy to data engineering.

Types define interfaces.

Everything else can be inferred.

------------------------------------------------------------------------

## What are Data Contracts?

Data contracts describe datasets.

Pipelantic uses ContractModel-compatible Pydantic models as the
source of truth and generates Open Data Contract Standard (ODCS)
documents from those models.

------------------------------------------------------------------------

## What are Transformation Contracts?

Transformation contracts describe the logical interface of a
transformation.

They specify:

-   inputs
-   outputs
-   parameters
-   metadata

They intentionally do not specify implementation details.

------------------------------------------------------------------------

## What are Pipeline Contracts?

Pipeline contracts describe how data contracts and transformation
contracts are connected together.

Pipelantic can generate Data Pipeline Contract Standard (DPCS)
documents directly from pipeline classes.

------------------------------------------------------------------------

## Why are execution engines separate?

Keeping execution separate allows the same logical pipeline to execute
through different runtimes.

Examples include:

- local Python
- Polars / Pandas (optional plugins)
- SQL (`pipelantic-sql`)
- future Spark or Airflow backends

Business logic remains unchanged.

------------------------------------------------------------------------

## Which dataframe engine should I use?

Pipelantic is dataframe-engine neutral.

Install `pipelantic-polars` or `pipelantic-pandas`, register
`@Transformation.implementation("polars")` / `"pandas"`, and set
`Profile.dataframe_engine` accordingly. Prefer Polars when you need lazy
preservation; use Pandas when you need the Pandas ecosystem. SQL is available
via `pipelantic-sql` and `Profile.sql_engine="sql"`. Spark backends are a later
milestone.

------------------------------------------------------------------------

## Does Pipelantic support asynchronous execution?

Yes.

Users may write synchronous (`def`) or asynchronous (`async def`)
implementations.

Pipelantic normalizes invocation internally so authors do not need to
manage event loops, worker threads, or execution scheduling.

------------------------------------------------------------------------

## Do I have to write YAML contracts?

No.

The preferred workflow is code-first.

Pipelantic generates ODCS, DTCS, and DPCS contracts automatically
from Python definitions.

Existing contracts can also be loaded and consumed.

------------------------------------------------------------------------

## Can I use existing ODCS contracts?

Yes.

Pipelantic supports loading existing ODCS contracts and integrating
them into typed pipeline definitions.

------------------------------------------------------------------------

## Is validation optional?

Validation is a core feature.

Pipelantic validates contracts, pipeline wiring, parameter types, and
implementation compatibility before execution whenever possible.

------------------------------------------------------------------------

## Can one transformation have multiple implementations?

Yes.

For example, the same transformation contract may have:

- a local Python implementation
- a Polars implementation
- a Pandas implementation
- later, a Spark or SQL implementation (future milestones)

The logical transformation remains unchanged.

------------------------------------------------------------------------

## Is Pipelantic tied to a specific cloud provider?

No.

Pipelantic is designed to be cloud-agnostic.

Cloud-specific integrations are implemented through plugins.

------------------------------------------------------------------------

## Can Pipelantic generate documentation?

Yes.

Pipelantic 0.5 generates or exposes:

-   contract documentation
-   pipeline documentation
-   lineage diagrams
-   Mermaid graphs
-   execution plans

Graphviz and generated HTML pipeline documentation remain future design work.

------------------------------------------------------------------------

## Who should use Pipelantic?

Pipelantic is intended for:

-   data engineers
-   analytics engineers
-   platform engineers
-   ETL framework authors
-   organizations adopting contract-first data engineering

------------------------------------------------------------------------

## Where should I go next?

Continue with the **Foundations** section to learn the design
philosophy, architecture, and core concepts behind Pipelantic.
