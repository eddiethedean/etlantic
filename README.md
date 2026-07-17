# ETLantic

[![CI](https://github.com/eddiethedean/etlantic/actions/workflows/ci.yml/badge.svg)](https://github.com/eddiethedean/etlantic/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/etlantic.svg)](https://pypi.org/project/etlantic/)
[![Python Versions](https://img.shields.io/pypi/pyversions/etlantic.svg)](https://pypi.org/project/etlantic/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Catch incompatible data-pipeline wiring before you process data.

Define datasets, transformations, and pipelines as typed Python classes.
Validate and plan them once. Run locally today with registered
implementations; optional Polars, Pandas, SQL, PySpark, and Airflow plugins
attach when installed. Portable `@Transformation.portable` authoring ships in
0.11; portable compilers remain 0.12–0.15.

**Status:** Alpha **0.11.0** — local runtime + optional
Polars/Pandas/SQL/PySpark/Airflow plugins, plus portable
`@Transformation.portable` authoring to `dtcs.transform-plan/2`. Structured
Streaming is experimental. Portable compilers remain planned for 0.12–0.15.

## Install

Requires Python 3.11+.

```bash
pip install etlantic
etlantic --version
```

This is everything required for the local quickstart. Add an engine only after
the first successful run: [choose an integration](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/CURRENT_VERSION/#choose-your-next-task).

### From source

Requires [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/eddiethedean/etlantic.git
cd etlantic
uv sync
uv run python -c "import etlantic; print(etlantic.__version__)"
uv run python examples/quickstart.py
```

## Quick example

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

Catch bad wiring **before** processing data—change the sink type and
`validate()` fails with a structured diagnostic instead of a runtime surprise.

Run the complete tested version at
[examples/quickstart.py](examples/quickstart.py).

## Current capability boundary

| Capability | 0.11 |
|---|---|
| Typed modeling, validation, contracts, and planning | Available |
| Local Python execution and run reports | Available |
| Memory, callable, JSON, CSV, and no-write storage | Available |
| Polars and Pandas dataframe plugins | Available (`etlantic-polars` / `etlantic-pandas`) |
| SQL plugin | Available (`etlantic-sql`) |
| PySpark plugin + local provider | Available (`etlantic-pyspark`) |
| Structured Streaming | Experimental |
| Airflow orchestrator compiler | Available (`etlantic-airflow`) |
| CLI compile / generate / schema / SARIF | Available |
| Plugin allowlists / keyring / SQLModel extras | Available |
| SparkForge migration adapter | Available (`etlantic-sparkforge`) |

**Next design line:** Portable authoring ships in 0.11. Releases 0.12–0.15 add
Polars, PySpark, Pandas, and safe SQL compilers for the same
`dtcs.transform-plan/2` plans. See the
[portable transformation guide](docs/04_TRANSFORMATIONS/PORTABLE_TRANSFORMATIONS.md)
and [roadmap](docs/11_DEVELOPMENT/ROADMAP.md).

## Documentation

Hosted docs: [etlantic.readthedocs.io](https://etlantic.readthedocs.io/)

- [Getting Started](docs/01_GETTING_STARTED/README.md) (start here)
- [Current 0.11 User Guide](docs/01_GETTING_STARTED/CURRENT_VERSION.md)
- [Quickstart](docs/01_GETTING_STARTED/QUICKSTART.md)
- [Capabilities and Limitations](docs/01_GETTING_STARTED/CAPABILITIES.md)
- [Evaluator brief](docs/01_GETTING_STARTED/EVALUATOR.md)
- [Core Concepts](docs/02_FOUNDATIONS/CORE_CONCEPTS.md)
- [Architecture](docs/02_FOUNDATIONS/ARCHITECTURE.md)
- [Contributing](CONTRIBUTING.md)
- [Roadmap](docs/11_DEVELOPMENT/ROADMAP.md)

Build the docs locally with `uv run mkdocs serve`.

## Development

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ruff format .
```

`uv sync` creates `.venv`, installs the package in editable mode, and installs
the `dev` dependency group (pytest, ruff, mkdocs) by default.

## License

MIT
