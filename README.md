![Pipelantic banner](https://raw.githubusercontent.com/eddiethedean/pipelantic/main/docs/theme/assets/pipelantic-banner.png)

# Pipelantic

[![Documentation Status](https://readthedocs.org/projects/pipelantic/badge/?version=latest)](https://pipelantic.readthedocs.io/en/latest/?badge=latest)

Define, validate, plan, and locally run contract-driven data pipelines with
typed Python.

> Define data, transformations, and pipelines with typed Python classes.
> Validate and plan them once. Execute them through interchangeable backends.

## Status

**0.5.0 — Dataframe Execution**

Pipelantic provides the typed modeling kernel, contract interoperability,
an immutable secret-free `PipelinePlan`, a local async runtime, and a
versioned dataframe execution protocol with independently installable
Polars (reference) and Pandas (compatibility) plugins.

Use Pipelantic when you want to catch incompatible wiring before processing
data, generate ODCS/DTCS/DPCS contracts from Python, inspect a deterministic
execution plan, or run the same logical pipeline on local Python, Polars, or
Pandas.

Pipelantic is currently alpha. SQL, Spark, Airflow, and other external
backend plugins remain future work.

See the [hosted documentation](https://pipelantic.readthedocs.io/) for the
full design,
[CHANGELOG.md](CHANGELOG.md) for release notes, and
[Roadmap](docs/11_DEVELOPMENT/ROADMAP.md) for sequencing.

## Install

```bash
pip install pipelantic
# optional dataframe engines
pip install pipelantic-polars
pip install pipelantic-pandas
# or
uv add pipelantic
```

### Development

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ruff format .
```

`uv sync` creates `.venv`, installs the package in editable mode, and installs
the `dev` dependency group (pytest, ruff, mkdocs) by default.

## Release

Tag a version that matches `src/pipelantic/_version.py`, then push the tag:

```bash
git tag v0.5.0
git push origin v0.5.0
```

GitHub Actions runs checks and publishes to PyPI using the `PYPI_API_TOKEN`
repository secret.

## Quick example

```python
from pipelantic import (
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


class CustomerPipeline(Pipeline):
    raw: Source[RawCustomer] = Source(binding="customer_source")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Sink[Customer] = Sink(
        input=normalized.result,
        binding="customer_sink",
    )


@NormalizeCustomers.implementation("local")
def normalize(customers: list[RawCustomer]) -> list[Customer]:
    return [
        Customer(
            customer_id=row.customer_id,
            full_name=f"{row.first_name} {row.last_name}",
        )
        for row in customers
    ]


CustomerPipeline.validate(profile="development").raise_for_errors()

runtime = PipelineRuntime()
runtime.memory.seed(
    "customer_source",
    [RawCustomer(customer_id=1, first_name="Ada", last_name="Lovelace")],
)
run_report = CustomerPipeline.run(profile="development", runtime=runtime)
print(runtime.memory.get("customer_sink"))
```

Run the complete tested version at
[examples/quickstart.py](examples/quickstart.py).

## Current capability boundary

| Capability | 0.4 |
|---|---|
| Typed modeling, validation, contracts, and planning | Available |
| Local Python execution and run reports | Available |
| Memory, callable, JSON, CSV, and no-write storage | Available |
| Pandas, Polars, SQL, Spark, and Airflow plugins | Not yet available |

## Documentation

- [Documentation site](https://pipelantic.readthedocs.io/)
- [Getting Started](docs/01_GETTING_STARTED/README.md)
- [Capabilities and Limitations](docs/01_GETTING_STARTED/CAPABILITIES.md)
- [Core Concepts](docs/02_FOUNDATIONS/CORE_CONCEPTS.md)
- [Architecture](docs/02_FOUNDATIONS/ARCHITECTURE.md)
- [Roadmap](docs/11_DEVELOPMENT/ROADMAP.md)

## License

MIT
