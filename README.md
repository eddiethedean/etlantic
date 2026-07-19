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

ETLantic catches incompatible wiring before data is processed. Define datasets,
transformations, and pipelines as typed Python classes, then validate, plan,
run, or compile the same logical pipeline for different execution engines.

```text
Typed contracts ──▶ Validation ──▶ Deterministic plan ──▶ Run or compile
```

ETLantic treats validation as a continuous control layer around ETL, not as a
single check at the beginning:

```text
V(model) ──▶ Extract ──▶ V(input) ──▶ Transform ──▶ V(output) ──▶ Load ──▶ V/evidence
```

That means validating the pipeline before work begins, validating data against
contracts at execution boundaries, and recording whether publication satisfied
the declared contract and write policy. Validation is not an extra business
transformation and does not always mean rereading a sink; the exact runtime
check is selected by policy and backend capability. The principle is simple:
**ETL, with validation at every boundary.**

That is also the promise behind the name: **ETL** is the familiar data flow;
**ETLantic** surrounds that flow with typed contracts, validation, planning,
and evidence from source to publication.

## Why ETLantic?

- **Fail earlier.** Detect broken references, incompatible contracts, missing
  implementations, unsupported capabilities, and untrusted plugins before a
  write occurs.
- **Validate throughout.** Check extracted inputs, transformation outputs, and
  publication boundaries against the same typed contracts and preserve the
  result as structured evidence.
- **Keep logic portable.** Separate logical pipeline structure from local,
  Polars, Pandas, SQL, PySpark, and orchestration implementations.
- **Make plans reviewable.** Generate deterministic, immutable, secret-free
  execution plans with stable fingerprints.
- **Preserve evidence.** Produce structured diagnostics, lineage, schema
  observations, and run reports instead of opaque task logs.
- **Adopt incrementally.** The core has no dataframe, SQL, Spark, or Airflow
  dependency. Install only the integrations you need.

> **Project status:** **0.18.0 is stable for documented single-tenant
> reference deployments** (not unrestricted enterprise production). Structured
> Streaming remains experimental. Multi-tenant isolation, compliance
> attestations, and SBOM/signing remain adopter-owned or roadmap (0.20+).
> See [Capabilities](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/CAPABILITIES/),
> [Evaluator](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/EVALUATOR/), and
> [Production readiness](https://etlantic.readthedocs.io/en/latest/06_EXECUTION/PRODUCTION_READINESS/).

## Green path

1. [Install](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/INSTALLATION/) — `pip install 'etlantic==0.18.0'`
2. [Quickstart](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/QUICKSTART/) — five-minute success
3. [First Pipeline](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/FIRST_PIPELINE/) — CLI validate/plan
4. [Engine selection](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/ENGINE_SELECTION/) — then an engine tutorial; diligence: [Capabilities](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/CAPABILITIES/) or [Compare](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/COMPARE/)

## Quickstart

ETLantic requires Python 3.11 or newer.

```bash
pip install etlantic==0.18.0
python -m etlantic --version
# equivalent: etlantic --version
```

Create `pipeline.py`:

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
            customer_id=row.customer_id,
            full_name=f"{row.first_name} {row.last_name}",
        )
        for row in customers
    ]


class CustomerPipeline(Pipeline):
    raw: Extract[RawCustomer] = Extract(asset="customer_source")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Load[Customer] = Load(
        input=normalized.result,
        asset="customer_sink",
    )


def main() -> None:
    # Validation and planning do not execute transformation code.
    CustomerPipeline.validate(profile="development").raise_for_errors()
    plan = CustomerPipeline.plan(profile="development")
    print(plan.fingerprint)

    runtime = PipelineRuntime()
    runtime.memory.seed(
        "customer_source",
        [RawCustomer(customer_id=1, first_name="Ada", last_name="Lovelace")],
    )
    report = CustomerPipeline.run(profile="development", runtime=runtime)

    print(report.status)  # succeeded
    print(runtime.memory.get("customer_sink")[0].model_dump())
    # {"customer_id": 1, "full_name": "Ada Lovelace"}


if __name__ == "__main__":
    main()
```

Keep contracts, the transformation registration, and `CustomerPipeline` at
module scope so the CLI can import them. Put validate/seed/run under
`if __name__ == "__main__"` so `etlantic validate` / `plan` do not execute the
pipeline during import.

Change the sink contract to an incompatible type and `validate()` returns a
structured diagnostic before any transformation or write is attempted.

The complete tested example is
[examples/quickstart.py](https://github.com/eddiethedean/etlantic/blob/main/examples/quickstart.py)
(requires a repository checkout—the PyPI wheel does not include `examples/`).
Prefer the paste-ready [Quickstart](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/QUICKSTART/)
after `pip install`.

## CLI workflow

The CLI follows the same validate-first lifecycle. Validation and planning do
not require seeded data; in-memory execution does, so run the seeded example
with Python:

```bash
# Inspect and validate a pipeline (import-safe when side effects are guarded)
etlantic inspect pipeline.py:CustomerPipeline --format json
etlantic validate pipeline.py:CustomerPipeline --profile development --format json

# Build and explain a deterministic execution plan
etlantic plan pipeline.py:CustomerPipeline --profile development --format json
etlantic plan explain pipeline.py:CustomerPipeline --profile development --format json

# Execute the seeded in-memory example
python pipeline.py

