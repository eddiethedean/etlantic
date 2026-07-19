# Frequently Asked Questions

## What is ETLantic?

ETLantic is a Python framework for defining typed, contract-driven data
pipelines. It validates them, generates portable contracts, creates
deterministic plans, and can execute registered Python implementations through
its local runtime.

------------------------------------------------------------------------

## Is ETLantic an orchestration framework?

No.

ETLantic models pipelines and produces resolved `PipelinePlan` objects. It intentionally
delegates scheduling and orchestration to external systems such as
Airflow or other orchestration plugins.

------------------------------------------------------------------------

## Is ETLantic an ETL engine?

No.

ETLantic does not implement a dataframe engine, database clients,
scheduling, or distributed cluster management. It includes an in-process local
runtime with memory, callable, JSON, CSV, and no-write storage, plus optional
Polars, Pandas, SQL, and PySpark plugins that execute through versioned
protocols.

Instead, it coordinates existing tools through a common typed model.

------------------------------------------------------------------------

## Why create ETLantic instead of using Airflow or Dagster?

Airflow and Dagster are excellent orchestration systems.

ETLantic solves a different problem.

Its focus is:

-   typed pipeline modeling
-   contract generation
-   validation
-   portability
-   execution abstraction

ETLantic's architecture is designed so plugins can consume the same
logical model. Use Airflow (via `etlantic-airflow`) or another orchestrator
for scheduling; use ETLantic for typed contracts and fail-closed planning.

------------------------------------------------------------------------

## How does ETLantic compare to dbt, Prefect, or Pandera?

| Tool | Primary job | ETLantic relationship |
|---|---|---|
| **dbt** | SQL transformation project / warehouse analytics | Complementary. ETLantic models typed Python pipelines and multi-engine plans; dbt owns SQL project workflows. |
| **Prefect / Dagster / Airflow** | Orchestration and scheduling | Complementary. ETLantic emits plans/DAGs; orchestrators run them. |
| **Pandera / Great Expectations** | Dataframe / table validation libraries | Complementary. ETLantic validates **wiring and contracts** before run; row-level suites remain engine-side or library-side. |

If you need only SQL analytics projects, start with dbt. If you need only
schedulers, start with Airflow/Dagster/Prefect. If you need typed pipeline
composition across engines with secret-free plans, evaluate ETLantic.

------------------------------------------------------------------------

## Why is ETLantic inspired by FastAPI?

FastAPI demonstrated that Python type annotations can become the
foundation for an outstanding developer experience.

ETLantic applies the same philosophy to data engineering.

Types define interfaces.

Everything else can be inferred.

------------------------------------------------------------------------

## What are Data Contracts?

Data contracts describe datasets.

ETLantic uses ContractModel-compatible Pydantic models as the
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

## Can one transformation run on Polars, PySpark, Pandas, and SQL?

ETLantic ships `@Transformation.portable` / `etlantic.transform` authoring
(0.11+) that emits `dtcs.transform-plan/2`. **0.12** executes Polars
**kernel** plans without a native `@implementation("polars")` when
`portable_transform_policy` is `prefer` or `require` and `etlantic-polars` is
installed. **0.13** shipped Polars and PySpark `portable-relational/1`
compilers; **0.14** shipped the eager Pandas compiler. Safe SQL portable
lowering for that claim set is the **0.15** exit gate—register native
`@implementation("sql")` today, and keep native implementations for profiles
outside the advertised claim set. Advanced families graduate later (0.15
continuation). Native implementations remain the escape hatch outside the
portable claim.

------------------------------------------------------------------------

## What are Pipeline Contracts?

Pipeline contracts describe how data contracts and transformation
contracts are connected together.

ETLantic can generate Data Pipeline Contract Standard (DPCS)
documents directly from pipeline classes.

------------------------------------------------------------------------

## Why are execution engines separate?

Keeping execution separate allows the same logical pipeline to execute
through different runtimes.

