# Execute with Pandas

> **Status: ETLantic 0.51.0 release candidate; publication pending.** Prefer the **PyPI path** after
> Quickstart. The clone companion is optional.

!!! tip "PyPI vs clone"
    Steps below work from a Quickstart `init` project with **pip only**.
    Repository `examples/` need a git checkout.

## PyPI path (add Pandas to an `init` project)

Start from a working local project ([Quickstart](../01_GETTING_STARTED/QUICKSTART.md)).
The scaffold defines `@Identity.portable`, so you only need to install Pandas
and select the engine. Do not rewrite the transformation with Pandas APIs.

### 1. Install

```bash
python -m pip install 'etlantic[pandas]==0.51.0'
```

### 2. Select the engine

In `profiles/development.json`, change only the engine and keep the generated
portable policy:

```json
"dataframe_engine": "pandas",
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
- Pandas is eager; requiring lazy execution fails during capability negotiation
  instead of degrading silently.

## Clone companion (optional)

Repository scripts under `examples/` are **not** in the PyPI wheel.

```bash
python -m pip install 'etlantic==0.51.0' 'etlantic-pandas==0.51.0'
git clone --branch v0.51.0 https://github.com/eddiethedean/etlantic.git
cd etlantic
python examples/dataframe_parity.py pandas
```

The companion defines the transformation once with
`@NormalizeCustomers.portable` and selects it with
`Profile(..., dataframe_engine="pandas", portable_transform_policy="require")`.
Complete source:
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

Native `@Transformation.implementation("pandas")` remains available for
Pandas-only behavior such as intentional index semantics, but it pins the step
to Pandas and is not eligible for adaptive execution.
