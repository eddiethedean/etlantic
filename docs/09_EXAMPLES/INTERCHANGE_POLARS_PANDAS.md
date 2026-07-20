# Polars ↔ Pandas Interchange

!!! success "**Status: Available in ETLantic 0.21.0**"
    Gate A versioned tabular interchange (`etlantic.interchange/1`) shipped in
    0.18.0 for compatible Polars↔Pandas cross-engine boundaries.

Runnable companion:
[`examples/interchange_polars_pandas.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/interchange_polars_pandas.py).

```bash
uv sync --group dataframes
uv run python examples/interchange_polars_pandas.py
```

Or from published packages:

```bash
pip install 'etlantic[dataframes]==0.21.0'
python examples/interchange_polars_pandas.py
```

The example plans a Polars step that feeds a Pandas step, prints the selected
`etlantic.interchange/1` descriptor (mechanism, engines, copy eligibility), and
runs the pipeline to confirm the boundary executes.

See [What's New in 0.18](../01_GETTING_STARTED/WHATS_NEW_0_18.md) and
[Capabilities](../01_GETTING_STARTED/CAPABILITIES.md).