Examples include:

- local Python
- Polars / Pandas (optional plugins)
- SQL (`etlantic-sql`)
- PySpark (`etlantic-pyspark`)
- Airflow (`etlantic-airflow`) and other orchestrator plugins
- Optional SQLModel / keyring packages in 0.9+

The transformation contract and pipeline wiring remain unchanged; native
implementation bodies may still differ by engine.

------------------------------------------------------------------------

## Which dataframe engine should I use?

ETLantic is dataframe-engine neutral.

Install `etlantic-polars` or `etlantic-pandas` and set
`Profile.dataframe_engine` accordingly. Prefer Polars when you need lazy
preservation or portable relational compilation; use Pandas when you need the
Pandas ecosystem (eager portable relational compilation is available in 0.14).
SQL is available via `etlantic-sql` and `Profile.sql_engine="sql"`. Spark is
available via `etlantic-pyspark` and `Profile.spark_engine="pyspark"`.

------------------------------------------------------------------------

## Does ETLantic support asynchronous execution?

Yes.

Users may write synchronous (`def`) or asynchronous (`async def`)
implementations.

ETLantic normalizes invocation internally so authors do not need to
manage event loops, worker threads, or execution scheduling.

------------------------------------------------------------------------

## Do I have to write YAML contracts?

No.

The preferred workflow is code-first.

ETLantic generates ODCS, DTCS, and DPCS contracts automatically
from Python definitions.

Existing contracts can also be loaded and consumed.

------------------------------------------------------------------------

## Can I use existing ODCS contracts?

Yes.

ETLantic supports loading existing ODCS contracts and integrating
them into typed pipeline definitions.

------------------------------------------------------------------------

## Is validation optional?

Validation is a core feature.

ETLantic validates contracts, pipeline wiring, parameter types, and
implementation compatibility before execution whenever possible.

------------------------------------------------------------------------

## Can one transformation have multiple implementations?

Yes.

For example, the same transformation contract may have:

- a local Python implementation
- a Polars implementation
- a Pandas implementation
- a SQL implementation (`@….implementation("sql")` with `Profile.sql_engine`)
- a PySpark implementation (`@….implementation("pyspark")` with
  `Profile.spark_engine`)

The logical transformation remains unchanged.

------------------------------------------------------------------------

## Is ETLantic tied to a specific cloud provider?

No.

ETLantic is designed to be cloud-agnostic.

Cloud-specific integrations are implemented through plugins.

------------------------------------------------------------------------

## Can ETLantic generate documentation?

Yes.

ETLantic generates or exposes:

-   contract documentation
-   pipeline documentation
-   lineage diagrams (including Graphviz DOT and HTML exporters in 0.9+)
-   Mermaid graphs
-   execution plans

------------------------------------------------------------------------

## Does ETLantic include SparkForge / medallion layers?

No.

Bronze / silver / gold stay in SparkForge. Optional package
`etlantic-sparkforge` maps medallion IR onto ordinary ETLantic nodes,
profiles, and reports. See [Migrating 0.9 → 0.10](../11_DEVELOPMENT/MIGRATION_0_9_TO_0_10.md).

------------------------------------------------------------------------

## Who should use ETLantic?

ETLantic is intended for:

-   data engineers
-   analytics engineers
-   platform engineers
-   ETL framework authors
-   organizations adopting contract-first data engineering

------------------------------------------------------------------------

## Where should I go next?

1. [Quickstart](QUICKSTART.md) or [Your First Pipeline](FIRST_PIPELINE.md)
2. [Capabilities](CAPABILITIES.md) for the shipped boundary
3. Runnable examples under `examples/` (see [Examples](../09_EXAMPLES/README.md))
4. [CLI reference](../10_REFERENCE/CLI.md) for `etlantic validate|plan|run|compile|viz`
5. Foundations (philosophy / architecture) when you want deeper design context
