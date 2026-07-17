# Pandas Pipeline

!!! warning "Future design—not a ETLantic 0.10 API guide"
    This page is a design study. It may describe packages, commands, or
    interfaces beyond the shipped API surface. Prefer Current Capabilities,
    the runnable examples under `examples/`, the API reference, and the CLI
    reference for installable behavior.


This example builds a complete ETLantic pipeline that reads customer data
from CSV, executes transformations with Pandas, validates the output against
typed data contracts, and writes the curated result to Parquet.

The example demonstrates Pandas as a first-class execution backend while keeping
the logical pipeline independent of Pandas itself.

## Goal

Build a pipeline that:

1. Reads customer data from CSV.
2. Validates source records against `RawCustomer`.
3. Normalizes names and email addresses with a Pandas implementation.
4. Produces `Customer` records.
5. Writes the curated dataset to Parquet.
6. Generates ODCS, DTCS, and DPCS artifacts.
7. Executes locally through the standard Pipeline Plan lifecycle.

## Architecture

```text
CSV Source
    │
    ▼
Pandas Transformation
    │
    ▼
Contract Validation
    │
    ▼
Parquet Sink
```

The logical pipeline remains portable:

```text
RawCustomer
      │
      ▼
NormalizeCustomers
      │
      ▼
Customer
```

## Project Structure

```text
pandas-pipeline/
├── pyproject.toml
├── data/
│   ├── customers.csv
│   └── curated/
├── src/
│   └── pandas_pipeline/
│       ├── __init__.py
│       ├── contracts.py
│       ├── transformations.py
│       ├── pandas_implementations.py
│       ├── pipeline.py
│       └── profiles.py
├── contracts/
│   ├── data/
│   ├── transformations/
│   └── pipelines/
├── docs/
└── tests/
    ├── test_pipeline.py
    └── test_backend_equivalence.py
```

## Input Data

Create `data/customers.csv`:

```csv
customer_id,first_name,last_name,email
1,Ada,Lovelace,ADA@EXAMPLE.COM
2,Grace,Hopper, grace@example.com
3,Alan,Turing,alan@example.com
```

## Step 1 — Define the Data Contracts

```python
from typing import Annotated

from pydantic import Field
from etlantic import DataContractModel


class RawCustomer(DataContractModel):
    customer_id: Annotated[int, Field(strict=True, gt=0)]
    first_name: str
    last_name: str
    email: str


class Customer(DataContractModel):
    customer_id: Annotated[int, Field(strict=True, gt=0)]
    full_name: str
    email: str
```

## Step 2 — Define the Transformation Contract

```python
from etlantic import Input, Output, Parameter, Transformation


class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    lowercase_email: Parameter[bool] = True
    trim_whitespace: Parameter[bool] = True
    result: Output[Customer]
```

## Step 3 — Add the Pandas Implementation

```python
import pandas as pd


@NormalizeCustomers.implementation("pandas")
def normalize_customers(
    customers: pd.DataFrame,
    lowercase_email: bool,
    trim_whitespace: bool,
) -> pd.DataFrame:
    result = customers.copy()

    first_name = result["first_name"].astype("string")
    last_name = result["last_name"].astype("string")
    email = result["email"].astype("string")

    if trim_whitespace:
        first_name = first_name.str.strip()
        last_name = last_name.str.strip()
        email = email.str.strip()

    if lowercase_email:
        email = email.str.lower()

    return pd.DataFrame(
        {
            "customer_id": result["customer_id"],
            "full_name": first_name + " " + last_name,
            "email": email,
        }
    )
```

The implementation uses vectorized Pandas operations and avoids row-wise
`apply()`.

## Step 4 — Define the Pipeline

```python
from etlantic import Pipeline, Sink, Source


class CustomerPandasPipeline(Pipeline):
    raw: Source[RawCustomer] = Source(
        binding="customers_input",
    )

    normalized = NormalizeCustomers.step(
        customers=raw,
        lowercase_email=True,
        trim_whitespace=True,
    )

    curated: Sink[Customer] = Sink(
        input=normalized.result,
        binding="customers_output",
    )
```

## Step 5 — Define the Local Profile

```python
from etlantic import Profile


local = Profile(
    name="local",
    orchestrator="local-python",
    dataframe_engine="pandas",
    bindings={
        "customers_input": {
            "plugin": "csv",
            "path": "data/customers.csv",
        },
        "customers_output": {
            "plugin": "parquet",
            "path": "data/curated/customers",
            "write_mode": "overwrite",
        },
    },
)
```

## Step 6 — Validate and Plan

```python
report = CustomerPandasPipeline.validate()
report.raise_for_errors()

profile_report = CustomerPandasPipeline.validate_profile(local)
profile_report.raise_for_errors()

plan = CustomerPandasPipeline.plan(profile=local)
```

The plan resolves the Pandas implementation, CSV source, Parquet sink, and local
execution backend.

## Step 7 — Execute

```python
result = CustomerPandasPipeline.run(
    profile=local,
)
```

Asynchronous orchestration is also supported:

```python
result = await CustomerPandasPipeline.arun(
    profile=local,
)
```

ETLantic handles sync invocation internally.

## Expected Output

