# Portable Customer Transformation

!!! success "**Status: Available in ETLantic 0.14** (Polars + PySpark + Pandas relational)"
    `@Transformation.portable` authoring shipped in 0.11. This guide runs a
    kernel or relational plan on Polars/PySpark/Pandas without a native
    `@implementation(...)` for the advertised claim set. Safe SQL portable
    lowering remains 0.15+.

Runnable companion:
[`examples/portable_polars_kernel.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/portable_polars_kernel.py).

```bash
pip install 'etlantic==0.14.0' 'etlantic-polars==0.14.0'
python examples/portable_polars_kernel.py
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
    Sink,
    Source,
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
    raw: Source[RawCustomer] = Source(binding="customers")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Sink[Customer] = Sink(input=normalized.result, binding="curated")
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

Joins, windows, and conversion-profile functions such as `dtcs:cast` are
outside the 0.12 Polars kernel claim. With `portable_transform_policy="require"`,
planning raises `PipelineValidationError` with `PMXFORM301` (or `PMXFORM302`
when no compiler is discoverable).

## What remains future

- Safe SQL portable lowering (0.15+)
- Portable SQL lowering (0.15+)

Keep `@implementation("pyspark")` / `"pandas"` / `"sql"` for those engines
until their compilers ship.
