---
hide:
  - toc
status: available
since: "0.45.0"
current_minor: "0.45"
audience: adopter
---

<div class="etlantic-hero">
  <div class="etlantic-hero__content">
    <span class="etlantic-hero__eyebrow">ETLantic 0.45 · Beta</span>
    <h1>One typed pipeline model. Many execution backends.</h1>
    <p>Define contracts and topology in Python, validate them before execution,
    then produce deterministic plans for local engines, backend plugins, or
    external orchestrators.</p>
    <div class="etlantic-hero__actions">
      <a class="md-button md-button--primary" href="01_GETTING_STARTED/QUICKSTART/">Run the quickstart</a>
      <a class="md-button" href="01_GETTING_STARTED/COMPARE/">Evaluate ETLantic</a>
      <a class="md-button" href="10_REFERENCE/API_REFERENCE/">Browse the API</a>
    </div>
    <div class="etlantic-hero__meta" aria-label="Project metadata">
      <span>Python 3.11+</span>
      <span>MIT licensed</span>
      <span>Typed</span>
    </div>
  </div>
  <div class="etlantic-flow" aria-label="ETLantic validation workflow">
    <div class="etlantic-flow__header">
      <img src="theme/assets/etlantic-logo.svg" alt="">
      <span>Pipeline gate</span>
    </div>
    <a class="etlantic-flow__step"
       href="05_PIPELINES/PIPELINE/"
       aria-label="Model: learn about pipeline types and topology">
      <span class="etlantic-flow__number">01</span>
      <span><strong>Model</strong><small>Types + topology</small></span>
    </a>
    <div class="etlantic-flow__connector" aria-hidden="true"></div>
    <a class="etlantic-flow__step"
       href="02_FOUNDATIONS/VALIDATION_EVERYWHERE/"
       aria-label="Validate: learn about contracts and trust checks">
      <span class="etlantic-flow__number">02</span>
      <span><strong>Validate</strong><small>Contracts + trust</small></span>
    </a>
    <div class="etlantic-flow__connector" aria-hidden="true"></div>
    <a class="etlantic-flow__step etlantic-flow__step--accent"
       href="05_PIPELINES/PLANNING/"
       aria-label="Resolve: learn how ETLantic plans runs, compilation, and generation">
      <span class="etlantic-flow__number">03</span>
      <span><strong>Resolve</strong><small>Run · compile · generate</small></span>
    </a>
  </div>
</div>

<div class="etlantic-definition">
  <strong>ETLantic gives Python data pipelines one portable, typed logical model.</strong>
  <span>Validate-before-write is the safety gate; deterministic planning and
  pluggable execution carry that model into dataframe engines and orchestrators.
  Cross-engine execution remains explicit.</span>
</div>

## Choose your path

> **Status: Available in ETLantic 0.45.0.**


<div class="etlantic-path-grid">
  <a class="etlantic-path-card" href="01_GETTING_STARTED/QUICKSTART/">
    <span class="etlantic-path-card__kicker">Build</span>
    <strong>Get a first success</strong>
    <span>Install, scaffold, validate, and run the file-backed sample.</span>
    <span class="etlantic-path-card__action">Start the quickstart →</span>
  </a>
  <a class="etlantic-path-card" href="01_GETTING_STARTED/EVALUATOR/">
    <span class="etlantic-path-card__kicker">Evaluate</span>
    <strong>Decide whether it fits</strong>
    <span>Review capabilities, limitations, alternatives, and pilot criteria.</span>
    <span class="etlantic-path-card__action">Open the evaluator brief →</span>
  </a>
  <a class="etlantic-path-card" href="06_EXECUTION/PRODUCTION_READINESS/">
    <span class="etlantic-path-card__kicker">Operate</span>
    <strong>Prepare a controlled pilot</strong>
    <span>Define trust, secrets, deployment, reports, and recovery boundaries.</span>
    <span class="etlantic-path-card__action">Review production readiness →</span>
  </a>
  <a class="etlantic-path-card" href="07_PLUGIN_SDK/">
    <span class="etlantic-path-card__kicker">Extend</span>
    <strong>Build a plugin</strong>
    <span>Implement public protocols and verify behavior with conformance suites.</span>
    <span class="etlantic-path-card__action">Explore the Plugin SDK →</span>
  </a>
</div>

## Green path: first success

Install from PyPI first: `pip install etlantic`. The commands below pin
`etlantic==0.45.0` so this version of the documentation and the installed API
stay aligned. The complete [Quickstart](01_GETTING_STARTED/QUICKSTART.md)
continues with an intentional validation failure after the first successful
run.

=== "macOS / Linux"

    ```bash
    python -m venv .venv
    source .venv/bin/activate
    python -m pip install --upgrade pip
    python -m pip install 'etlantic==0.45.0'
    python -m etlantic --version

    mkdir my-pipeline
    cd my-pipeline
    python -m etlantic init --with-toml
    python -m etlantic validate pipeline.py:SamplePipeline --profile development
    python -m etlantic run pipeline.py:SamplePipeline --profile development
    cat data/out.json
    ```

=== "Windows PowerShell"

    ```powershell
    py -3.11 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    python -m pip install 'etlantic==0.45.0'
    python -m etlantic --version

    mkdir my-pipeline
    cd my-pipeline
    python -m etlantic init --with-toml
    python -m etlantic validate pipeline.py:SamplePipeline --profile development
    python -m etlantic run pipeline.py:SamplePipeline --profile development
    Get-Content data\out.json
    ```

