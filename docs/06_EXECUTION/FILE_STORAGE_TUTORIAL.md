# Run a File-Backed Pipeline

> **Status: Available in ETLantic 0.14.0.** The companion script is exercised
> by CI.

Use file storage when a pipeline must run in a fresh process, including from
the CLI. Unlike in-memory storage, JSON and CSV inputs survive process
boundaries.

## Run the tested example

```bash
git clone https://github.com/eddiethedean/etlantic.git
cd etlantic
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

The binding names must match the `Source` and `Sink` declarations. Use
`provider="csv"` for CSV files. The complete source is
[`examples/file_storage.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/file_storage.py).

## Failure checks

- A missing input path fails before transformation output is written.
- Records are validated against the declared `Data` model.
- Never point examples at production files; use a temporary working directory.

Next: [runtime configuration](../10_REFERENCE/RUNTIME_CONFIGURATION.md).
