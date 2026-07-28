# Frequently Asked Questions

## What is ETLantic?

ETLantic is a Python framework for defining typed, contract-driven data
pipelines. It validates them, generates portable contracts, creates
deterministic plans, and can execute registered Python implementations through
its local runtime.

------------------------------------------------------------------------

## Is ETLantic an orchestration framework?

No.

ETLantic models pipelines and produces resolved `PipelinePlan` objects. It
includes a built-in `LocalScheduler` for development and tests, and
intentionally delegates durable scheduling and external workflow platforms to
optional plugins (for example Airflow compilation via `etlantic-airflow`, or
Prefect direct execution via the shipped `etlantic-prefect`
`ExecutionScheduler` local MVP).

------------------------------------------------------------------------

## Is ETLantic 0.25 production-supported?

ETLantic **0.25.1** is a **Beta** (PyPI) release suitable for documented single-tenant reference
deployments (not unrestricted enterprise production). See
[Capabilities](CAPABILITIES.md) and
[Production readiness](../06_EXECUTION/PRODUCTION_READINESS.md). Multi-tenant
isolation, deployment topology, compliance, and advanced supply-chain controls
remain adopter-owned.

------------------------------------------------------------------------

## What is the difference between Available and Experimental?

**Available** APIs and behaviors are supported within the documented 0.25
single-tenant pilot envelope (the package itself remains **Beta** on PyPI).
Features explicitly labeled **Experimental**, currently including Structured
Streaming foundations and `etlantic-datafusion`, may change and are outside
that claim. A page describing a shipped feature does not make every feature on
that page ready for pilots; check its status label and
[Capabilities](CAPABILITIES.md).

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
logical model. Use Airflow (via `etlantic-airflow`) to compile plans into DAG
artifacts; use a direct-execution scheduler (built-in `LocalScheduler`, or
the shipped `etlantic-prefect` local MVP) to run resolved plans in process; use ETLantic for
typed contracts and fail-closed planning.

------------------------------------------------------------------------

## How does ETLantic compare to dbt, Prefect, or Pandera?

| Tool | Primary job | ETLantic relationship |
|---|---|---|
| **dbt** | SQL transformation project / warehouse analytics | Complementary. ETLantic models typed Python pipelines and multi-engine plans; dbt owns SQL project workflows. |
| **Prefect / Dagster / Airflow** | Orchestration and scheduling | Complementary. Airflow compiles plans to DAG artifacts; the shipped `etlantic-prefect` local MVP directly executes resolved plans (it is not a DAG compiler). Prefect deployment/serve and Dagster remain future. |
| **Pandera / Great Expectations** | Dataframe / table validation libraries | Complementary. ETLantic validates **wiring and contracts** before run; row-level suites remain engine-side or library-side. |

If you need only SQL analytics projects, start with dbt. If you need only
schedulers, start with Airflow/Dagster/Prefect. If you need typed pipeline
composition across engines with secret-free plans, evaluate ETLantic.

------------------------------------------------------------------------

## Why is ETLantic inspired by FastAPI?

FastAPI showed that Python type annotations can drive an outstanding developer
experience. ETLantic applies the same idea to data pipelines: types declare
interfaces that validation and planning can enforce.

That does **not** mean everything is inferred. Profiles, assets, plugin
allowlists, and security modes remain explicit—just as FastAPI still requires
you to declare routes and dependencies.

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

Yes, when you author with `@Transformation.portable` and install the matching
engine plugin. Support differs by engine—see the
[Portable Compiler Matrix](../10_REFERENCE/PORTABLE_COMPILER_MATRIX.md).
Use a native `@implementation(...)` for anything outside that matrix.

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
- Airflow compile (`etlantic-airflow`) and Prefect local scheduler (`etlantic-prefect`)
- Optional SQLModel / keyring packages (`etlantic-sqlmodel`, `etlantic-keyring`)

The transformation contract and pipeline wiring remain unchanged; native
implementation bodies may still differ by engine.

------------------------------------------------------------------------

## Which dataframe engine should I use?

ETLantic is dataframe-engine neutral.

Install `etlantic-polars` or `etlantic-pandas` and set
`Profile.dataframe_engine` accordingly. Prefer Polars when you need lazy
preservation or portable relational compilation; use Pandas when you need the
Pandas ecosystem (eager portable relational compilation is available).
SQL is available via `etlantic-sql` and `Profile.sql_engine="sql"`. Spark is
available via `etlantic-pyspark` and `Profile.spark_engine="pyspark"`.

