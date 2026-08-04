# Execute with Polars

> **Status: Available in ETLantic 0.44.0.** Prefer the **PyPI path** after
> Quickstart. The clone companion is optional.

!!! tip "PyPI vs clone"
    Steps below work from a Quickstart `init` project with **pip only**.
    Repository `examples/` need a git checkout.

## PyPI path (add Polars to an `init` project)

Start from a working local project ([Quickstart](../01_GETTING_STARTED/QUICKSTART.md)).
The scaffold only registers `@Identity.implementation("local")`—you must add a
Polars implementation and select the engine.

### 1. Install

```bash
python -m pip install 'etlantic[polars]==0.44.0'
```

### 2. Register a Polars implementation

In `pipeline.py`, keep the local implementation and add:

```python
@Identity.implementation("polars")
def identity_polars(rows):
    import polars as pl

    if hasattr(rows, "with_columns"):
        return rows
    return pl.DataFrame(
        [row.model_dump() if hasattr(row, "model_dump") else row for row in rows]
    )
```

### 3. Select the engine

In `profiles/development.json`, set:

```json
"dataframe_engine": "polars"
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
- Planning fails closed if Polars is selected but no `"polars"` implementation
  exists (do not expect a silent fallback to local Python).

For a non-identity transform (normalize customers), see the clone companion
below or [dataframe plugin compatibility](../10_REFERENCE/COMPATIBILITY.md).

## Clone companion (optional)

Repository scripts under `examples/` are **not** in the PyPI wheel. Use them
from a matching checkout when you want the CI-tested NormalizeCustomers demo.

```bash
python -m pip install 'etlantic==0.44.0' 'etlantic-polars==0.44.0'
git clone --branch v0.44.0 https://github.com/eddiethedean/etlantic.git
cd etlantic
python examples/dataframe_parity.py polars
```

From a checkout, `uv sync --group dataframes` installs the matching workspace
plugin.

```python
@NormalizeCustomers.implementation("polars")
def normalize_polars(customers):
    import polars as pl

    frame = customers if hasattr(customers, "with_columns") else pl.DataFrame(customers)
    return frame.with_columns(
        (pl.col("first_name") + " " + pl.col("last_name")).alias("full_name")
    ).select("customer_id", "full_name")
```

Select it with `Profile(name="polars", dataframe_engine="polars")`. Complete
source:
[`examples/dataframe_parity.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/dataframe_parity.py).

## Expected output

Run identifiers, timestamps, and durations vary. The stable evidence is the
selected profile, successful three-step summary, and normalized rows:

```text
profile:  polars-example
status:   succeeded
summary:  total=3 ok=3 failed=0 skipped=0 cancelled=0
{'customer_id': 1, 'full_name': 'Ada Lovelace'}
{'customer_id': 2, 'full_name': 'Grace Hopper'}
```

For the earlier `init` project, `cat data/out.json` retains the Quickstart
records because the added implementation is an identity transform:

```json
[
  {"id": 1, "name": "Ada"},
  {"id": 2, "name": "Grace"}
]
```

Lazy frames are preserved until a plan-declared collection boundary.

See [Polars execution details](POLARS.md) and
[dataframe plugin compatibility](../10_REFERENCE/COMPATIBILITY.md).
