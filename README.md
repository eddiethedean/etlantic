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
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-d6a84b.svg" alt="MIT license"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
</p>

<p align="center">
  <a href="https://etlantic.readthedocs.io/">Documentation</a> ·
  <a href="docs/01_GETTING_STARTED/QUICKSTART.md">Quickstart</a> ·
  <a href="docs/01_GETTING_STARTED/CAPABILITIES.md">Capabilities</a> ·
  <a href="docs/11_DEVELOPMENT/ROADMAP.md">Roadmap</a>
</p>

---

ETLantic catches incompatible wiring before data is processed. Define datasets,
transformations, and pipelines as typed Python classes, then validate, plan,
run, or compile the same logical pipeline for different execution engines.

```text
Typed contracts ──▶ Validation ──▶ Deterministic plan ──▶ Run or compile
```

## Why ETLantic?

- **Fail earlier.** Detect broken references, incompatible contracts, missing
  implementations, unsupported capabilities, and untrusted plugins before a
  write occurs.
- **Keep logic portable.** Separate logical pipeline structure from local,
  Polars, Pandas, SQL, PySpark, and orchestration implementations.
- **Make plans reviewable.** Generate deterministic, immutable, secret-free
  execution plans with stable fingerprints.
- **Preserve evidence.** Produce structured diagnostics, lineage, schema
  observations, and run reports instead of opaque task logs.
- **Adopt incrementally.** The core has no dataframe, SQL, Spark, or Airflow
  dependency. Install only the integrations you need.

> **Project status:** Alpha **0.12.0**. The local runtime and reference plugins
> are available today. Structured Streaming is experimental. Portable
> transformation authoring and the Polars kernel compiler are available;
> relational, PySpark, Pandas, and safe SQL portable compilers are planned for
> 0.13–0.15. See the
> [capabilities guide](docs/01_GETTING_STARTED/CAPABILITIES.md) before choosing
> a production architecture.

## Quickstart

ETLantic requires Python 3.11 or newer.

```bash
pip install etlantic
etlantic --version
```

Create `pipeline.py`:

```python
from etlantic import (
    Data,
    Input,
    Output,
    Pipeline,
    PipelineRuntime,
    Sink,
    Source,
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
    raw: Source[RawCustomer] = Source(binding="customer_source")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Sink[Customer] = Sink(
        input=normalized.result,
        binding="customer_sink",
    )


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
```

Change the sink contract to an incompatible type and `validate()` returns a
structured diagnostic before any transformation or write is attempted.

The complete tested example is
[examples/quickstart.py](examples/quickstart.py).

## CLI workflow

The CLI follows the same validate-first lifecycle:

```bash
# Inspect and validate a pipeline
etlantic inspect pipeline.py:CustomerPipeline --format json
etlantic validate pipeline.py:CustomerPipeline --format json

# Build and explain a deterministic execution plan
etlantic plan pipeline.py:CustomerPipeline --format json
etlantic plan explain pipeline.py:CustomerPipeline --format json

# Execute locally
etlantic run pipeline.py:CustomerPipeline --profile development

# Emit CI diagnostics
etlantic validate pipeline.py:CustomerPipeline --format sarif
```

Airflow compilation requires the optional `etlantic-airflow` package:

```bash
pip install "etlantic[airflow]"
etlantic compile pipeline.py:CustomerPipeline --target airflow -o dags/
```

Other public command groups cover contract generation and diffs, plugins,
schema drift, reliability, visualization, and reports. Run `etlantic --help`
for the complete command surface.

## Choose an engine

Start with the core package, then add engines as needed:

```bash
pip install "etlantic[polars]"
pip install "etlantic[pandas]"
pip install "etlantic[sql]"
pip install "etlantic[pyspark]"
pip install "etlantic[airflow]"
```

| Integration | Package | Purpose |
|---|---|---|
| Polars | `etlantic-polars` | Eager/lazy dataframe execution and portable kernel compilation |
| Pandas | `etlantic-pandas` | Eager dataframe execution |
| SQL | `etlantic-sql` | Parameterized relational execution and SQL-to-SQL plans |
| PySpark | `etlantic-pyspark` | Spark execution and local session provider |
| Airflow | `etlantic-airflow` | Compile plans into Airflow DAG artifacts |
| Keyring | `etlantic-keyring` | Resolve runtime secrets from the OS keyring |
| SQLModel | `etlantic-sqlmodel` | Bridge ContractModel schemas and SQLModel |
| SparkForge | `etlantic-sparkforge` | Migrate SparkForge pipeline definitions |

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

Plans and reports contain secret references, never resolved secret values.
Secrets are resolved only at runtime. Capability and trust failures occur
before mutation.

## Capability boundary

| Capability | 0.12 |
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
| Polars portable kernel compiler | Available |
| Structured Streaming | Experimental |
| Relational, PySpark, Pandas, and safe SQL portable compilers | Planned for 0.13–0.15 |

See [Capabilities and Limitations](docs/01_GETTING_STARTED/CAPABILITIES.md)
and the [roadmap](docs/11_DEVELOPMENT/ROADMAP.md) for the precise support
boundary.

## Documentation

- [Hosted documentation](https://etlantic.readthedocs.io/)
- [Getting Started](docs/01_GETTING_STARTED/README.md)
- [Current 0.12 User Guide](docs/01_GETTING_STARTED/CURRENT_VERSION.md)
- [Quickstart](docs/01_GETTING_STARTED/QUICKSTART.md)
- [Core Concepts](docs/02_FOUNDATIONS/CORE_CONCEPTS.md)
- [Architecture](docs/02_FOUNDATIONS/ARCHITECTURE.md)
- [Portable Transformations](docs/04_TRANSFORMATIONS/PORTABLE_TRANSFORMATIONS.md)
- [Contributing](CONTRIBUTING.md)
- [Roadmap](docs/11_DEVELOPMENT/ROADMAP.md)

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

See [CONTRIBUTING.md](CONTRIBUTING.md) for package-specific test groups and
development conventions.

## License

[MIT](LICENSE)