<div class="etlantic-success">
  <span class="etlantic-success__mark" aria-hidden="true">✓</span>
  <span><strong>Expected result</strong>You should see a <code>succeeded</code>
  run and two JSON rows for Ada and Grace.</span>
</div>

`init` should run in a fresh directory. `--force` can overwrite scaffolded
files, so use it only when you have reviewed the target directory.

!!! note "PyPI users and repository examples"
    The wheel does not include `examples/`. Pip users should continue to
    [First Pipeline](01_GETTING_STARTED/FIRST_PIPELINE.md), then choose a
    PyPI-ready engine tutorial. Contributors can use the repository
    [`examples/`](https://github.com/eddiethedean/etlantic/tree/main/examples)
    after `uv sync --locked`.

## Why validation-first

<div class="etlantic-benefits">
  <div class="etlantic-benefit">
    <span class="etlantic-benefit__number">01</span>
    <strong>Fail before side effects</strong>
    <span>Catch invalid wiring, incompatible contracts, unavailable
    capabilities, and plugin-trust failures before publication.</span>
  </div>
  <div class="etlantic-benefit">
    <span class="etlantic-benefit__number">02</span>
    <strong>Review what will run</strong>
    <span>Inspect, fingerprint, diff, and retain deterministic, secret-free
    plans as build evidence.</span>
  </div>
  <div class="etlantic-benefit">
    <span class="etlantic-benefit__number">03</span>
    <strong>Keep execution explicit</strong>
    <span>Use one logical model while plugins own Polars, Pandas, SQL,
    PySpark, and orchestration behavior.</span>
  </div>
</div>

## Choose an execution path

Core installs without dataframe engines, database drivers, Spark, Airflow, or
Prefect. Add only what the pipeline uses.

| Path | Install | Current scope |
|---|---|---|
| Local Python + JSON/CSV | `pip install 'etlantic==0.45.0'` | Built-in first-success and test path |
| Polars | `pip install 'etlantic[polars]==0.45.0'` | Eager/lazy execution and portable compilation |
| Pandas | `pip install 'etlantic[pandas]==0.45.0'` | Eager execution and portable compilation |
| SQL | `pip install 'etlantic[sql]==0.45.0'` | SQLite evaluation and PostgreSQL reference execution |
| PySpark | `pip install 'etlantic[pyspark]==0.45.0'` | Batch Spark execution; compatible JVM required |
| Airflow | `pip install 'etlantic[airflow]==0.45.0'` | DAG compilation; Apache Airflow installs separately |
| Prefect | `pip install 'etlantic[prefect]==0.45.0'` | Bounded local direct-execution integration |

See [Engine selection](01_GETTING_STARTED/ENGINE_SELECTION.md) for prerequisites
and [Compatibility](10_REFERENCE/COMPATIBILITY.md) before pinning a deployment.

## Know the release boundary

ETLantic 0.45 is a **Beta** release for documented, controlled, single-tenant
pilots—not unrestricted enterprise production.

<div class="etlantic-release-grid">
  <div class="etlantic-release-card etlantic-release-card--available">
    <strong>Available</strong>
    <span>Typed authoring, validation, deterministic planning, local and plugin
    execution, Airflow compilation, reports, and observability providers.</span>
  </div>
  <div class="etlantic-release-card etlantic-release-card--experimental">
    <strong>Experimental</strong>
    <span>Structured Streaming and the <code>etlantic-datafusion</code>
    package remain outside the pilot path.</span>
  </div>
  <div class="etlantic-release-card etlantic-release-card--unavailable">
    <strong>Not included</strong>
    <span>Managed runtime, multi-tenant control plane, formal SLA, or
    compliance certification.</span>
  </div>
</div>

Production profiles require a non-empty `plugin_allowlist`; allowlisting
controls selection, not process isolation. Plans and reports carry secret
references, never resolved values. Review
[Capabilities](01_GETTING_STARTED/CAPABILITIES.md),
[Security](02_FOUNDATIONS/SECURITY.md),
[Production readiness](06_EXECUTION/PRODUCTION_READINESS.md), and the
[planned multi-tenant control-plane program](11_DEVELOPMENT/MULTI_TENANT_CONTROL_PLANE_PLAN.md)
before a pilot.

## Continue by goal

| Goal | Next document |
|---|---|
| Understand the logical model | [Core concepts](02_FOUNDATIONS/CORE_CONCEPTS.md) |
| Author with the public Python facade | [Python SDK in 10 minutes](01_GETTING_STARTED/SDK_10_MINUTES.md) |
| Configure CI validation | [CI integration](06_EXECUTION/CI_INTEGRATION.md) |
| Diagnose a failure | [Troubleshooting](01_GETTING_STARTED/TROUBLESHOOTING.md) |
| Review the current release | [What's new in 0.45](01_GETTING_STARTED/WHATS_NEW_0_45.md) |
| Review future direction | [Planning Hub](11_DEVELOPMENT/PLAN_INDEX.md) |
| Contribute to ETLantic | [Contributor guide](11_DEVELOPMENT/CONTRIBUTING.md) |
