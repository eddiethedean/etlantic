# Execute with Pandas

> **Status: Available in ETLantic 0.14.0.** This guide uses the same logical
> pipeline as the Polars tutorial.

## Install and run

```bash
python -m pip install 'etlantic==0.14.0' 'etlantic-pandas==0.14.0'
git clone https://github.com/eddiethedean/etlantic.git
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
