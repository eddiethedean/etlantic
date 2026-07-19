# Portable Customer Transformation

!!! success "**Status: Available since ETLantic 0.17** (Polars + PySpark + Pandas + SQL relational); current docs target **0.18.0**."
    `@Transformation.portable` authoring shipped in 0.11. This guide runs a
    kernel or relational plan on Polars/PySpark/Pandas without a native
    `@implementation(...)` for the advertised claim set. Safe SQL portable
    lowering for that claim set also shipped in **0.15** (`etlantic-sql`).

Runnable companion (checkout required — not in the PyPI wheel):
[`examples/portable_polars_kernel.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/portable_polars_kernel.py).

```bash
pip install 'etlantic==0.18.0' 'etlantic-polars==0.18.0'
# from a checkout:
uv run python examples/portable_polars_kernel.py
```

To exercise advanced profile families on **Polars** (string-advanced +
window/1), use
[`examples/portable_wave17.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/portable_wave17.py)
(Polars-only companion):

```bash
uv sync --group dataframes
uv run python examples/portable_wave17.py
```

## Author once

```python
from etlantic import (
    Data,
    Input,
    Output,
    Parameter,
    Pipeline,
    PipelineRuntime,
    Profile,
    Load,
    Extract,
    Transformation,
)
from etlantic.plan import explain_plan, plan_pipeline
from etlantic.registry import PlanningContext
from etlantic.transform import functions as F
from etlantic_polars import create_plugin


class RawCustomer(Data):
    customer_id: int
    email: str
    age: int


class Customer(Data):
    customer_id: int
    email: str
    age: int


class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    minimum_age: Parameter[int] = 18
    result: Output[Customer]


@NormalizeCustomers.portable
def normalize(customers, minimum_age):
    return (
        customers.filter(F.col("age") >= minimum_age)
        .withColumn("email", F.lower(F.col("email")))
        .select("customer_id", "email", "age")
    )


class PortablePolarsPipeline(Pipeline):
    raw: Extract[RawCustomer] = Extract(asset="customers")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Load[Customer] = Load(input=normalized.result, asset="curated")
```

Inspect the emitted plan (no engine required):

```python
plan = NormalizeCustomers.to_transform_plan()
assert plan["planIdentity"] == "dtcs.transform-plan/2"
print(NormalizeCustomers.portable_fingerprint())
```

## Run on Polars without a native callable

```python
profile = Profile(
    name="polars-portable",
    dataframe_engine="polars",
    portable_transform_policy="require",  # fail closed if unsupported
)
runtime = PipelineRuntime()
runtime.register_dataframe_plugin("polars", create_plugin())
runtime.memory.seed(
    "customers",
    [
        RawCustomer(customer_id=1, email="A@X.COM", age=30),
        RawCustomer(customer_id=2, email="b@y.com", age=10),
    ],
)
context = PlanningContext.create(profile=profile, registry=runtime.registry)
planned = plan_pipeline(PortablePolarsPipeline, context=context)
assert planned.implementations["normalized"].kind == "portable_compiled"
report = PortablePolarsPipeline.run(
    profile=profile, runtime=runtime, context=context
)
print(runtime.memory.get("curated"))
```

Default policy is `prefer` (portable when covered; diagnosed native fallback
otherwise). Use `native` to ignore compilers.

## Expected plan evidence

```json
{
  "node": "normalized",
  "implementation_kind": "portable_compiled",
  "compiler": {"name": "etlantic-polars"},
  "ir_fingerprint": "<64-char sha256>"
}
```

Use `explain_plan(planned)` or `etlantic plan … --format json`.

## Expected outputs

| customer_id | email | age |
|---|---|---|
| 1 | a@x.com | 30 |

Age 10 is filtered out. Email is lowercased.

## Unsupported operations fail closed

All four official compilers ship kernel + `portable-relational/1`. In 0.17,
Polars and PySpark additionally claim string-advanced, conversion, statistics,
window `/1`, complex-types, complex-values, and reshape `/1`. Pandas and SQL
remain baseline-only. A plan requiring a profile the selected compiler does not
claim raises `PipelineValidationError` during planning under
`portable_transform_policy="require"`.

Explicit window frames remain unsupported; use unframed `row_number`, `rank`,
`dense_rank`, `lag`, `lead`, `first_value`, or `last_value` on Polars or
PySpark. Conversion and reshape are likewise available only on those two
engines in 0.17.

## What remains post-0.17

`portable-relational-extended/1`, `portable-temporal-iana/1`,
`portable-nondeterministic/1`, and `portable-window/2` remain unclaimed. Keep
native callables for those profiles and for any backend/profile combination
outside the [compiler matrix](../10_REFERENCE/PORTABLE_COMPILER_MATRIX.md).
