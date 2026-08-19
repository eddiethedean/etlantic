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
  <a href="https://etlantic.readthedocs.io/en/stable/01_GETTING_STARTED/QUICKSTART/">Quickstart</a> ·
  <a href="https://etlantic.readthedocs.io/en/stable/">Documentation</a> ·
  <a href="https://etlantic.readthedocs.io/en/stable/01_GETTING_STARTED/COMPARE/">Is ETLantic for me?</a> ·
  <a href="https://etlantic.readthedocs.io/en/stable/10_REFERENCE/API_REFERENCE/">Python API</a> ·
  <a href="https://etlantic.readthedocs.io/en/stable/10_REFERENCE/CLI/">CLI</a>
</p>

---

ETLantic is a Python library for **defining** data pipelines as typed
contracts and graphs, **validating** them before they run, and **producing a
deterministic plan** that a plugin executes (local Python, Polars, Pandas,
SQL, or Spark) or an orchestrator compiles (Airflow). It is not dbt, not a
dataframe engine, and not a hosted scheduler.

## Quickstart

ETLantic requires Python 3.11 or newer. In an activated virtual environment:

```bash
python -m pip install 'etlantic==0.48.0'
python -m etlantic --version
mkdir my-pipeline
cd my-pipeline
python -m etlantic init --with-toml
python -m etlantic validate pipeline.py:SamplePipeline --profile development
python -m etlantic run pipeline.py:SamplePipeline --profile development
```

The run should succeed and write Ada and Grace to `data/out.json`. See the
[full Quickstart](https://etlantic.readthedocs.io/en/stable/01_GETTING_STARTED/QUICKSTART/)
for setup details and expected output.

If `init` refuses the directory, use an empty folder (or `--force` only after
you have reviewed what it overwrites). Pin every official plugin to the same
version as core (`etlantic-polars==0.48.0` with `etlantic==0.48.0`). Mixed
plugin versions fail closed — see
[Troubleshooting](https://etlantic.readthedocs.io/en/stable/01_GETTING_STARTED/TROUBLESHOOTING/#core-and-plugin-versions-do-not-match).

## What it provides

- Typed `Data`, `Transformation`, `Extract`, `Load`, and `Pipeline` building
  blocks.
- Validation before execution or publication, with human, JSON, and SARIF
  diagnostics.
- Deterministic plans that can be inspected, fingerprinted, diffed, run, or
  compiled.
- Contract generation for
  [ODCS](https://etlantic.readthedocs.io/en/stable/03_DATA_CONTRACTS/ODCS/),
  [DTCS](https://etlantic.readthedocs.io/en/stable/04_TRANSFORMATIONS/DTCS/),
  and [DPCS](https://etlantic.readthedocs.io/en/stable/05_PIPELINES/DPCS/)
  artifacts.
- Pluggable execution across local Python, Polars, Pandas, SQL, and PySpark,
  plus orchestration integrations.

Application code should use the curated public facade:

```python
import etlantic as etl
```

The public CLI (see the
[CLI reference](https://etlantic.readthedocs.io/en/stable/10_REFERENCE/CLI/)):

- Authoring: `init`, `doctor`, `validate`, `inspect`, `plan`, `profile`, `run`,
  `compile`, `generate`, `diff`
- Ops: `plugin`, `schema`, `reliability`, `erasure`, `viz`, `report`, `watch`,
  `stream`, `schedule`, `scheduler`, `worker`
- Agents: `context`, `proposal`

## Execution options

Core has no dataframe, database, Spark, or orchestrator dependency. Install
only the integrations a pipeline needs:

| Capability | 0.48 |
|---|---|
| Local Python + JSON/CSV | `etlantic` |
| Polars or Pandas | `etlantic[polars]` or `etlantic[pandas]` |
| SQL or PySpark | `etlantic[sql]` or `etlantic[pyspark]` |
| Airflow or Prefect | `etlantic[airflow]` or `etlantic[prefect]` |

Each transformation must support the selected backend. In controlled
deployments, pin ETLantic and official plugins to the same release. See
[engine selection](https://etlantic.readthedocs.io/en/stable/01_GETTING_STARTED/ENGINE_SELECTION/)
and
[compatibility](https://etlantic.readthedocs.io/en/stable/10_REFERENCE/COMPATIBILITY/).

## Security and production posture

ETLantic is **Beta**, community-supported, with no SLA. Use it for documented
single-tenant pilots. You can embed an HTTP control plane
(`etlantic-fastapi`) with **Supported** isolation profiles
(`isolated-deployment`, `dedicated-schema`). There is no hosted multi-tenant
SaaS. See
[Capabilities](https://etlantic.readthedocs.io/en/stable/01_GETTING_STARTED/CAPABILITIES/)
and the
[control-plane program](https://etlantic.readthedocs.io/en/stable/11_DEVELOPMENT/MULTI_TENANT_CONTROL_PLANE_PLAN/).

Plans and reports contain secret references, never resolved secret values.
Production profiles require an explicit non-empty `plugin_allowlist`; an
allowlist controls selection but is not a sandbox. Schema history stores
fingerprints and metadata, never source rows.

Review the
[production readiness](https://etlantic.readthedocs.io/en/stable/06_EXECUTION/PRODUCTION_READINESS/)
and
[security model](https://etlantic.readthedocs.io/en/stable/02_FOUNDATIONS/SECURITY/)
before a pilot.

## Learn more

These links use the Read the Docs **stable** alias (currently 0.48.0). The
pinned tree is also at
[v0.48.0](https://etlantic.readthedocs.io/en/v0.48.0/).

- [Quickstart](https://etlantic.readthedocs.io/en/stable/01_GETTING_STARTED/QUICKSTART/)
  and [first pipeline](https://etlantic.readthedocs.io/en/stable/01_GETTING_STARTED/FIRST_PIPELINE/)
- [Is ETLantic for me?](https://etlantic.readthedocs.io/en/stable/01_GETTING_STARTED/COMPARE/)
  and [capabilities](https://etlantic.readthedocs.io/en/stable/01_GETTING_STARTED/CAPABILITIES/)
- [CLI reference](https://etlantic.readthedocs.io/en/stable/10_REFERENCE/CLI/)
  and [Python API](https://etlantic.readthedocs.io/en/stable/10_REFERENCE/API_REFERENCE/)
- [Plugin SDK](https://etlantic.readthedocs.io/en/stable/07_PLUGIN_SDK/)
  and [optional packages](https://etlantic.readthedocs.io/en/stable/10_REFERENCE/OPTIONAL_PACKAGES/)
- [Human-governed AI](https://etlantic.readthedocs.io/en/stable/01_GETTING_STARTED/HUMAN_GOVERNED_AI/)
  and [scheduler tutorial](https://etlantic.readthedocs.io/en/stable/01_GETTING_STARTED/SCHEDULER_TUTORIAL/)

## Contributing

See [CONTRIBUTING.md](https://github.com/eddiethedean/etlantic/blob/main/CONTRIBUTING.md)
for development setup and pull-request guidance. Use
[GitHub Issues](https://github.com/eddiethedean/etlantic/issues) for bugs and
questions, and follow the private instructions in
[SECURITY.md](https://github.com/eddiethedean/etlantic/blob/main/SECURITY.md)
to report vulnerabilities.

ETLantic is available under the
[MIT License](https://github.com/eddiethedean/etlantic/blob/main/LICENSE).
