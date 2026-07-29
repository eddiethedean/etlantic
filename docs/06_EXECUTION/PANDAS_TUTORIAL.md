# Execute with Pandas

> **Status: Available in ETLantic 0.33.0.** Prefer the **PyPI path** after
> Quickstart. The clone companion is optional.

## PyPI path (add Pandas to an `init` project)

Start from a working local project ([Quickstart](../01_GETTING_STARTED/QUICKSTART.md)).
The scaffold only registers `@Identity.implementation("local")`—you must add a
Pandas implementation and select the engine.

### 1. Install

```bash
python -m pip install 'etlantic[pandas]==0.33.0'
```

### 2. Register a Pandas implementation

In `pipeline.py`, keep the local implementation and add:

```python
@Identity.implementation("pandas")
def identity_pandas(rows):
    import pandas as pd

    if isinstance(rows, pd.DataFrame):
        return rows.copy()
    return pd.DataFrame(
        [row.model_dump() if hasattr(row, "model_dump") else row for row in rows]
    )
```

### 3. Select the engine

In `profiles/development.json`, set:

```json
"dataframe_engine": "pandas"
```

### 4. Validate and run

```bash
python -m etlantic validate pipeline.py:SamplePipeline --profile development
python -m etlantic run pipeline.py:SamplePipeline --profile development
cat data/out.json
```

### What to verify

- Report status is `succeeded`.
- `data/out.json` still contains Ada and Grace.
- Pandas is eager; requiring lazy execution fails during capability negotiation
  instead of degrading silently.

## Clone companion (optional)

Repository scripts under `examples/` are **not** in the PyPI wheel.

```bash
python -m pip install 'etlantic==0.33.0' 'etlantic-pandas==0.33.0'
git clone --branch v0.33.0 https://github.com/eddiethedean/etlantic.git
cd etlantic
python examples/dataframe_parity.py pandas
```

```python
@NormalizeCustomers.implementation("pandas")
def normalize_pandas(customers):
    import pandas as pd

    frame = customers if isinstance(customers, pd.DataFrame) else pd.DataFrame(customers)
    out = frame.copy()
    out["full_name"] = out["first_name"] + " " + out["last_name"]
    return out[["customer_id", "full_name"]]
```

Select it with `Profile(name="pandas", dataframe_engine="pandas")`. Complete
source:
[`examples/dataframe_parity.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/dataframe_parity.py).

See [Pandas execution details](PANDAS.md).
