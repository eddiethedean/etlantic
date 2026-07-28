<p align="center">
  <img
    src="https://raw.githubusercontent.com/eddiethedean/etlantic/main/docs/theme/assets/etlantic-logo.svg"
    width="148"
    alt="ETLantic logo"
  >
</p>

<h1 align="center">ETLantic</h1>

<p align="center">
  <strong>Typed Python data pipelines with validate-before-write.</strong><br>
  Design once. Validate everywhere.
</p>

<p align="center">
  <a href="https://github.com/eddiethedean/etlantic/actions/workflows/ci.yml"><img src="https://github.com/eddiethedean/etlantic/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/etlantic/"><img src="https://img.shields.io/pypi/v/etlantic.svg" alt="PyPI"></a>
  <a href="https://pypi.org/project/etlantic/"><img src="https://img.shields.io/pypi/pyversions/etlantic.svg" alt="Python versions"></a>
  <a href="https://github.com/eddiethedean/etlantic/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-d6a84b.svg" alt="MIT license"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
</p>

<p align="center">
  <a href="https://etlantic.readthedocs.io/">Documentation</a> ·
  <a href="https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/QUICKSTART/">Quickstart</a> ·
  <a href="https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/CAPABILITIES/">Capabilities</a> ·
  <a href="https://etlantic.readthedocs.io/en/latest/11_DEVELOPMENT/ROADMAP_SUMMARY/">Roadmap</a>
</p>

---

ETLantic lets you define Python data pipelines as typed classes **or**
functional builders / JSON (`PipelineDefinition`), catch bad wiring and
contract mismatches **before any write**, then run or compile the same
pipeline on local Python, Polars, Pandas, SQL, or Spark—and emit Airflow
DAGs when you need them.

It is **not** a warehouse tool (use dbt), **not** a scheduler (use Airflow,
Dagster, or Prefect), and **not** a dataframe engine. It is a typed pipeline
framework that coordinates the tools you already choose.

```text
Typed contracts ──▶ Validation ──▶ Deterministic plan ──▶ Run or compile
```

## Why ETLantic?

- Catch invalid wiring, incompatible contracts, missing capabilities, and
  untrusted plugins before a write.
- Validate extracted inputs, transformation outputs, engine transitions, and
  publication boundaries against the same contracts.
- Keep one logical pipeline across local Python, Polars, Pandas, SQL, and
  PySpark; compile to Airflow DAGs; run under Prefect where the local MVP
  applies.
- Review deterministic, secret-free plans and preserve structured diagnostics,
  lineage, schema observations, and run reports.
- Install a small core and add only the engines you need.

## Quickstart

Requires Python 3.11 or newer. Use an empty directory for `init` (or pass
`--force`). On Windows PowerShell, activate with
`.\.venv\Scripts\Activate.ps1` and prefer `py -3.11 -m …` (see
[Installation](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/INSTALLATION/)).

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install 'etlantic==0.28.0'
python -m etlantic --version

mkdir my-pipeline && cd my-pipeline
python -m etlantic init --with-toml
python -m etlantic validate pipeline.py:SamplePipeline --profile development
python -m etlantic run pipeline.py:SamplePipeline --profile development
cat data/out.json
```

You should see run status `succeeded` and JSON rows for Ada and Grace (identity
transform on the sample). That proves plumbing—next, change the transform in
[First Pipeline](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/FIRST_PIPELINE/).

The CLI defaults to `development` when `--profile` is omitted (or your project's
`default_profile`). Prefer an explicit profile in scripts and CI.

Full walkthrough: [Quickstart](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/QUICKSTART/).

> **After first success (clone only):** repository demos under `examples/`
> (for example
> [`memory_customers.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/memory_customers.py))
> require a git checkout — they are **not** in the PyPI wheel.

