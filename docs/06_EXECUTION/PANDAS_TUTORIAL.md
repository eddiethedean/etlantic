# Execute with Pandas

> **Status: Available in ETLantic 0.37.0.** Prefer the **PyPI path** after
> Quickstart. The clone companion is optional.

!!! tip "PyPI vs clone"
    Steps below work from a Quickstart `init` project with **pip only**.
    Repository `examples/` need a git checkout.

## PyPI path (add Pandas to an `init` project)

Start from a working local project ([Quickstart](../01_GETTING_STARTED/QUICKSTART.md)).
The scaffold only registers `@Identity.implementation("local")`—you must add a
Pandas implementation and select the engine.

### 1. Install

```bash
python -m pip install 'etlantic[pandas]==0.37.0'
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
python -m pip install 'etlantic==0.37.0' 'etlantic-pandas==0.37.0'
git clone --branch v0.37.0 https://github.com/eddiethedean/etlantic.git
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

## Expected output

Run identifiers, timestamps, and durations vary. The companion's stable
evidence is:

```text
profile:  pandas-example
status:   succeeded
summary:  total=3 ok=3 failed=0 skipped=0 cancelled=0
diagnostics:
  - [warning] PMDF420: Column 'full_name' uses object dtype; logical type may be ambiguous.
{'customer_id': 1, 'full_name': 'Ada Lovelace'}
{'customer_id': 2, 'full_name': 'Grace Hopper'}
```

`PMDF420` explains Pandas' broad `object` dtype; it does not change the
successful run status. For the earlier identity example, `data/out.json`
retains the same Ada and Grace records shown in Quickstart.

See [Pandas execution details](PANDAS.md).
