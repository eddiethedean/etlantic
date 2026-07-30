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
  <a href="https://astral.sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
</p>

<p align="center">
  <a href="https://etlantic.readthedocs.io/">Documentation</a> ·
  <a href="https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/QUICKSTART/">Quickstart</a> ·
  <a href="https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/COMPARE/">Compare</a> ·
  <a href="https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/CAPABILITIES/">Capabilities</a>
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

Not sure if ETLantic fits? Start with
[Compare](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/COMPARE/).

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

## Quickstart (start here)

**Primary path:** CLI `init` → validate → run (file-backed sample). Requires
Python 3.11+. Use an empty directory for `init` (or pass `--force`).

```bash
pip install etlantic
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
> require a git checkout — they are **not** in the PyPI wheel. Pip-only users:
> ignore `examples/` until you clone.

> **Status:** ETLantic is currently **Beta** and suitable for
> documented single-tenant pilots—not unrestricted enterprise production.
> Structured Streaming remains experimental. See
> [Capabilities](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/CAPABILITIES/)
> and [Production readiness](https://etlantic.readthedocs.io/en/latest/06_EXECUTION/PRODUCTION_READINESS/).

## Engines and integrations

| Integration | Install | Role |
|---|---|---|
| Polars | `etlantic-polars` | Eager/lazy dataframe (PyPI tutorial path) |
| Pandas | `etlantic-pandas` | Eager dataframe (PyPI tutorial path) |
| SQL | `etlantic-sql` | Relational execution; SQLite demo on PyPI; PostgreSQL for MERGE; deeper tutorials may need a clone |
| PySpark | `etlantic-pyspark` | Spark execution (needs Java; clone-assisted tutorials) |
| Airflow | `etlantic-airflow` | Compile plans into DAG artifacts (does not install Airflow) |
| Prefect | `etlantic-prefect` | Direct-execution local MVP (deployment/serve remain future) |
| Keyring | `etlantic-keyring` | OS keyring secret provider |
| SQLModel | `etlantic-sqlmodel` | SQLModel bridge helpers |
| Medallantic | `medallantic` | Medallion facade (bronze/silver/gold stay out of core) |
| DataFusion | `etlantic-datafusion` | **Experimental** stub — not for pilots |
| FastAPI | `etlantic-fastapi` | Thin authoring/service **reference** adapter |

See [Optional packages](https://etlantic.readthedocs.io/en/latest/10_REFERENCE/OPTIONAL_PACKAGES/)
for observability (`otel` / `observability` extras) and Arrow helpers.
Official engine packages share the **0.34 Beta pilot envelope** even when PyPI
classifiers say Stable—treat the docs narrative as authoritative.

Matching extras such as `etlantic[polars]` are equivalent. Pin matching minors
while ETLantic follows its 0.x roadmap.

## After Ada/Grace — SDK sketch

Once the CLI Quickstart succeeds, the same model fits in a few lines of Python
(memory-backed demo; seed data yourself):

```python
import etlantic as etl


class RawCustomer(etl.Data):
    customer_id: int
    first_name: str
    last_name: str


class Customer(etl.Data):
    customer_id: int
    full_name: str


class NormalizeCustomers(etl.Transformation):
    customers: etl.Input[RawCustomer]
    result: etl.Output[Customer]


@NormalizeCustomers.implementation("local")
def normalize(customers: list[RawCustomer]) -> list[Customer]:
    return [
        Customer(
            customer_id=row.customer_id,
            full_name=f"{row.first_name} {row.last_name}",
        )
        for row in customers
    ]


class CustomerPipeline(etl.Pipeline):
    raw: etl.Extract[RawCustomer] = etl.Extract(asset="customers")
    normalized = NormalizeCustomers.step(customers=raw)
    output: etl.Load[Customer] = etl.Load(
        input=normalized.result,
        asset="normalized_customers",
    )


profile = etl.Profile(
    name="demo",
    assets={"customers": "memory", "normalized_customers": "memory"},
)
runtime = etl.PipelineRuntime()
runtime.memory.seed(
    "customers",
    [RawCustomer(customer_id=1, first_name="Ada", last_name="Lovelace")],
)

CustomerPipeline.validate(profile=profile).raise_for_errors()
plan = CustomerPipeline.plan(profile=profile)
run = CustomerPipeline.run(profile=profile, runtime=runtime)
```

Longer SDK walkthrough:
[SDK 10 minutes](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/SDK_10_MINUTES/)
(after CLI first success).

## Contract artifacts

Your Python types are also portable, reviewable contract artifacts. Generate
the complete bundle from a valid pipeline:

```bash
python -m etlantic generate pipeline.py:SamplePipeline -o contracts/
```

```text
contracts/
├── data/              # ODCS data contracts
├── transformations/   # DTCS transformation contracts
└── pipelines/         # DPCS pipeline contract
```

| Artifact | Captures |
|---|---|
| [ODCS](https://etlantic.readthedocs.io/en/latest/03_DATA_CONTRACTS/ODCS/) | Data shape, constraints, identity, and version |
| [DTCS](https://etlantic.readthedocs.io/en/latest/04_TRANSFORMATIONS/DTCS/) | Typed inputs, outputs, parameters, and transformation semantics |
| [DPCS](https://etlantic.readthedocs.io/en/latest/05_PIPELINES/DPCS/) | Pipeline graph, bindings, assets, and contract references |

Generation is deterministic and refuses invalid pipelines, so contract changes
can be reviewed and versioned alongside the code that defines them.

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

Interchange formats and the validation envelope are covered in
[Architecture](https://etlantic.readthedocs.io/en/latest/02_FOUNDATIONS/ARCHITECTURE/)
and [Validation Everywhere](https://etlantic.readthedocs.io/en/latest/02_FOUNDATIONS/VALIDATION_EVERYWHERE/).

## Capability boundary

| Capability | 0.34 |
|---|---|
| Cohesive CLI (`init`, `doctor`, durable reports) | Available |
| Typed contracts, graph validation, deterministic planning | Available |
| Local, Polars, Pandas, SQL, and PySpark execution paths | Available |
| Portable compilers for Polars, Pandas, SQL, and PySpark | Available |
| Portable quality expressions (`etlantic.quality/1`) | Available (Polars/Pandas/local; SQL/PySpark fail-closed) |
| Contract interchange, schema drift, lineage, reports, SARIF | Available |
| Airflow compilation (compile-only) and Prefect local MVP | Available (bounded) |
| Observability providers, run history, event consumers | Available |
| Trust, isolation, safe I/O, SBOM/attestations (single-tenant reference) | Available (bounded) |
| Structured Streaming / `etlantic-datafusion` | Experimental |
| Multi-tenant control plane, formal SLA | Not included |

Full matrix: [Capabilities](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/CAPABILITIES/).
Roadmap programs live under docs Contribute → Maintainers (for example the
[multi-tenant control-plane plan](https://etlantic.readthedocs.io/en/latest/11_DEVELOPMENT/MULTI_TENANT_CONTROL_PLANE_PLAN/))
— not day-0 reading.

## Learn more

[Installation](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/INSTALLATION/)
· [Quickstart](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/QUICKSTART/)
· [Compare](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/COMPARE/)
· [Engine selection](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/ENGINE_SELECTION/)
· [Security](https://etlantic.readthedocs.io/en/latest/02_FOUNDATIONS/SECURITY/)
· [Roadmap](https://etlantic.readthedocs.io/en/latest/11_DEVELOPMENT/ROADMAP_SUMMARY/)
· [Contributing](https://github.com/eddiethedean/etlantic/blob/main/CONTRIBUTING.md)

MIT licensed.
