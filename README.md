<p align="center">
  <img
    src="https://raw.githubusercontent.com/eddiethedean/etlantic/main/docs/theme/assets/etlantic-logo.svg"
    width="148"
    alt="ETLantic logo"
  >
</p>

<h1 align="center">ETLantic</h1>

<p align="center">
  <strong>One typed pipeline model. Many execution backends.</strong><br>
  Typed contracts. Deterministic plans. Pluggable execution.
</p>

<p align="center">
  <a href="https://github.com/eddiethedean/etlantic/actions/workflows/ci.yml"><img src="https://github.com/eddiethedean/etlantic/actions/workflows/ci.yml/badge.svg" alt="CI status"></a>
  <a href="https://pypi.org/project/etlantic/"><img src="https://img.shields.io/pypi/v/etlantic.svg" alt="PyPI version"></a>
  <a href="https://pypi.org/project/etlantic/"><img src="https://img.shields.io/pypi/pyversions/etlantic.svg" alt="Supported Python versions"></a>
  <img src="https://img.shields.io/badge/status-beta-d6a84b.svg" alt="Project status: beta">
  <a href="https://github.com/eddiethedean/etlantic/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-0f766e.svg" alt="MIT license"></a>
</p>

<p align="center">
  <a href="https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/QUICKSTART/">Quickstart</a> ·
  <a href="https://etlantic.readthedocs.io/">Documentation</a> ·
  <a href="https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/COMPARE/">Is ETLantic for me?</a> ·
  <a href="https://etlantic.readthedocs.io/en/latest/10_REFERENCE/API_REFERENCE/">Python API</a> ·
  <a href="https://etlantic.readthedocs.io/en/latest/10_REFERENCE/CLI/">CLI</a>
</p>

---

ETLantic gives Python data pipelines one portable, typed logical model. It
coordinates contracts, transformations, and topology without replacing the
tools that execute them. Before execution reaches a write, ETLantic checks
wiring, contract compatibility, backend capabilities, and plugin trust, then
produces a deterministic plan for local engines, backend plugins, or external
orchestrators.

It is not a dataframe engine, warehouse transformation system, or scheduler.
ETLantic coordinates those tools through one typed logical model.

```text
Python types + pipeline topology
              │
              ▼
      validate before write
              │
              ▼
   deterministic, secret-free plan
              │
       ┌──────┼────────┐
       ▼      ▼        ▼
      run   compile  generate
```

## Five-minute quickstart

ETLantic requires Python 3.11 or newer. Create and activate a virtual
environment outside the project that ETLantic will generate.

macOS or Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Then install ETLantic and initialize a fresh project directory:

```bash
python -m pip install --upgrade pip
python -m pip install 'etlantic==0.35.0'
python -m etlantic --version

mkdir my-pipeline
cd my-pipeline
python -m etlantic init --with-toml
python -m etlantic validate pipeline.py:SamplePipeline --profile development
python -m etlantic run pipeline.py:SamplePipeline --profile development
```

Inspect the result:

```bash
cat data/out.json
```

Or, in PowerShell:

```powershell
Get-Content data\out.json
```

You should see a `succeeded` run and two JSON rows for Ada and Grace.

| Command | What it proves |
|---|---|
| `init` | Creates an import-safe pipeline, profile, sample data, and workspace |
| `validate` | Checks topology, contracts, capabilities, configuration, and trust without running transforms |
| `run` | Validates, plans, executes, and records a structured run report |

Continue with the full
[Quickstart](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/QUICKSTART/)
to see ETLantic reject an incompatible contract before a write, then build
[your first transformation](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/FIRST_PIPELINE/).

## Why teams use ETLantic

- **Fail before side effects.** Catch invalid graph wiring, incompatible
  contracts, missing engine capabilities, and plugin-trust failures before
  publication.
- **Review what will run.** Produce deterministic plans that can be inspected,
  fingerprinted, diffed, and retained as build evidence.
- **Keep contracts at every boundary.** Apply the same typed expectations to
  extracted inputs, transformation outputs, engine transitions, and loads.
- **Separate intent from execution.** Keep one logical pipeline while plugins
  own Polars, Pandas, SQL, and PySpark execution or Airflow compilation.
- **Adopt incrementally.** Start with local Python and JSON files, then install
  only the engines and integrations you need.
- **Automate enforcement.** Emit human, JSON, or SARIF diagnostics for local
  development and CI.

Cross-engine execution is explicit rather than magical: each transformation
needs either an implementation for the selected backend or a portable
transformation supported by that backend's compiler.

