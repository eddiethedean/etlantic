# 5–10 Minute Quickstart

> **Status: Available in ETLantic 0.23.0.** Use `etlantic init` for the
> recommended CLI-first path with durable reports and declarative assets.

## 1. Install

ETLantic requires Python 3.11 or newer. Prefer `python -m` so PATH issues do not
block you.

```bash
python -m pip install 'etlantic==0.23.0'
python -m etlantic --version
```

## 2. Initialize a project

`init` requires an **empty directory** (or pass `--force`):

```bash
mkdir my-pipeline && cd my-pipeline
python -m etlantic init --with-toml
```

This creates `pipeline.py` (`SamplePipeline`), `profiles/development.json`,
sample `data/sample.json`, and `.etlantic/` workspace directories.

## 3. Validate, plan, and run

```bash
python -m etlantic doctor --profile development
python -m etlantic inspect pipeline.py:SamplePipeline
python -m etlantic validate pipeline.py:SamplePipeline --profile development
python -m etlantic plan pipeline.py:SamplePipeline --profile development
python -m etlantic run pipeline.py:SamplePipeline --profile development
python -m etlantic report list
```

No Python-side `runtime.memory.seed()` is required: the generated profile maps
assets to `json://data/...` paths.

### What success looks like

- `doctor` exits 0 with no blocking issues.
- `validate` / `plan` print a report with no errors (JSON with `--format json`).
- `run` prints a run status of **`succeeded`**.
- `report list` shows at least one durable report under `.etlantic/`.

Inspect the written asset:

```bash
cat data/out.json
```

Expected shape (identity transform on sample rows):

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

This first run proves plumbing with an identity transform. **Next:** change the
transform so names become uppercase (or add a field) in
[First Pipeline](FIRST_PIPELINE.md)—that is where the product value shows up.

## 4. Python SDK path (optional)

From the same project directory:

```python
from pipeline import SamplePipeline

report = SamplePipeline.validate(profile="development")
report.raise_for_errors()
SamplePipeline.plan(profile="development")
SamplePipeline.run(profile="development")
```

## Next steps

- [First Pipeline](FIRST_PIPELINE.md) — evolve contracts, intentional errors,
  richer transforms
- [Engine selection](ENGINE_SELECTION.md) — add Polars, Pandas, SQL, or Spark
- [Installation](INSTALLATION.md) — optional engine packages
