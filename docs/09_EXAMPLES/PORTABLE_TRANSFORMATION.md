# Portable Customer Transformation

!!! warning "Design study—not available in ETLantic 0.10"
    This example fixes the intended portable transformation experience before
    implementation. It is an acceptance fixture, not runnable current code.

This example defines one transformation and runs it through any conformant
dataframe compiler.

```python
from etlantic import (
    Data,
    Input,
    Output,
    Parameter,
    Pipeline,
    Sink,
    Source,
    Transformation,
)
from etlantic.transform import functions as F


class RawCustomer(Data):
    customer_id: int
    first_name: str
    last_name: str
    email: str | None
    age: int
    lifetime_value: float


class Customer(Data):
    customer_id: int
    full_name: str
    email: str | None
    segment: str


class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    minimum_age: Parameter[int] = 18
    result: Output[Customer]


@NormalizeCustomers.portable
def normalize(customers, minimum_age):
    return (
        customers
        .filter(F.col("age") >= minimum_age)
        .select(
            F.col("customer_id"),
            F.concat_ws(
                " ",
                F.col("first_name"),
                F.col("last_name"),
            ).alias("full_name"),
            F.lower(F.col("email")).alias("email"),
            F.when(F.col("lifetime_value") >= 10_000, F.lit("platinum"))
            .when(F.col("lifetime_value") >= 1_000, F.lit("gold"))
            .otherwise(F.lit("standard"))
            .alias("segment"),
        )
    )


class CustomerPipeline(Pipeline):
    raw: Source[RawCustomer] = Source(binding="customers")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Sink[Customer] = Sink(
        input=normalized.result,
        binding="curated_customers",
    )
```

## Profile selection

The pipeline does not change across engines:

```python
polars_profile = Profile(
    name="polars-local",
    dataframe_engine="polars",
    portable_transform_policy="require",
)

spark_profile = Profile(
    name="spark-production",
    spark_engine="pyspark",
    portable_transform_policy="require",
)
```

Both profiles select a plugin compiler for the same `dtcs.transform-plan/2`
(v1 readable) generated through the `etlantic.transform/1` authoring profile.

## Expected plan evidence

```json
{
  "step": "normalized",
  "implementation_kind": "portable_compiled",
  "portable_protocol": "dtcs.transform-plan/2",
  "authoring_profile": "etlantic.transform/1",
  "compiler_engine": "polars",
  "requirements": {
    "profiles": ["dtcs:profile/portable-relational-kernel/1"],
    "actions": ["dtcs:filter", "dtcs:project"],
    "functions": [
      "dtcs:case_when",
      "dtcs:concat_ws",
      "dtcs:lower"
    ]
  }
}
```

The real plan uses stable identities and fingerprints. It does not include
runtime parameter values or source rows.

## Expected outputs

Sample input (`customers`):

```text
customer_id  first_name  last_name  email                 age  lifetime_value
1            Ada         Lovelace   Ada@Example.com       36   12000.0
2            Grace       Hopper     grace@example.com     17   2500.0
3            Katherine   Johnson    k.johnson@example.com 42   800.0
```

With `minimum_age=18`, the curated sink (`result` / `curated_customers`) is:

```text
customer_id  full_name            email                  segment
1            Ada Lovelace         ada@example.com        platinum
3            Katherine Johnson    k.johnson@example.com  standard
```

Grace is filtered out by age. Segment thresholds are platinum ≥ 10000,
gold ≥ 1000, otherwise standard. Email is lowercased. Trimming is omitted
because DTCS 2.0 publishes `trim` as a field Semantic Action, not a general
structured-expression Function.

## Acceptance assertions

The eventual runnable example must prove:

1. Polars and PySpark produce contract-equivalent records.
2. Polars retains `LazyFrame` until the sink boundary.
3. PySpark uses native Column expressions and no Python UDF.
4. `minimum_age` remains a symbolic parameter in the plan.
5. Missing columns and unsupported functions fail during planning.
6. Plan and report serialization contain no source rows or secrets.
7. The native implementation mechanism can override this definition only under
   explicit profile policy.