| customer_id | full_name | email |
|---|---|---|
| 1 | Ada Lovelace | ada@example.com |
| 2 | Grace Hopper | grace@example.com |
| 3 | Alan Turing | alan@example.com |

## Pandas Data Types

The Pandas plugin should map logical contract types to appropriate physical
dtypes, including:

- `int64`
- Nullable `Int64`
- `float64`
- `boolean`
- `string`
- `datetime64`
- PyArrow-backed extension dtypes

Physical dtype choices must not weaken the logical data contract.

## Nullable Dtypes

Pandas nullable extension dtypes are preferable when null values are valid:

```python
series.astype("Int64")
series.astype("boolean")
series.astype("string")
```

The plugin must distinguish contract nullability from physical dtype behavior.

## PyArrow-Backed Pandas

A profile may request the PyArrow dtype backend:

```python
Profile(
    dataframe_engine="pandas",
    pandas={
        "dtype_backend": "pyarrow",
    },
)
```

This can improve interoperability with Parquet, Arrow, Polars, Spark, and SQL
plugins.

## Validation

Validation may occur during source loading, after transformation, before sink
publication, or at explicit quality gates.

Portable constraints may be compiled into Pandas masks:

```python
invalid = dataframe[
    (dataframe["customer_id"] <= 0)
    | dataframe["email"].isna()
]
```

The active policy determines whether invalid rows fail, quarantine, or continue
through an explicitly permitted valid-row path.

## Memory Model

Pandas runs in one Python process. It is appropriate for:

- Small and moderate datasets
- Existing Pandas ecosystems
- Local analysis
- Pandas-only integrations
- Compatibility-focused pipelines

For larger workloads, Polars, SQL, or PySpark may be more appropriate.

## Chunked Sources

A Pandas source plugin may support chunked reads, but only transformations that
declare chunk-safe semantics should be selected.

Chunk-safe operations often include projection, filtering, and stateless column
normalization.

Global deduplication, full aggregation, sorting, windows, and cross-chunk joins
usually require additional coordination.

## Error Handling

Potential failures include:

- CSV parse errors
- Missing columns
- Dtype conversion failures
- Contract violations
- Out-of-memory conditions
- Missing Parquet dependencies
- Sink write failures

Plugins should translate backend exceptions into structured ETLantic
diagnostics.

## Testing

```python
from pathlib import Path

import pandas as pd


def test_pipeline_is_valid() -> None:
    report = CustomerPandasPipeline.validate()
    assert report.valid, report.diagnostics


def test_pandas_pipeline(tmp_path: Path) -> None:
    input_path = tmp_path / "customers.csv"
    output_path = tmp_path / "curated"

    input_path.write_text(
        "customer_id,first_name,last_name,email\n"
        "1,Ada,Lovelace,ADA@EXAMPLE.COM\n",
        encoding="utf-8",
    )

    profile = local.with_bindings(
        {
            "customers_input": {
                "plugin": "csv",
                "path": str(input_path),
            },
            "customers_output": {
                "plugin": "parquet",
                "path": str(output_path),
                "write_mode": "overwrite",
            },
        }
    )

    CustomerPandasPipeline.run(profile=profile)

    output = pd.read_parquet(output_path)

    assert output.to_dict(orient="records") == [
        {
            "customer_id": 1,
            "full_name": "Ada Lovelace",
            "email": "ada@example.com",
        }
    ]
```

## Backend Equivalence

The same transformation may also provide Polars or PySpark implementations.

Tests should normalize container and dtype differences while comparing logical
contract values:

```python
def test_pandas_matches_polars(
    pandas_result,
    polars_result,
) -> None:
    assert normalize(pandas_result) == normalize(polars_result)
```

## Generate Contracts and Documentation

```python
CustomerPandasPipeline.write_contracts(
    "contracts/",
)

plan.write_html(
    "docs/customer-pandas-pipeline.html",
    self_contained=True,
)

plan.write_mermaid(
    "docs/customer-pandas-lineage.mmd",
)
```

Expected contract output:

```text
contracts/
├── data/
│   ├── raw-customer.odcs.yaml
│   └── customer.odcs.yaml
├── transformations/
│   └── normalize-customers.dtcs.yaml
└── pipelines/
    └── customer-pandas-pipeline.dpcs.yaml
```

## Best Practices

- Use vectorized Pandas operations.
- Avoid row-wise `apply()` when native operations exist.
- Use explicit dtypes.
- Copy inputs before mutation.
- Validate outputs before publication.
- Keep contracts and pipelines independent of Pandas.
- Switch backends when data no longer fits memory.
- Test equivalence with the reference backend.

## Anti-Patterns

Avoid:

- Using `pd.DataFrame` in public pipeline contracts.
- Mutating shared upstream DataFrames unexpectedly.
- Assuming Pandas uses distributed execution.
- Hiding materialization boundaries.
- Skipping validation because dtypes appear correct.
- Using append sinks without considering retry duplication.

## Key Principle

> Pandas is a supported execution backend, not a modeling dependency.
> ETLantic preserves one portable transformation contract while allowing
> Pandas to serve compatibility-focused, in-memory, and ecosystem-integrated
> workloads.

## Next Step

Continue with **POLARS_PIPELINE.md** to implement the same logical workflow using
ETLantic's recommended high-performance dataframe backend.
