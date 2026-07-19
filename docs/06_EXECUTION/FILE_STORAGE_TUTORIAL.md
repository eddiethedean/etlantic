# Run a File-Backed Pipeline

> **Status: Available in ETLantic 0.14.0.** The companion script is exercised
> by CI.

Use file storage when a pipeline must survive process boundaries. Unlike
in-memory storage, JSON and CSV inputs persist on disk.

This companion demonstrates durable JSON/CSV storage through the **Python
API**. It is not directly runnable with `etlantic run` because its binding
registry is constructed inside `run_files()`. Use `python examples/file_storage.py`
for execution, and use the CLI for `inspect` / `validate` / `plan` against
import-safe pipeline modules.

## Prerequisites

Repository examples are not installed with the PyPI wheel. Clone a matching
release checkout (prefer the `v0.14.0` tag) and use `uv`:

```bash
git clone https://github.com/eddiethedean/etlantic.git
cd etlantic
git checkout v0.14.0
uv sync
uv run python examples/file_storage.py
```

The example creates `_file_storage_out/json/output.json` and
`_file_storage_out/csv/output.csv` under `examples/`. Both contain normalized
customer-style records.

## The important configuration

File locations are explicit planning bindings:

```python
context.registry.register_binding(
    BindingDescriptor(
        binding="file_source",
        provider="json",
        location="input.json",
        kind="source",
    )
)
context.registry.register_binding(
    BindingDescriptor(
        binding="file_sink",
        provider="json",
        location="output.json",
        kind="sink",
    )
)
```

The binding names must match the `Extract` / `Load` `asset=` declarations
(registry descriptors still use the wire field `binding=`). Use
`provider="csv"` for CSV files. The complete source is
[`examples/file_storage.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/file_storage.py).

## Failure checks

- A missing input path fails before transformation output is written.
- Records are validated against the declared `Data` model.
- Never point examples at production files; use a temporary working directory.

Next: [runtime configuration](../10_REFERENCE/RUNTIME_CONFIGURATION.md) or the
[pilot walkthrough](PILOT_WALKTHROUGH.md).
