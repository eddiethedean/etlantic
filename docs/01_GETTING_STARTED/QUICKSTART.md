# Five-Minute Quickstart

> **Status: Available in Pipelantic 0.6.0.** Every API in this guide is shipped
> and the complete example is tested in CI.

This guide defines, validates, plans, and runs a typed pipeline using only the
core package and in-memory storage.

## Three terms you need

| Term | Meaning in this guide |
|---|---|
| **Binding** | Logical name for a source or sink (`binding="customer_source"`). The runtime resolves it to storage (here, in-memory). |
| **Profile** | Named environment for planning and running. Use `development` for the built-in local runtime examples. The CLI `plan` command defaults to `local`; `run` defaults to `development`. |
| **Implementation** | Engine-specific body registered with `@Transformation.implementation("local")` (or `"polars"` / `"pandas"` after installing those plugins). |

## 1. Install

Pipelantic requires Python 3.11 or newer.

```bash
python -m pip install pipelantic
```

Verify the installation:

```bash
python -c "import pipelantic; print(pipelantic.__version__)"
```

## 2. Create `pipeline.py`

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
    raw: Source[RawCustomer] = Source(binding="customer_source")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Sink[Customer] = Sink(
        input=normalized.result,
        binding="customer_sink",
    )


report = CustomerPipeline.validate()
report.raise_for_errors()

plan = CustomerPipeline.plan(profile="development")
print(f"Plan: {plan.plan_id}")

runtime = PipelineRuntime()
runtime.memory.seed(
    "customer_source",
    [
        RawCustomer(customer_id=1, first_name="Ada", last_name="Lovelace"),
        RawCustomer(customer_id=2, first_name="Grace", last_name="Hopper"),
    ],
)

run_report = CustomerPipeline.run(profile="development", runtime=runtime)
print(run_report.to_text())

for customer in runtime.memory.get("customer_sink"):
    print(customer.model_dump())
```

## 3. Run it

```bash
python pipeline.py
```

The final records are:

```text
{'customer_id': 1, 'full_name': 'Ada Lovelace'}
{'customer_id': 2, 'full_name': 'Grace Hopper'}
```

The exact generated plan and run identifiers vary, but the run status should
be `succeeded`.

## What happened

1. `Data` classes defined the input and output contracts.
2. `Transformation` declared the typed interface.
3. `implementation("local")` registered executable Python code.
4. `Pipeline` connected a named source, step, and sink.
5. Validation checked the graph before execution.
6. Planning produced a deterministic, secret-free `PipelinePlan`.
7. `PipelineRuntime` supplied in-memory source and sink storage.
8. `run()` returned a structured `PipelineRunReport`.

The same example is available at `examples/quickstart.py`.

## Next

- File-backed JSON/CSV: run `python examples/file_storage.py`
- Polars or Pandas (after installing plugins):
  `python examples/dataframe_parity.py polars`
- Build the example in smaller steps in [Your First Pipeline](FIRST_PIPELINE.md)
- Review [Current Capabilities and Limitations](CAPABILITIES.md)
- See [Troubleshooting](TROUBLESHOOTING.md) if the run fails