------------------------------------------------------------------------

## Which engine should I start with?

Start with the built-in local Python engine and memory or JSON/CSV storage; it
has no optional engine dependency and makes validation and wiring easiest to
understand. Add Polars for a first dataframe engine, Pandas for ecosystem
compatibility, SQL when work should remain in PostgreSQL, or PySpark only when
you need Spark semantics and have a working Java environment.

------------------------------------------------------------------------

## Must core and plugin versions match?

Yes. Keep core and optional plugins on the same minor release. For a
reproducible 0.25.0 environment, pin both exactly, for example:

```bash
python -m pip install 'etlantic==0.25.1' 'etlantic-polars==0.25.1'
```

A mismatched plugin may fail discovery, protocol checks, validation, or
planning even when both packages install successfully.

------------------------------------------------------------------------

## Why do `validate` and `plan` work but CLI `run` has no input data?

Validation and planning inspect pipeline definitions—they do not need source
rows.

The [Quickstart](QUICKSTART.md) uses `etlantic init`, which binds assets to
JSON files under `data/`. If `run` shows empty output, check that:

1. Input JSON files exist and match your contract schema.
2. You use the same `--profile` for `validate`, `plan`, and `run`.
3. Asset paths in your profile match the generated project layout.

For in-process demos without file bindings, use
[`examples/memory_customers.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/memory_customers.py)
from a repo checkout and run with `python examples/memory_customers.py`—not
`etlantic run` in a separate process.

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
-   lineage diagrams (including Graphviz DOT and HTML exporters)
-   Mermaid graphs
-   execution plans

------------------------------------------------------------------------

## Can I build ETLantic pipelines in a GUI?

Not as a shipped product. Since 0.24, ETLantic exposes programmatic authoring
APIs (`PipelineDefinition`, builders, `etlantic.pipeline/1` JSON,
`AuthoringService`) that **your application** can wrap in a GUI. Optional
`etlantic-fastapi` is a thin OpenAPI **reference** adapter only — you still
own authentication, persistence, durable jobs, and deployment. See
[Programmatic authoring](../05_PIPELINES/PROGRAMMATIC_AUTHORING.md) and
[Application integration](../08_VISUALIZATION/APPLICATION_INTEGRATION.md).

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

## How do I author pipelines without classes (builders / JSON)?

Since 0.24, ETLantic ships programmatic authoring: functional builders,
`PipelineDefinition`, and lossless `etlantic.pipeline/1` JSON. Class
`Pipeline` subclasses, builders, and JSON documents normalize to the same
definition and feed the same validate/plan/run path.

Start with
[Programmatic authoring](../05_PIPELINES/PROGRAMMATIC_AUTHORING.md). From a
clone, `examples/pipeline_definition_json.py` shows builders → JSON →
`etlantic validate`.

------------------------------------------------------------------------

## Why does `from etlantic import SomeError` warn?

Specialist root exports demoted in 0.22 (including most exception types) remain
as pre-1.0 compatibility aliases and emit a **one-time** demotion warning.
Prefer owning modules:

```python
from etlantic.exceptions import DataValidationError, PipelineValidationError
```

Curated root symbols (`Data`, `Pipeline`, `Transformation`, …) do not warn.
See [Exceptions](../10_REFERENCE/EXCEPTIONS.md) and
[Surface inventory](../10_REFERENCE/SURFACE_INVENTORY.md).

------------------------------------------------------------------------

## What is the difference between profile name and `security_mode`?

A profile **name** (for example `development`, `prod-example`) is how you
select a profile file or object. Production **fail-closed trust** keys off
`security_mode="production"` (and `plugin_allowlist`), **not** the profile
name or `security_domain`.

A profile named `production` that still has `security_mode: "development"`
does **not** enable production trust. See
[Profile primer](../05_PIPELINES/PROFILE_PRIMER.md) and
[Capabilities](CAPABILITIES.md).

------------------------------------------------------------------------

## Where should I go next?

1. [Installation](INSTALLATION.md) → [Quickstart](QUICKSTART.md) →
   [First Pipeline](FIRST_PIPELINE.md) → [Engine selection](ENGINE_SELECTION.md)
2. [Capabilities](CAPABILITIES.md) for the shipped boundary
3. Runnable examples from a checkout (see [Examples](../09_EXAMPLES/README.md));
   pip users stay on paste-ready Quickstart
4. [CLI reference](../10_REFERENCE/CLI.md) for `etlantic validate|plan|run|compile|viz`
5. Foundations (philosophy / architecture) when you want deeper design context
