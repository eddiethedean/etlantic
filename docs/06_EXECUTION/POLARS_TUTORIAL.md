# Execute with Polars

> **Status: ETLantic 0.51.0 release candidate; publication pending.** Prefer the **PyPI path** after
> Quickstart. The clone companion is optional.

!!! tip "PyPI vs clone"
    Steps below work from a Quickstart `init` project with **pip only**.
    Repository `examples/` need a git checkout.

## PyPI path (add Polars to an `init` project)

Start from a working local project ([Quickstart](../01_GETTING_STARTED/QUICKSTART.md)).
The scaffold defines `@Identity.portable`, so you only need to install Polars
and select the engine. Do not rewrite the transformation with Polars APIs.

### 1. Install

```bash
python -m pip install 'etlantic[polars]==0.51.0'
```

### 2. Select the engine

In `profiles/development.json`, change only the engine and keep the generated
portable policy:

```json
"dataframe_engine": "polars",
"portable_transform_policy": "require"
```

### 3. Validate and run

```bash
python -m etlantic validate pipeline.py:SamplePipeline --profile development
python -m etlantic run pipeline.py:SamplePipeline --profile development
cat data/out.json
```

### What to verify

- Report status is `succeeded`.
- `data/out.json` still contains Ada and Grace.
- The plan selects a portable compiled implementation for Polars.
- Planning fails closed if the portable definition uses semantics outside the
  Polars compiler's advertised capabilities.

For a non-identity transform (normalize customers), see the clone companion
below or [dataframe plugin compatibility](../10_REFERENCE/COMPATIBILITY.md).

## Clone companion (optional)

Repository scripts under `examples/` are **not** in the PyPI wheel. Use them
from a matching checkout when you want the CI-tested NormalizeCustomers demo.

```bash
python -m pip install 'etlantic==0.51.0' 'etlantic-polars==0.51.0'
git clone --branch v0.51.0 https://github.com/eddiethedean/etlantic.git
cd etlantic
python examples/dataframe_parity.py polars
```

From a checkout, `uv sync --group dataframes` installs the matching workspace
plugin.

The companion defines the transformation once with
`@NormalizeCustomers.portable` and selects it with
`Profile(..., dataframe_engine="polars", portable_transform_policy="require")`.
Complete source:
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

Native `@Transformation.implementation("polars")` remains available for
Polars-only behavior outside the portable surface, but it pins the step to
Polars and is not eligible for adaptive execution.

See [Polars execution details](POLARS.md) and
[dataframe plugin compatibility](../10_REFERENCE/COMPATIBILITY.md).
