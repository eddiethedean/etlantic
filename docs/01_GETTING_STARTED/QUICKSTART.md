# Quickstart

> **Status: Available in ETLantic 0.27.0.** Use `python -m etlantic init` for the
> recommended CLI-first path with durable reports and declarative assets.
> Budget ~15–20 minutes if you include the required aha step below; first
> validate → run alone is usually under 10 minutes.

!!! tip "PyPI vs clone"
    This page is for **PyPI installs**. Repository `examples/` scripts need a
    git checkout and `uv` — see [Installation](INSTALLATION.md).

## 1. Install

ETLantic requires Python 3.11 or newer. Prefer `python -m` so PATH issues do not
block you.

**Unix / macOS:**

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install 'etlantic==0.27.0'
python -m etlantic --version
```

**Windows (PowerShell):**

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
py -3.11 -m pip install --upgrade pip
py -3.11 -m pip install 'etlantic==0.27.0'
py -3.11 -m etlantic --version
```

## 2. Initialize a project

`init` requires an **empty directory** (or pass `--force` if the directory
already has files, for example a Poetry or uv project):

```bash
mkdir my-pipeline && cd my-pipeline
python -m etlantic init --with-toml
```

`--with-toml` writes a minimal `etlantic.toml` (project name + default profile)
so later CLI invocations resolve project settings without extra flags. You can
omit it for a profile-JSON-only scaffold.

This creates `pipeline.py` (`SamplePipeline`), `profiles/development.json`,
sample `data/sample.json`, and `.etlantic/` workspace directories.

The generated profile uses `dataframe_engine: "local"` — the built-in local
Python runtime (not Polars/Pandas). Add those engines later via
[Engine selection](ENGINE_SELECTION.md).

## 3. Validate and run (first success)

Pipeline **targets** use `path/to/file.py:PipelineClass`,
`package.module:PipelineClass`, or a path to an `etlantic.pipeline/1` JSON
document. See [CLI — Pipeline targets](../10_REFERENCE/CLI.md).

```bash
python -m etlantic validate pipeline.py:SamplePipeline --profile development
python -m etlantic run pipeline.py:SamplePipeline --profile development
cat data/out.json
```

No Python-side seed is required: the generated profile maps assets to
`json://data/...` paths.

### What success looks like

- `validate` exits 0 and prints a report with no errors (add `--format json`
  for machines). Typical text output includes a summary line with **0 errors**.
- `run` prints a run status of **`succeeded`** (look for `status: succeeded` or
  equivalent in the run summary).
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

## 4. Required aha — catch a bad change before write

Do not skip this step (it is outside the “first success” timing above). Edit
`pipeline.py` and change the `Row` contract so `name` becomes `full_name` (or
delete a required field). Re-validate:

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