## Where ETLantic fits

| If your primary need is… | Start with… | Add ETLantic when you need… |
|---|---|---|
| Warehouse-only SQL transformation | dbt | Typed Python pipelines across additional engines |
| Durable scheduling and operations | Airflow, Dagster, or Prefect | Contract validation and deterministic plans before orchestration |
| Dataframe or table validation | Pandera or Great Expectations | Pipeline topology, capability, and publication-boundary validation |
| Typed multi-engine pipeline coordination | ETLantic | A validation-first logical model with pluggable execution |

Read the full
[comparison guide](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/COMPARE/)
before adopting ETLantic as a replacement for an existing tool. It is usually
a complementary control layer.

## Choose an execution path

Core installs without dataframe engines, database drivers, Spark, Airflow, or
Prefect. Add only what the pipeline uses. The middle column describes the
capability shipped in 0.35, not future roadmap intent.

| Capability | 0.35 | Install |
|---|---|---|
| Local Python + JSON/CSV | Built-in first-success and test path | `pip install etlantic` |
| Polars | Eager/lazy dataframe execution and portable compilation | `pip install 'etlantic[polars]'` |
| Pandas | Eager dataframe execution and portable compilation | `pip install 'etlantic[pandas]'` |
| SQL | SQLite evaluation path and PostgreSQL reference execution | `pip install 'etlantic[sql]'` |
| PySpark | Batch Spark execution; requires a compatible JVM | `pip install 'etlantic[pyspark]'` |
| Airflow | Compile plans to DAG modules; Apache Airflow is installed separately | `pip install 'etlantic[airflow]'` |
| Prefect | Local direct-execution scheduler integration | `pip install 'etlantic[prefect]'` |
| OS keyring | Runtime secret-provider integration | `pip install 'etlantic[keyring]'` |
| SQLModel | SQLModel-to-contract bridge helpers | `pip install 'etlantic[sqlmodel]'` |
| OpenTelemetry | Observability API integration | `pip install 'etlantic[observability]'` |
| Medallion pipelines | Bronze/silver/gold facade outside ETLantic core | `pip install medallantic` |

