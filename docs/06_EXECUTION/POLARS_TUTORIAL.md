# Execute with Polars

> **Status: Available in ETLantic 0.21.0.** This guide uses the CI-tested
> dataframe parity example.


!!! note "Repository examples"
    Companion scripts under `examples/` are not installed with the PyPI
    wheel. Clone a matching checkout (prefer the `v0.21.0` tag) and use
    `uv sync` / the documented dependency group before running them.

## Install and run

```bash
python -m pip install 'etlantic==0.21.0' 'etlantic-polars==0.21.0'
git clone --branch v0.21.0 https://github.com/eddiethedean/etlantic.git
cd etlantic
python examples/dataframe_parity.py polars
```

From a checkout, `uv sync --group dataframes` installs the matching workspace
plugin.

## Register the implementation

```python
@NormalizeCustomers.implementation("polars")
def normalize_polars(customers):
    import polars as pl

    frame = customers if hasattr(customers, "with_columns") else pl.DataFrame(customers)
    return frame.with_columns(
        (pl.col("first_name") + " " + pl.col("last_name")).alias("full_name")
    ).select("customer_id", "full_name")
```

Select it with `Profile(name="polars", dataframe_engine="polars")`. Planning
records the selected engine and capabilities; it does not silently fall back
to local Python.

The complete source is
[`examples/dataframe_parity.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/dataframe_parity.py).

## What to verify

- The report status is `succeeded`.
- The curated records contain `customer_id` and `full_name` only.
- Lazy frames are preserved until a plan-declared collection boundary.

See [Polars execution details](POLARS.md) and
[dataframe plugin compatibility](../10_REFERENCE/COMPATIBILITY.md).
