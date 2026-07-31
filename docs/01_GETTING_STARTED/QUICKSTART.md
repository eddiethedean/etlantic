# Quickstart

> **Status: Available in ETLantic 0.40.0.** Use `python -m etlantic init` for the
> recommended CLI-first path with durable reports and declarative assets.
> Budget ~5–10 minutes for first success; optional validation aha below adds a
> few minutes.

!!! tip "PyPI vs clone"
    This page is for **PyPI installs**. Repository `examples/` scripts need a
    git checkout and `uv` — see [Installation](INSTALLATION.md).

## 1. Install

ETLantic requires Python 3.11 or newer. Prefer `python -m` so PATH issues do not
block you. See [Installation](INSTALLATION.md) for full options.

**Unix / macOS:**

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install 'etlantic==0.40.0'
python -m etlantic --version   # expect 0.40.0
```

**Windows (PowerShell):**

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
py -3.11 -m pip install --upgrade pip
py -3.11 -m pip install 'etlantic==0.40.0'
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

## 4. Optional — see validation catch a bug {#required-aha}

Skip if you only want the five-minute green path; return here when you want
to feel validate-before-write.

The `etlantic init` scaffold defines `Identity` **in** `pipeline.py` (it is not
imported from `etlantic`). Edit only the `Load` annotation so the load expects
a different contract than the upstream step produces.

**Before** (generated):

```python
from etlantic import Data, Extract, Input, Load, Output, Pipeline, Transformation


class Row(Data):
    id: int
    name: str


class Identity(Transformation):
    rows: Input[Row]
    result: Output[Row]


@Identity.implementation("local")
def identity_local(rows: list[Row]) -> list[Row]:
    return list(rows)


class SamplePipeline(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    step = Identity.step(rows=raw)
    out: Load[Row] = Load(input=step.result, asset="out")
```

**After** (broken on purpose — add `Other` and change only the `Load` line):

```python
from etlantic import Data, Extract, Input, Load, Output, Pipeline, Transformation


class Row(Data):
    id: int
    name: str


class Other(Data):
    id: int
    name: str


class Identity(Transformation):
    rows: Input[Row]
    result: Output[Row]


@Identity.implementation("local")
def identity_local(rows: list[Row]) -> list[Row]:
    return list(rows)


class SamplePipeline(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    step = Identity.step(rows=raw)
    # Broken: Load expects Other but step.result is still Row
    out: Load[Other] = Load(input=step.result, asset="out")
```

Optional equivalent as a unified diff (same scaffold imports):

```diff
 class Row(Data):
     id: int
     name: str


+class Other(Data):
+    id: int
+    name: str
+
+
 class Identity(Transformation):
     rows: Input[Row]
     result: Output[Row]
@@
     step = Identity.step(rows=raw)
-    out: Load[Row] = Load(input=step.result, asset="out")
+    out: Load[Other] = Load(input=step.result, asset="out")
```

Re-validate:

```bash
python -m etlantic validate pipeline.py:SamplePipeline --profile development
```

Expect a **non-zero** exit and a wiring diagnostic such as:

```text
PMPIPE210: The step "out" expects Other on "input", but received Row from "step.result".
```

`data/out.json` must not gain a new successful write until you restore
`Load[Row]`. That is the product promise: validate before write.

Restore `out: Load[Row] = Load(input=step.result, asset="out")` (and remove
`Other` if unused). Continue with an intentional uppercase transform in
[First Pipeline](FIRST_PIPELINE.md)—you can skip the wiring demo there if you
just completed this step.

## 5. Python SDK path (optional)

From the **same project directory** created by `init` (so `pipeline.py` is
importable as a top-level module):

```python
from pipeline import SamplePipeline

report = SamplePipeline.validate(profile="development")
report.raise_for_errors()
SamplePipeline.run(profile="development")
```

If you see `ModuleNotFoundError: pipeline`, `cd` into the init project root
(the directory that contains `pipeline.py`) and retry.

Standards acronyms ([ODCS](../03_DATA_CONTRACTS/ODCS.md) / [DTCS](../04_TRANSFORMATIONS/DTCS.md) / [DPCS](../05_PIPELINES/DPCS.md)) and Gate A/B labels appear later in
Capabilities and Foundations—you do not need them for first success.
