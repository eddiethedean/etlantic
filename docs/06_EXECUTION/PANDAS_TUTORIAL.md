# Execute with Pandas

> **Status: Available in ETLantic 0.21.0.** This guide uses the same logical
> pipeline as the Polars tutorial.


!!! note "Repository examples"
    Companion scripts under `examples/` are not installed with the PyPI
    wheel. Clone a matching checkout (prefer the `v0.21.0` tag) and use
    `uv sync` / the documented dependency group before running them.

## Install and run

```bash
python -m pip install 'etlantic==0.21.0' 'etlantic-pandas==0.21.0'
git clone --branch v0.21.0 https://github.com/eddiethedean/etlantic.git
cd etlantic
python examples/dataframe_parity.py pandas
```

## Register the implementation

```python
@NormalizeCustomers.implementation("pandas")
def normalize_pandas(customers):
    import pandas as pd

    frame = customers if isinstance(customers, pd.DataFrame) else pd.DataFrame(customers)
    out = frame.copy()
    out["full_name"] = out["first_name"] + " " + out["last_name"]
    return out[["customer_id", "full_name"]]
```

Select it with `Profile(name="pandas", dataframe_engine="pandas")`. The copy is
intentional: plugin ownership rules prevent one step from mutating a shared
artifact unexpectedly.

The complete source is
[`examples/dataframe_parity.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/dataframe_parity.py).

Pandas is eager. Requiring lazy execution fails during capability negotiation
instead of degrading silently. See [Pandas execution details](PANDAS.md).