> **Status:** ETLantic **0.28.0** is a **Beta** (PyPI) release suitable for
> documented single-tenant pilots—not unrestricted enterprise production.
> Structured Streaming remains experimental. See
> [Capabilities](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/CAPABILITIES/)
> and [Production readiness](https://etlantic.readthedocs.io/en/latest/06_EXECUTION/PRODUCTION_READINESS/).

## Engines and integrations

| Integration | Install | Role |
|---|---|---|
| Polars | `etlantic-polars` | Eager/lazy dataframe execution and portable compilation |
| Pandas | `etlantic-pandas` | Eager dataframe execution and portable compilation |
| SQL | `etlantic-sql` | Parameterized relational execution and portable SQL compilation |
| PySpark | `etlantic-pyspark` | Spark execution and portable compilation |
| Airflow | `etlantic-airflow` | Compile plans into DAG artifacts (does not install Airflow) |
| Prefect | `etlantic-prefect` | Direct-execution local MVP (deployment/serve remain future) |
| Keyring | `etlantic-keyring` | OS keyring secret provider |
| SQLModel | `etlantic-sqlmodel` | SQLModel bridge helpers |
| Medallantic | `medallantic` | Engine-agnostic medallion facade (bronze/silver/gold stay out of core) |
| DataFusion | `etlantic-datafusion` | Experimental query engine stub (Gate B) |
| FastAPI | `etlantic-fastapi` | Thin 0.28 authoring/service **reference** adapter (not the 1.1 control plane) |

See [Optional packages](https://etlantic.readthedocs.io/en/latest/10_REFERENCE/OPTIONAL_PACKAGES/)
for observability (`otel` / `observability` extras) and Arrow helpers.

Matching extras such as `etlantic[polars]` are equivalent. Pin matching minors
while ETLantic is pre-1.0.

## Architecture

ETLantic keeps logical meaning separate from physical execution:

```text
Data + Transformation + Pipeline contracts
                              │
                       validate and plan
                              ▼
                    secret-free PipelinePlan
                              │
                  ┌───────────┼───────────┐
                  ▼           ▼           ▼
               execute      compile     generate
                  │           │           │
                  └──── plugins and external systems
```

Plans and reports contain secret references, never resolved secret values.
Production profiles require explicit plugin allowlists. Backend optimizations
may change the physical graph but must preserve contracts, validation
boundaries, security domains, and logical attribution.

Contract standards (ODCS / DTCS / DPCS) and the validation envelope are covered
in the [Architecture](https://etlantic.readthedocs.io/en/latest/02_FOUNDATIONS/ARCHITECTURE/)
and [Validation Everywhere](https://etlantic.readthedocs.io/en/latest/02_FOUNDATIONS/VALIDATION_EVERYWHERE/)
guides.

## Capability boundary

| Capability | 0.28 |
|---|---|
| Cohesive CLI (`init`, `doctor`, durable reports) | Available |
| Typed contracts, graph validation, deterministic planning | Available |
| Local, Polars, Pandas, SQL, and PySpark execution paths | Available |
| Portable compilers for Polars, Pandas, SQL, and PySpark | Available |
| ODCS, DTCS, DPCS, schema drift, lineage, reports, and SARIF | Available |
| Airflow compilation (compile-only) and Prefect local MVP | Available (bounded) |
| Versioned Polars↔Pandas tabular interchange | Available |
| Contract and configuration freeze (deep plans, security_mode) | Available |
| Trust, isolation, safe I/O, SBOM/attestations (single-tenant reference) | Available (bounded) |
| Structured Streaming | Experimental |
| `etlantic-datafusion` | Experimental |
| Full multi-tenant control plane / SLA / unrestricted enterprise | Not included |

See the full [Capabilities](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/CAPABILITIES/)
guide for precise guarantees and limitations.

Release notes:
[What's New in 0.25](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/WHATS_NEW_0_25/).

## Learn more

[Installation](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/INSTALLATION/)
· [Quickstart](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/QUICKSTART/)
· [Engine selection](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/ENGINE_SELECTION/)
· [Compare](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/COMPARE/)
· [Security](https://etlantic.readthedocs.io/en/latest/02_FOUNDATIONS/SECURITY/)
· [Roadmap](https://etlantic.readthedocs.io/en/latest/11_DEVELOPMENT/ROADMAP_SUMMARY/)
· [Contributing](https://github.com/eddiethedean/etlantic/blob/main/CONTRIBUTING.md)

MIT licensed.
