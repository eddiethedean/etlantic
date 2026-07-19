# Five-Minute Quickstart

> **Status: Available in ETLantic 0.14.0.** Every API in this guide is shipped
> and the complete example is tested in CI.

This guide defines, validates, plans, and runs a typed pipeline using only the
core package and in-memory storage.

## Three terms you need

| Term | Meaning in this guide |
|---|---|
| **Binding** | Logical name for a source or sink (`binding="customer_source"`). The runtime resolves it to storage (here, in-memory). |
| **Profile** | Named environment for planning and running. These docs use `development` for the built-in local runtime. Pass the same name to `validate`, `plan`, and `run`. CLI defaults differ (`plan` → `local`, `run` → `development`)—pass `--profile development` to keep them aligned. |
| **Implementation** | Engine-specific body registered with `@Transformation.implementation("local")` (or `"polars"` / `"pandas"` after installing those plugins). |

## 1. Install

ETLantic requires Python 3.11 or newer.

```bash
python -m pip install 'etlantic>=0.14.0'
etlantic --version
```

From a git checkout (contributors), use `uv sync` and then
`uv run python …` so the project virtualenv is used. See
[Installation](INSTALLATION.md).

## 2. Create `pipeline.py`

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


report = CustomerPipeline.validate(profile="development")
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

## 4. See the product value (broken wiring)

Change the sink type so it no longer matches the transformation output, then
validate again:

```python
class WrongCustomer(Data):
    customer_id: int
    # missing full_name — incompatible with NormalizeCustomers.result


class BrokenPipeline(Pipeline):
    raw: Source[RawCustomer] = Source(binding="customer_source")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Sink[WrongCustomer] = Sink(
        input=normalized.result,
        binding="customer_sink",
    )


broken = BrokenPipeline.validate(profile="development")
print(broken.valid)  # False
for diagnostic in broken.diagnostics:
    print(f"{diagnostic.code}: {diagnostic.message}")
```

That failure—before any data is processed—is the core ETLantic value.

## 5. Validate and plan from the CLI

Save the quickstart script as `pipeline.py`, then validate and inspect its plan:

```bash
etlantic validate pipeline.py:CustomerPipeline --profile development --format json
etlantic plan pipeline.py:CustomerPipeline --profile development --format json
```

The records seeded above live only inside that Python process. A new CLI process
does not inherit them, so `etlantic run` cannot replay the same in-memory input.

## 6. Continue with a CLI-runnable file-backed pipeline

For a pipeline that survives process boundaries (and works with `etlantic run`),
use JSON/CSV storage:

```bash
# From a git checkout
uv sync
uv run python examples/file_storage.py
```

Then follow the
[file-storage tutorial](../06_EXECUTION/FILE_STORAGE_TUTORIAL.md) to register
file bindings and run via the CLI. That is the first-session path for
`etlantic validate` / `plan` / `run` against durable inputs.

Use the same `--profile` for validation, planning, and execution.

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

- [File-backed pipeline](../06_EXECUTION/FILE_STORAGE_TUTORIAL.md) — CLI-runnable continuation
- [Your First Pipeline](FIRST_PIPELINE.md) — inspect Mermaid, contracts, and plan explain
- [Capabilities](CAPABILITIES.md) — shipped vs not
- [Troubleshooting](TROUBLESHOOTING.md) if the run fails
- Optional engines: `examples/dataframe_parity.py`, `examples/airflow_compile.py`