# Emit CI diagnostics
etlantic validate pipeline.py:CustomerPipeline --profile development --format sarif
```

Airflow compilation requires the optional `etlantic-airflow` package. It is
**compile-only** and does not install Apache Airflow—install Airflow separately
in the environment that loads generated DAGs:

```bash
pip install 'etlantic[airflow]==0.18.0'
etlantic compile pipeline.py:CustomerPipeline --target airflow -o dags/
```

Other public command groups cover contract generation and diffs, plugins,
schema drift, reliability, visualization, and reports. Run `etlantic --help`
for the complete command surface.

## Choose an engine

Start with the core package, then add engines as needed (pin the minor in 0.x).
**Primary form** installs the optional package directly; extras are equivalent:

```bash
pip install 'etlantic-polars==0.18.0'    # equivalent: etlantic[polars]==0.18.0
pip install 'etlantic-pandas==0.18.0'    # equivalent: etlantic[pandas]==0.18.0
pip install 'etlantic-sql==0.18.0'       # equivalent: etlantic[sql]==0.18.0
pip install 'etlantic-pyspark==0.18.0'   # equivalent: etlantic[pyspark]==0.18.0
pip install 'etlantic-airflow==0.18.0'   # equivalent: etlantic[airflow]==0.18.0
pip install 'etlantic-prefect==0.18.0'   # equivalent: etlantic[prefect]==0.18.0
```

| Integration | Package | Purpose |
|---|---|---|
| Polars | `etlantic-polars` | Eager/lazy dataframe execution and portable kernel compilation |
| Pandas | `etlantic-pandas` | Eager dataframe execution |
| SQL | `etlantic-sql` | Parameterized relational execution and SQL-to-SQL plans |
| PySpark | `etlantic-pyspark` | Spark execution and local session provider |
| Airflow | `etlantic-airflow` | Compile plans into Airflow DAG artifacts (does **not** install Apache Airflow) |
| Prefect | `etlantic-prefect` | Optional direct-execution scheduler (local MVP) |
| Keyring | `etlantic-keyring` | Resolve runtime secrets from the OS keyring |
| SQLModel | `etlantic-sqlmodel` | Bridge ContractModel schemas and SQLModel |
| SparkForge | `etlantic-sparkforge` | Migrate SparkForge pipeline definitions |

`etlantic-airflow` is compile-only: install Apache Airflow separately in the
environment that loads generated DAGs.

Plugins are discovered through Python entry points and scoped to a runtime
registry. Production profiles require an explicit plugin allowlist and reject
untrusted plugins by default.

## How it works

ETLantic keeps logical intent separate from physical execution:

1. **Author** typed `Data`, `Transformation`, and `Pipeline` classes.
2. **Inspect** an immutable logical graph without running user code.
3. **Validate** structure, references, contracts, policies, capabilities, and
   plugin trust in ordered phases.
4. **Plan** engine selections, execution regions, bindings, artifacts, and
   materialization boundaries.
5. **Execute or compile** the plan through small backend protocols.
6. **Report** step outcomes, diagnostics, lineage, artifacts, and schema
   observations.

During execution, the same contracts form validation boundaries around
extracts, transformations, engine/interchange transitions, and loads. A
policy may fail, reject/quarantine invalid rows where supported, or record
evidence, but a backend cannot silently weaken a required check.

Plans and reports contain secret references, never resolved secret values.
Secrets are resolved only at runtime. Capability and trust failures occur
before mutation.

## Capability boundary

| Capability | 0.18 |
|---|---|
| Typed modeling, validation, contracts, and deterministic planning | Available |
| Local Python execution and structured run reports | Available |
| Memory, callable, JSON, CSV, and no-write storage | Available |
| Polars and Pandas dataframe plugins | Available |
| SQL and PySpark plugins | Available |
| Airflow plan compiler | Available |
| ODCS, DTCS, and DPCS interchange | Available |
| Schema drift, reliability, visualization, and SARIF tooling | Available |
| Production plugin allowlists and runtime secret providers | Available |
| Portable transformation authoring | Available |
| Polars + PySpark + Pandas + SQL portable compilers (kernel + relational `/1`) | Available |
| Public portable transform conformance SDK | Available |
| Versioned tabular interchange (Polars↔Pandas Gate A) | Available |
| Structured Streaming | Experimental |
| Advanced portable profile graduation | **Available** on Polars + PySpark (since 0.17; current in 0.18); Pandas/SQL baseline only |

See [Capabilities and Limitations](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/CAPABILITIES/)
and the [roadmap](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md) for the precise support
boundary.

## Documentation

- [Hosted documentation](https://etlantic.readthedocs.io/)
- [Getting Started](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/)
- [Quickstart](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/QUICKSTART/)
- [Compare](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/COMPARE/) — vs dbt, Airflow, Prefect, Pandera
- [Evaluator brief](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/EVALUATOR/)
- [Capabilities](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/CAPABILITIES/)
- [Production readiness](https://etlantic.readthedocs.io/en/latest/06_EXECUTION/PRODUCTION_READINESS/)
- [Security](https://etlantic.readthedocs.io/en/latest/02_FOUNDATIONS/SECURITY/)
- [Contributing](https://github.com/eddiethedean/etlantic/blob/main/CONTRIBUTING.md)
- [Roadmap](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md)

## Development

The repository uses [uv](https://docs.astral.sh/uv/) for its workspace and
development environment:

```bash
git clone https://github.com/eddiethedean/etlantic.git
cd etlantic
uv sync
uv run python examples/quickstart.py
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mkdocs serve
```

See [CONTRIBUTING.md](https://github.com/eddiethedean/etlantic/blob/main/CONTRIBUTING.md) for package-specific test groups and
development conventions.

## License

[MIT](https://github.com/eddiethedean/etlantic/blob/main/LICENSE)
