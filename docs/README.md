<div class="etlantic-hero">
  <div class="etlantic-hero__content">
    <span class="etlantic-hero__eyebrow">Typed Python data pipelines</span>
    <h1>Validate before write.<br><span class="etlantic-hero__nowrap">Run where your engines are.</span></h1>
    <p>Define pipelines as typed classes, catch bad wiring before any write, then
    run or compile on Polars, Pandas, SQL, Spark, or Airflow.</p>
    <div class="etlantic-hero__actions">
      <a class="md-button md-button--primary" href="01_GETTING_STARTED/QUICKSTART/">Quickstart</a>
      <a class="md-button" href="01_GETTING_STARTED/COMPARE/">Is this for me?</a>
      <a class="md-button" href="01_GETTING_STARTED/INSTALLATION/">Installation</a>
    </div>
  </div>
</div>

ETLantic is a Python framework for defining typed, contract-driven data
pipelines and coordinating their execution through the tools you already
choose. It is **not** a warehouse tool, scheduler, or dataframe engine.

!!! tip "Green path (start here only)"
    1. [Installation](01_GETTING_STARTED/INSTALLATION.md) — install **0.34.0**
       (from `main` until the wheel is on PyPI; see that page)
    2. [Quickstart](01_GETTING_STARTED/QUICKSTART.md) — `python -m etlantic init` → validate → run
    3. [First Pipeline](01_GETTING_STARTED/FIRST_PIPELINE.md) — evolve the generated project
    4. [Engine selection](01_GETTING_STARTED/ENGINE_SELECTION.md) — then a
       **PyPI** Polars/Pandas tutorial or the
       [SQL hello](06_EXECUTION/SQL_HELLO_PYPI.md); deeper SQL and PySpark
       tutorials are clone-assisted
    5. [Learning path](01_GETTING_STARTED/LEARNING_PATH.md) — week-by-week after first success

    That is the whole first-hour path. Optional later:
    [Programmatic authoring](05_PIPELINES/PROGRAMMATIC_AUTHORING.md),
    [SDK 10 minutes](01_GETTING_STARTED/SDK_10_MINUTES.md) (after Ada/Grace).
    Ignore Maintainers / Standards nav until you contribute.
    Pages marked **Future design** are not APIs.

### What you get in 0.34 (short)

- Typed contracts + validate-before-write + deterministic plans
- Local / Polars / Pandas / SQL / PySpark execution; Airflow compile; Prefect local MVP
- Observability providers, run history, and event consumers (M6 pilot slice)
- Fail-closed production trust via `plugin_allowlist` (not the profile name alone)

Full matrix: [Capabilities](01_GETTING_STARTED/CAPABILITIES.md).
Fit check: [Compare](01_GETTING_STARTED/COMPARE.md).

## Project status

**ETLantic 0.34.0** is a **Beta** release for documented single-tenant pilots.
Until the `0.34.0` wheel is on PyPI (latest published may still be **0.33.0**),
install from `main` as shown in
[Installation](01_GETTING_STARTED/INSTALLATION.md).

- **Available:** typed authoring, validate/plan/run, Polars/Pandas/SQL/PySpark
  plugins, Airflow compile, Prefect local MVP, observability / run history (M6).
- **Experimental:** Structured Streaming; `etlantic-datafusion` stub.
- **Not in 0.34:** multi-tenant control plane, formal SLA, unrestricted
  enterprise production. Roadmap detail lives under
  [Evaluate](01_GETTING_STARTED/EVALUATOR.md) / Contribute → Maintainers
  (e.g. [multi-tenant control-plane plan](11_DEVELOPMENT/MULTI_TENANT_CONTROL_PLANE_PLAN.md)).

The milestone name “production readiness” for M6 means the observability/history
*pilot* slice shipped—not unrestricted enterprise production. See
[Production readiness](06_EXECUTION/PRODUCTION_READINESS.md) and CHANGELOG
`[Unreleased]` for post-cut hardening.

## Minimal working example

=== "Unix / macOS"

    ```bash
    python -m venv .venv && source .venv/bin/activate
    python -m pip install --upgrade pip
    # Until 0.34.0 is on PyPI:
    python -m pip install 'git+https://github.com/eddiethedean/etlantic.git@main'
    # After publish: python -m pip install 'etlantic==0.34.0'
    python -m etlantic --version
    mkdir my-pipeline && cd my-pipeline
    python -m etlantic init --with-toml
    python -m etlantic validate pipeline.py:SamplePipeline --profile development
    python -m etlantic run pipeline.py:SamplePipeline --profile development
    cat data/out.json
    ```

=== "Windows (PowerShell)"

    ```powershell
    py -3.11 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    # Until 0.34.0 is on PyPI:
    python -m pip install 'git+https://github.com/eddiethedean/etlantic.git@main'
    # After publish: python -m pip install 'etlantic==0.34.0'
    python -m etlantic --version
    mkdir my-pipeline; cd my-pipeline
    python -m etlantic init --with-toml
    python -m etlantic validate pipeline.py:SamplePipeline --profile development
    python -m etlantic run pipeline.py:SamplePipeline --profile development
    Get-Content data\out.json
    ```

You should see `succeeded` and Ada/Grace sample rows (identity transform).
`init` requires an **empty directory** (or pass `--force` — it can overwrite
scaffolded files). Next: [First Pipeline](01_GETTING_STARTED/FIRST_PIPELINE.md).

!!! note "PyPI vs clone"
    **PyPI / pip users:** Installation → Quickstart → First Pipeline → Polars/Pandas
    tutorials (PyPI path). The wheel does **not** include `examples/`.
    **Contributors / clone users:** after `uv sync`, optional demos live under
    [`examples/`](https://github.com/eddiethedean/etlantic/tree/main/examples)
    (see [examples/README](https://github.com/eddiethedean/etlantic/blob/main/examples/README.md)).
    The SQL hello is PyPI-ready; deeper SQL and PySpark tutorials are
    clone-assisted.

## After first success

| Goal | Start here |
|---|---|
| Understand the model | [Architecture](02_FOUNDATIONS/ARCHITECTURE.md), [Manifesto](ETLANTIC_MANIFESTO.md) |
| Author without classes | [Programmatic authoring](05_PIPELINES/PROGRAMMATIC_AUTHORING.md) |
| SDK sketch | [SDK 10 minutes](01_GETTING_STARTED/SDK_10_MINUTES.md) |
| Evaluate for a pilot | [Evaluator brief](01_GETTING_STARTED/EVALUATOR.md) |
| Contribute | [Contributing](11_DEVELOPMENT/CONTRIBUTING.md) |
