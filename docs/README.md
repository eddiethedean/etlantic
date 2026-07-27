<div class="etlantic-hero">
  <div class="etlantic-hero__content">
    <span class="etlantic-hero__eyebrow">Typed Python data pipelines</span>
    <h1>Validate before write.<br><span class="etlantic-hero__nowrap">Run where your engines are.</span></h1>
    <p>Define pipelines as typed classes, catch bad wiring before any write, then
    run or compile on Polars, Pandas, SQL, Spark, or Airflow.</p>
    <div class="etlantic-hero__actions">
      <a class="md-button md-button--primary" href="01_GETTING_STARTED/QUICKSTART/">Quickstart</a>
      <a class="md-button" href="01_GETTING_STARTED/INSTALLATION/">Installation</a>
    </div>
  </div>
</div>

ETLantic is a Python framework for defining typed, contract-driven data
pipelines and coordinating their execution through the tools you already
choose. It is **not** a warehouse tool, scheduler, or dataframe engine.

!!! tip "Green path (start here only)"
    1. [Installation](01_GETTING_STARTED/INSTALLATION.md) — `pip install etlantic==0.24.0`
    2. [Quickstart](01_GETTING_STARTED/QUICKSTART.md) — `python -m etlantic init` → validate → run
    3. [First Pipeline](01_GETTING_STARTED/FIRST_PIPELINE.md) — evolve the generated project
    4. [Engine selection](01_GETTING_STARTED/ENGINE_SELECTION.md) — then an engine tutorial

    After first success: [Capabilities](01_GETTING_STARTED/CAPABILITIES.md),
    [Evaluator](01_GETTING_STARTED/EVALUATOR.md), [Compare](01_GETTING_STARTED/COMPARE.md).
    Pages marked **Future design** are not APIs.

## Project status

**ETLantic 0.24.0** is a **Beta** release for documented single-tenant pilots.
Install with `pip install 'etlantic==0.24.0'`. Class, functional, and JSON
authoring share `PipelineDefinition` (`etlantic.pipeline/1`).

- **Use today:** single-tenant pilots and reference deployments (see
  [Capabilities](01_GETTING_STARTED/CAPABILITIES.md)).
- **Not included:** multi-tenant control plane, managed Spark, SLA, unrestricted
  enterprise compliance beyond shipped SBOM/attestations.
- **Experimental:** Structured Streaming; `etlantic-datafusion` (Gate B stub).

## Minimal working example

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install 'etlantic==0.24.0'
mkdir my-pipeline && cd my-pipeline
python -m etlantic init --with-toml
python -m etlantic validate pipeline.py:SamplePipeline --profile development
python -m etlantic run pipeline.py:SamplePipeline --profile development
cat data/out.json
```

You should see `succeeded` and Ada/Grace sample rows (identity transform).
Next: change the transform in [First Pipeline](01_GETTING_STARTED/FIRST_PIPELINE.md)
or try [Programmatic authoring](05_PIPELINES/PROGRAMMATIC_AUTHORING.md).

The PyPI wheel does **not** include `examples/`; from a checkout an optional
in-memory SDK demo is
[`examples/memory_customers.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/memory_customers.py).

## The Architecture in One View

```text
Typed Python authoring or portable contracts
                    │
                    ▼
          Typed logical pipeline model
                    │
                    ▼
     Introspection and semantic validation
                    │
                    ▼
        Profile and capability resolution
                    │
                    ▼
        Immutable PipelinePlan (resolved IR)
                    │
          ┌─────────┼──────────┐
          ▼         ▼          ▼
      Execute    Compile    Generate
          │         │          │
          ▼         ▼          ▼
      Plugins   Airflow/SQL  Docs/graphs
```

ETLantic owns modeling, validation, planning, and coordination. Standards own
contract meaning. Plugins and external systems perform the work.

## Choose Your Path

Follow the **Green path** above for first success. Optional persona forks:

### I want to run something in five minutes

Same as the Green path: [Installation](01_GETTING_STARTED/INSTALLATION.md) →
[Quickstart](01_GETTING_STARTED/QUICKSTART.md) →
[First Pipeline](01_GETTING_STARTED/FIRST_PIPELINE.md).

### I want to understand the idea

1. [Manifesto](ETLANTIC_MANIFESTO.md)
2. [Evaluator brief](01_GETTING_STARTED/EVALUATOR.md)
3. [Core Concepts](02_FOUNDATIONS/CORE_CONCEPTS.md)
4. [Architecture](02_FOUNDATIONS/ARCHITECTURE.md)

### I want to author pipelines

1. [Getting Started](01_GETTING_STARTED/README.md)
2. [Data Contracts](03_DATA_CONTRACTS/README.md)
3. [Transformations](04_TRANSFORMATIONS/README.md)
4. [Pipelines](05_PIPELINES/README.md)

### I want to understand execution (shipped)

1. [Execution Model](06_EXECUTION/EXECUTION_MODEL.md)
2. [Local Python](06_EXECUTION/LOCAL_PYTHON.md)
3. [Polars](06_EXECUTION/POLARS.md) / [Pandas](06_EXECUTION/PANDAS.md) / [SQL](06_EXECUTION/SQL.md)

### I want runnable examples

See [Examples](09_EXAMPLES/README.md) (runnable guides only in the primary nav).

### I want to extend plugins

1. [Plugin SDK overview](07_PLUGIN_SDK/README.md)
2. [Testing Plugins](07_PLUGIN_SDK/TESTING_PLUGINS.md)

## Documentation Map

| Section | Purpose |
|---|---|
| [Getting Started](01_GETTING_STARTED/README.md) | Learn the core workflow |
| [Foundations](02_FOUNDATIONS/README.md) | Philosophy and architecture |
| [Data Contracts](03_DATA_CONTRACTS/README.md) | Typed datasets |
| [Transformations](04_TRANSFORMATIONS/README.md) | Typed transformation interfaces |
| [Pipelines](05_PIPELINES/README.md) | Portable graphs |
| [Execution](06_EXECUTION/README.md) | Engines and runtime |
| [Examples](09_EXAMPLES/README.md) | Runnable pointers |
| [Reference](10_REFERENCE/README.md) | CLI, API, compatibility |
| [Contribute](11_DEVELOPMENT/CONTRIBUTING.md) | Contributing and release |
| [Project](11_DEVELOPMENT/README.md) | Roadmap, audits, design proposals |

## Non-Goals

ETLantic is not intended to become a dataframe engine, distributed scheduler,
storage system, secret manager, or a replacement for Pandas, Polars, SQL,
Spark, Airflow, or Dagster. It is the typed framework that connects those
systems without letting any one of them define portable pipeline meaning.