For controlled deployments, pin core and every official plugin to the same
tested release. See
[engine selection](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/ENGINE_SELECTION/),
[compatibility](https://etlantic.readthedocs.io/en/latest/10_REFERENCE/COMPATIBILITY/),
and
[optional packages](https://etlantic.readthedocs.io/en/latest/10_REFERENCE/OPTIONAL_PACKAGES/).

Structured Streaming and `etlantic-datafusion` are experimental. The FastAPI
package is a thin reference adapter, not a production control plane.

## The authoring model

ETLantic pipelines have four public building blocks:

| Building block | Responsibility |
|---|---|
| `Data` | Typed dataset contract |
| `Transformation` | Typed inputs, outputs, parameters, and implementations |
| `Extract` / `Load` | External read and publication boundaries |
| `Pipeline` | Declarative topology with `validate`, `plan`, and `run` |

Application code should prefer the curated facade:

```python
import etlantic as etl
```

Pipelines can be authored as typed classes or with functional builders and
versioned `PipelineDefinition` JSON. Start with the generated project above;
then use the
[SDK tutorial](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/SDK_10_MINUTES/)
or
[programmatic authoring guide](https://etlantic.readthedocs.io/en/latest/05_PIPELINES/PROGRAMMATIC_AUTHORING/).

## Contracts as build artifacts

Generate a reviewable contract bundle only after the pipeline validates:

```bash
python -m etlantic validate pipeline.py:SamplePipeline --format json
python -m etlantic generate pipeline.py:SamplePipeline -o contracts/
```

```text
contracts/
├── data/              # data contracts
├── transformations/   # transformation contracts
└── pipelines/         # pipeline topology contract
```

ETLantic integrates with the
[Open Data Contract Standard (ODCS)](https://etlantic.readthedocs.io/en/latest/03_DATA_CONTRACTS/ODCS/),
[Data Transformation Contract Standard (DTCS)](https://etlantic.readthedocs.io/en/latest/04_TRANSFORMATIONS/DTCS/),
and
[Data Pipeline Contract Standard (DPCS)](https://etlantic.readthedocs.io/en/latest/05_PIPELINES/DPCS/).
Generation is deterministic and refuses invalid pipelines.

## Security and production posture

ETLantic is currently **Beta**. It is suitable for documented, controlled,
single-tenant pilots—not unrestricted enterprise production.

| Boundary | Current posture |
|---|---|
| Plans and reports | Carry secret references, never resolved secret values |
| Production plugin trust | `security_mode="production"` requires an explicit non-empty `plugin_allowlist` |
| Plugin isolation | Allowlists control selection; they are not a sandbox |
| Schema history | Stores fingerprints and metadata, never source rows |
| Deployment | Application-owned process, storage, network, recovery, and isolation controls |
| Not included | Managed runtime, multi-tenant control plane, formal SLA, or compliance certification |

Use separate processes or stronger infrastructure boundaries for distinct
tenants and trust domains. Before a pilot, review:

- [Capabilities and limitations](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/CAPABILITIES/)
- [Production readiness](https://etlantic.readthedocs.io/en/latest/06_EXECUTION/PRODUCTION_READINESS/)
- [Security model](https://etlantic.readthedocs.io/en/latest/02_FOUNDATIONS/SECURITY/)
- [Enterprise evaluation guide](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/ENTERPRISE_EVALUATION/)
- [Planned multi-tenant control-plane program](https://etlantic.readthedocs.io/en/latest/11_DEVELOPMENT/MULTI_TENANT_CONTROL_PLANE_PLAN/)
- [Security reporting policy](https://github.com/eddiethedean/etlantic/blob/main/SECURITY.md)

## Common workflows

```bash
# Inspect the logical graph
python -m etlantic inspect pipeline.py:SamplePipeline --format json

# Resolve a deterministic plan
python -m etlantic plan pipeline.py:SamplePipeline \
  --profile development --format json

# Emit SARIF for CI
python -m etlantic validate pipeline.py:SamplePipeline \
  --profile development --format sarif

# Compile through the optional Airflow package
python -m etlantic compile pipeline.py:SamplePipeline \
  --profile development --target airflow -o dags/

# Inspect durable run reports
python -m etlantic report list
```

The public CLI also includes `doctor`, `profile`, `diff`, `plugin`, `schema`,
`reliability`, and `viz`. See the
[CLI reference](https://etlantic.readthedocs.io/en/latest/10_REFERENCE/CLI/)
for exit codes and mutation behavior.

## Documentation

| Goal | Start here |
|---|---|
| Get a first success | [Quickstart](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/QUICKSTART/) |
| Decide whether ETLantic fits | [Compare](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/COMPARE/) |
| Choose an engine | [Engine selection](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/ENGINE_SELECTION/) |
| Learn the architecture | [Architecture](https://etlantic.readthedocs.io/en/latest/02_FOUNDATIONS/ARCHITECTURE/) |
| Use the Python SDK | [API reference](https://etlantic.readthedocs.io/en/latest/10_REFERENCE/API_REFERENCE/) |
| Operate a controlled pilot | [Production readiness](https://etlantic.readthedocs.io/en/latest/06_EXECUTION/PRODUCTION_READINESS/) |
| Review future direction | [Planning Hub](https://etlantic.readthedocs.io/en/latest/11_DEVELOPMENT/PLAN_INDEX/) |
| Build a plugin | [Plugin SDK](https://etlantic.readthedocs.io/en/latest/07_PLUGIN_SDK/) |
| Troubleshoot a failure | [Troubleshooting](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/TROUBLESHOOTING/) |
| Upgrade safely | [Upgrade hub](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/UPGRADE/) |

Repository examples require a clone and are not included in the wheel. Pip
users should begin with `etlantic init`; contributors can use
[`examples/`](https://github.com/eddiethedean/etlantic/tree/main/examples)
after `uv sync --locked`.

## Contributing and support

Contributions are welcome. Start with
[CONTRIBUTING.md](https://github.com/eddiethedean/etlantic/blob/main/CONTRIBUTING.md)
for setup, test scopes, documentation checks, and pull-request expectations.

- Usage questions and bug reports:
  [GitHub Issues](https://github.com/eddiethedean/etlantic/issues)
- Vulnerabilities:
  [private reporting instructions](https://github.com/eddiethedean/etlantic/blob/main/SECURITY.md)
- Release history:
  [CHANGELOG.md](https://github.com/eddiethedean/etlantic/blob/main/CHANGELOG.md)
- Project governance:
  [GOVERNANCE.md](https://github.com/eddiethedean/etlantic/blob/main/GOVERNANCE.md)

ETLantic is available under the [MIT License](https://github.com/eddiethedean/etlantic/blob/main/LICENSE).
