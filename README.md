<p align="center">
  <img
    src="https://raw.githubusercontent.com/eddiethedean/etlantic/main/docs/theme/assets/etlantic-logo.svg"
    width="148"
    alt="ETLantic logo"
  >
</p>

<h1 align="center">ETLantic</h1>

<p align="center">
  <strong>Design once. Validate everywhere.</strong><br>
  Typed, contract-driven data pipelines for Python.
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
  <a href="https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md">Roadmap</a>
</p>

---

ETLantic is a typed control layer for data pipelines. Define data,
transformations, and topology as Python contracts; validate them before work
begins; then run or compile the same logical pipeline for different backends.

```text
Typed contracts ──▶ Validation ──▶ Deterministic plan ──▶ Run or compile
```

The name describes the model: **ETL** is the data flow; **ETLantic** surrounds
it with typed contracts, validation, planning, and evidence.

```text
V(model) → Extract → V(input) → Transform → V(output) → Load → V/evidence
```

Validation is a control layer, not another business transformation. Runtime
checks are selected by policy and backend capability; publication evidence does
not imply an automatic sink reread.

## Why ETLantic?

- Catch invalid wiring, incompatible contracts, missing capabilities, and
  untrusted plugins before a write.
- Validate extracted inputs, transformation outputs, engine transitions, and
  publication boundaries against the same contracts.
- Keep one logical pipeline across local Python, Polars, Pandas, SQL, PySpark,
  Airflow, and Prefect.
- Review deterministic, secret-free plans and preserve structured diagnostics,
  lineage, schema observations, and run reports.
- Install a small core and add only the engines you need.

ETLantic does not replace dataframe engines, databases, Spark, schedulers,
storage systems, catalogs, or secret managers. It gives them one typed pipeline
model and one inspectable validation lifecycle.

> **Status:** ETLantic **0.21.0** ships a cohesive CLI journey with durable
> local workspaces. Stable for documented single-tenant reference deployments, not unrestricted enterprise production. Structured
> Streaming remains experimental. See [Capabilities](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/CAPABILITIES/)
> and [Production readiness](https://etlantic.readthedocs.io/en/latest/06_EXECUTION/PRODUCTION_READINESS/).

## Quickstart

ETLantic requires Python 3.11 or newer.

```bash
pip install etlantic==0.21.0
etlantic --version
```

```python
from etlantic import (
    Data,
    Extract,
    Input,
    Load,
    Output,
    Pipeline,
    PipelineRuntime,
    Transformation,
)


class RawCustomer(Data):
    customer_id: int
    first_name: str
    last_name: str


class Customer(Data):
    customer_id: int
    full_name: str


class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    result: Output[Customer]


@NormalizeCustomers.implementation("local")
def normalize_customers(customers: list[RawCustomer]) -> list[Customer]:
    return [
        Customer(
            customer_id=customer.customer_id,
            full_name=f"{customer.first_name} {customer.last_name}",
        )
        for customer in customers
    ]


class CustomerPipeline(Pipeline):
    raw: Extract[RawCustomer] = Extract(asset="customer_source")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Load[Customer] = Load(
        input=normalized.result,
        asset="customer_sink",
    )


def main() -> None:
    validation = CustomerPipeline.validate(profile="development")
    validation.raise_for_errors()
    CustomerPipeline.plan(profile="development")

    runtime = PipelineRuntime()
    runtime.memory.seed(
        "customer_source",
        [
            RawCustomer(customer_id=1, first_name="Ada", last_name="Lovelace"),
            RawCustomer(customer_id=2, first_name="Grace", last_name="Hopper"),
        ],
    )
    report = CustomerPipeline.run(profile="development", runtime=runtime)

    print(report.status.value)
    for customer in runtime.memory.get("customer_sink"):
        print(customer.model_dump())


if __name__ == "__main__":
    main()
```

For an import-safe module and CLI workflow, use the tested
[Quickstart](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/QUICKSTART/)
or [examples/quickstart.py](https://github.com/eddiethedean/etlantic/blob/main/examples/quickstart.py).

Save the Python example above as `pipeline.py` in an empty directory, then run:

```bash
etlantic inspect pipeline.py:CustomerPipeline --format json
etlantic validate pipeline.py:CustomerPipeline --profile development
etlantic plan pipeline.py:CustomerPipeline --profile development --format json
etlantic validate pipeline.py:CustomerPipeline --format sarif
```

Pass `--profile development` on every CLI command above. The CLI defaults to
`local` when `--profile` is omitted, which may not match tutorial pipelines.

## Engines and integrations

| Integration | Install | Role |
|---|---|---|
| Polars | `etlantic-polars` | Eager/lazy dataframe execution and portable compilation |
| Pandas | `etlantic-pandas` | Eager dataframe execution and portable compilation |
| SQL | `etlantic-sql` | Parameterized relational execution and portable SQL compilation |
| PySpark | `etlantic-pyspark` | Spark execution and portable compilation |
| Airflow | `etlantic-airflow` | Compile plans into DAG artifacts |
| Prefect | `etlantic-prefect` | Direct-execution scheduler integration |
| Keyring | `etlantic-keyring` | OS keyring secret provider |
| SQLModel | `etlantic-sqlmodel` | SQLModel bridge helpers |
| SparkForge | `etlantic-sparkforge` | Medallion adapter (bronze/silver/gold stay out of core) |
| DataFusion | `etlantic-datafusion` | Experimental query engine stub (Gate B) |

See [Optional packages](https://etlantic.readthedocs.io/en/latest/10_REFERENCE/OPTIONAL_PACKAGES/)
for observability (`otel` / `observability` extras) and Arrow helpers.

Matching extras such as `etlantic[polars]` are equivalent. Pin matching minors
while ETLantic is pre-1.0. Airflow is compile-only and does not install Apache
Airflow itself.

## Architecture

ETLantic keeps logical meaning separate from physical execution:

```text
Data (ODCS/ContractModel) + Transformation (DTCS) + Pipeline (DPCS)
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

## Capability boundary

| Capability | 0.21 |
|---|---|
| Cohesive CLI (`init`, `doctor`, durable reports) | Available |
| Typed contracts, graph validation, deterministic planning | Available |
| Local, Polars, Pandas, SQL, and PySpark execution paths | Available |
| Portable compilers for Polars, Pandas, SQL, and PySpark | Available |
| ODCS, DTCS, DPCS, schema drift, lineage, reports, and SARIF | Available |
| Airflow compilation and Prefect scheduling | Available |
| Versioned Polars↔Pandas tabular interchange | Available |
| Contract and configuration freeze (deep plans, security_mode) | Available |
| Trust, isolation, safe I/O, SBOM/attestations | Available |
| Structured Streaming | Experimental |
| `etlantic-datafusion` | Experimental |
| Full multi-tenant control plane | Not included |

See the full [Capabilities](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/CAPABILITIES/)
and [Validation Everywhere](https://etlantic.readthedocs.io/en/latest/02_FOUNDATIONS/VALIDATION_EVERYWHERE/)
guides for precise guarantees and limitations.

## Learn more

[Installation](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/INSTALLATION/)
· [Quickstart](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/QUICKSTART/)
· [Engine selection](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/ENGINE_SELECTION/)
· [Compare](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/COMPARE/)
· [Security](https://etlantic.readthedocs.io/en/latest/02_FOUNDATIONS/SECURITY/)
· [Roadmap](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md)
· [Contributing](https://github.com/eddiethedean/etlantic/blob/main/CONTRIBUTING.md)

MIT licensed.
