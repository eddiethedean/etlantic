# Five-Minute Quickstart

> **Status: Available in ETLantic 0.14.0.** Every API in this guide is shipped
> and the complete example is tested in CI.

This guide defines, validates, plans, and runs a typed pipeline using only the
core package and in-memory storage.

## Three terms you need

| Term | Meaning in this guide |
|---|---|
| **Asset** | Logical name for an extract or load (`asset="customer_source"`). The runtime resolves it to storage (here, in-memory). Plan/DPCS wire fields still say `binding`. |
| **Profile** | Named environment for planning and running. These docs use `development` for the built-in local runtime. Pass the same name to `validate`, `plan`, and `run`. CLI defaults differ (`plan` → `local`, `run` → `development`)—pass `--profile development` to keep them aligned. |
| **Implementation** | Engine-specific body registered with `@Transformation.implementation("local")` (or `"polars"` / `"pandas"` after installing those plugins). |

## 1. Install

ETLantic requires Python 3.11 or newer.

```bash
python -m pip install 'etlantic==0.14.0'
etlantic --version
# or: python -m etlantic --version
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
    Load,
    Extract,
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
    raw: Extract[RawCustomer] = Extract(asset="customer_source")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Load[Customer] = Load(
        input=normalized.result,
        asset="customer_sink",
    )


def main() -> None:
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


if __name__ == "__main__":
    main()
```

Keep contracts, `@implementation`, and `CustomerPipeline` at module scope so
the CLI can import them. Guard validate/seed/run under
`if __name__ == "__main__"` so `etlantic validate` / `plan` do not execute the
pipeline during import.

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
    raw: Extract[RawCustomer] = Extract(asset="customer_source")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Load[WrongCustomer] = Load(
        input=normalized.result,
        asset="customer_sink",
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

## 6. Continue with durable file-backed storage

For a pipeline that survives process boundaries, use JSON/CSV storage through
the Python API:

```bash
# From a git checkout of v0.14.0 (examples are not installed with the wheel)
uv sync
uv run python examples/file_storage.py
```

Follow the
[file-storage tutorial](../06_EXECUTION/FILE_STORAGE_TUTORIAL.md). That
companion registers bindings inside Python and is **not** directly runnable
with `etlantic run` today—use `python examples/file_storage.py` for durable
inputs, and use the CLI for `inspect` / `validate` / `plan` against
import-safe pipeline modules.

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

- [File-backed pipeline](../06_EXECUTION/FILE_STORAGE_TUTORIAL.md) — durable JSON/CSV via Python
- [Your First Pipeline](FIRST_PIPELINE.md) — inspect Mermaid, contracts, and plan explain
- [Capabilities](CAPABILITIES.md) — shipped vs not
- [Troubleshooting](TROUBLESHOOTING.md) if the run fails
- Optional engines: `examples/dataframe_parity.py`, `examples/airflow_compile.py`
