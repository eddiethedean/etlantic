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
    1. [Installation](01_GETTING_STARTED/INSTALLATION.md) — `pip install etlantic==0.27.0`
    2. [Quickstart](01_GETTING_STARTED/QUICKSTART.md) — `python -m etlantic init` → validate → run
    3. [First Pipeline](01_GETTING_STARTED/FIRST_PIPELINE.md) — evolve the generated project
    4. [Engine selection](01_GETTING_STARTED/ENGINE_SELECTION.md) — then an engine tutorial

    That is the whole first-hour path. Optional later:
    [Programmatic authoring](05_PIPELINES/PROGRAMMATIC_AUTHORING.md),
    [Capabilities](01_GETTING_STARTED/CAPABILITIES.md),
    [Compare](01_GETTING_STARTED/COMPARE.md).
    Pages marked **Future design** are not APIs.

## Project status

**ETLantic 0.27.0** is a **Beta** release for documented single-tenant pilots.
Install with `pip install 'etlantic==0.27.0'`.

- **Use today:** single-tenant pilots and reference deployments (see
  [Capabilities](01_GETTING_STARTED/CAPABILITIES.md)).
- **Not included:** multi-tenant control plane, managed Spark, SLA, unrestricted
  enterprise compliance beyond shipped SBOM/attestations.
- **Experimental:** Structured Streaming; `etlantic-datafusion` (Gate B stub).

## Minimal working example

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install 'etlantic==0.27.0'
mkdir my-pipeline && cd my-pipeline
python -m etlantic init --with-toml
python -m etlantic validate pipeline.py:SamplePipeline --profile development
python -m etlantic run pipeline.py:SamplePipeline --profile development
cat data/out.json
```

You should see `succeeded` and Ada/Grace sample rows (identity transform).
Next: [First Pipeline](01_GETTING_STARTED/FIRST_PIPELINE.md).

!!! note "PyPI vs clone"
    **PyPI users:** stay on Installation → Quickstart → First Pipeline. The
    wheel does **not** include `examples/`.
    **Contributors / clone users:** after `uv sync`, optional demos live under
    [`examples/`](https://github.com/eddiethedean/etlantic/tree/main/examples)
    (see [examples/README](https://github.com/eddiethedean/etlantic/blob/main/examples/README.md)).

## After first success

| Goal | Start here |
|---|---|
| Understand the model | [Architecture](02_FOUNDATIONS/ARCHITECTURE.md), [Manifesto](ETLANTIC_MANIFESTO.md) |
| Author without classes | [Programmatic authoring](05_PIPELINES/PROGRAMMATIC_AUTHORING.md) |
| Evaluate for a pilot | [Evaluator brief](01_GETTING_STARTED/EVALUATOR.md) |
| Contribute | [Contributing](11_DEVELOPMENT/CONTRIBUTING.md) |
