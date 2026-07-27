# 5–10 Minute Quickstart

> **Status: Available in ETLantic 0.24.0.** Use `python -m etlantic init` for the
> recommended CLI-first path with durable reports and declarative assets.

## 1. Install

ETLantic requires Python 3.11 or newer. Prefer `python -m` so PATH issues do not
block you.

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install 'etlantic==0.24.0'
python -m etlantic --version
```

## 2. Initialize a project

`init` requires an **empty directory** (or pass `--force` if the directory
already has files, for example a Poetry or uv project):

```bash
mkdir my-pipeline && cd my-pipeline
python -m etlantic init --with-toml
```

This creates `pipeline.py` (`SamplePipeline`), `profiles/development.json`,
sample `data/sample.json`, and `.etlantic/` workspace directories.

## 3. Validate and run (first success)

```bash
python -m etlantic validate pipeline.py:SamplePipeline --profile development
python -m etlantic run pipeline.py:SamplePipeline --profile development
cat data/out.json
```

No Python-side seed is required: the generated profile maps assets to
`json://data/...` paths.

### What success looks like

- `validate` prints a report with no errors (add `--format json` for machines).
- `run` prints a run status of **`succeeded`**.
- `data/out.json` contains Ada and Grace (identity transform on the sample).

Expected shape:

```json
[
  {
    "id": 1,
    "name": "Ada"
  },
  {
    "id": 2,
    "name": "Grace"
  }
]
```

Optional later: `python -m etlantic doctor --profile development`,
`inspect`, `plan`, and `report list`.

## 4. Aha — catch a bad change before write

Edit `pipeline.py` and change the `Row` contract so `name` becomes `full_name`
(or delete a required field). Re-validate:

```bash
python -m etlantic validate pipeline.py:SamplePipeline --profile development
```

You should see a validation error and **no** new write to `data/out.json` until
you fix the wiring. That is the product promise: validate before write.

Restore the contract (or continue with an intentional uppercase transform) in
[First Pipeline](FIRST_PIPELINE.md).

## 5. Python SDK path (optional)

From the same project directory:

```python
from pipeline import SamplePipeline

report = SamplePipeline.validate(profile="development")
report.raise_for_errors()
SamplePipeline.run(profile="development")
```

Standards acronyms (ODCS / DTCS / DPCS) and Gate A/B labels appear later in
Capabilities and Foundations—you do not need them for first success.

## Next steps

- [First Pipeline](FIRST_PIPELINE.md) — uppercase transform, richer contracts
- [Programmatic authoring](../05_PIPELINES/PROGRAMMATIC_AUTHORING.md) — builders + JSON
- [Engine selection](ENGINE_SELECTION.md) — add Polars, Pandas, SQL, or Spark
- [Installation](INSTALLATION.md) — optional engine packages
