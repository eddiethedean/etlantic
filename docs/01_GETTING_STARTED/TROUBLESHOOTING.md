# Troubleshooting

## `pip install etlantic` rejects my Python version

ETLantic requires Python 3.11 or newer. Check with:

```bash
python --version
# Windows:
py -3.11 --version
```

## Installed version is older than the docs

These docs describe ETLantic **0.24.0**. Confirm what you installed:

```bash
python -c "import etlantic; print(etlantic.__version__)"
etlantic --version
# Interpreter-specific (avoids PATH mismatches):
python -m etlantic --version
```

Upgrade from PyPI (pin the published **0.24.0** release for reproducible installs):

```bash
python -m pip install --upgrade 'etlantic==0.24.0'
# or accept compatible 0.24.x patches within the minor:
python -m pip install --upgrade 'etlantic>=0.24.0,<0.25'
```

From a checkout, prefer `uv sync` / `git pull`.

## Wrong interpreter or `etlantic: command not found`

The console script is on PATH only for the environment where you installed
ETLantic. Prefer the module form tied to the active interpreter:

```bash
python -m etlantic --version
# Windows:
py -3.11 -m etlantic --version
```

If that fails with `No module named etlantic`, reinstall into the intended
virtualenv. If `import etlantic` works but `etlantic` on PATH does not, you
are mixing environments.

## CLI validate/plan unexpectedly runs my pipeline

`etlantic` loads `path.py:Class` by importing the module. Keep contracts and
pipeline classes at module scope, but put seed/run side effects under
`if __name__ == "__main__"` so import is safe. See
[Quickstart](QUICKSTART.md).

## Plugin install fails (`etlantic-polars`, `etlantic-pyspark`, …)

Those packages ship with ETLantic 0.24.0 as separate distributions. Keep every
plugin on the same minor as core.

From PyPI:

```bash
python -m pip install --upgrade \
  'etlantic-polars==0.24.0' 'etlantic-pandas==0.24.0'
python -m pip install --upgrade \
  'etlantic-sql==0.24.0' 'etlantic-pyspark==0.24.0'
python -m pip install --upgrade \
  'etlantic-airflow==0.24.0' 'etlantic-prefect==0.24.0'
python -m pip install --upgrade \
  'etlantic-sparkforge==0.24.0'
```

From a checkout:

```bash
uv sync --group dataframes   # polars + pandas
uv sync --group sql
uv sync --group pyspark
uv sync --group airflow
uv sync --group prefect
uv sync --group sparkforge
uv sync --group keyring
uv sync --group sqlmodel
```

Confirm Python is 3.11+ and the package name uses a hyphen
(`etlantic-pyspark`), not an underscore.

## Core and plugin versions do not match

Compare distributions in the same interpreter:

```bash
python -c "import importlib.metadata as m; print(m.version('etlantic')); print(m.version('etlantic-polars'))"
```

Core **0.24.x** requires official plugins from the **same** minor
(`0.24.x`). Do not mix `0.22` plugins with `0.23` core. Remove stale plugin
versions and install matching pins, for example:

```bash
python -m pip install --upgrade --force-reinstall \
  'etlantic==0.24.0' 'etlantic-polars==0.24.0'
```

Use the plugin distribution relevant to your engine in place of
`etlantic-polars`.

## A transformation has no implementation

Declaring a `Transformation` defines its contract, not its executable code.
Either register a native implementation:

```python
@MyTransformation.implementation("local")
def run_locally(rows):
    return rows
```

…or use a shipped portable relational compiler: Polars and PySpark shipped in
0.13, and eager Pandas shipped in 0.14. Author with
`@MyTransformation.portable`, install the matching engine plugin, and select
that engine with `portable_transform_policy="require"`. See
`examples/portable_polars_kernel.py` for the Polars path.

## Portable compiler not discovered / `PMXFORM302`

```bash
python -c "from etlantic.transform.discovery import discover_transform_compilers; print(discover_transform_compilers())"
```

If the map is empty, install a matching `etlantic-polars==0.24.0` into the same
environment as core. Entry-point discovery uses installed distribution
metadata, so reinstall the plugin after editable-install or interpreter
changes. Confirm with:

```bash
python -m pip show etlantic etlantic-polars
python -c "from etlantic.transform.discovery import discover_transform_compilers; print(sorted(discover_transform_compilers()))"
```

## `PMXFORM301` unsupported action or function

`PMXFORM301` means the selected compiler does not support an action, function,
or profile required by that particular plan. In 0.17, relational joins are
graduated across the shipped portable relational compilers, while advanced
window and reshape families are graduated on Polars and PySpark. Conversion
support remains capability-specific. Check the selected plugin's advertised
capabilities; narrow the portable definition, choose a capable engine, add a
native `@implementation(...)`, or use
`portable_transform_policy="prefer"` / `"native"`.

## Diagnostic codes → remediation

| Code | Meaning | Fix |
|---|---|---|
| `PMCFG100` | Unknown bare profile name | Use a built-in template, a JSON path, or `--allow-adhoc-profile` |
| `PMCFG110` / `PMCFG111` | Legacy `bindings`-only profile | Prefer `assets`; `etlantic profile migrate` or `--accept-legacy-bindings` once |
| `PMPLUG401` | Production allowlist empty / plugin not allowed | Set non-empty `plugin_allowlist` with pinned versions; install matching plugins |
| `PMXFORM301` | Portable action unsupported on selected compiler | Narrow portable IR, switch engine, or add `@implementation` |
| `PMEXEC410` | Report persistence failed after publication | Inspect terminal status; recover orphaned writes; do not assume success |
| `PMEXEC412` | Missing callable reader on storage binding | Register a reader or use a supported binding |
| `PMEXEC501` | Unsafe retry after partial write | Fix write mode / idempotency; keep `PMORCH310` compile checks in CI |
| `PMORCH310` | Compile-time unsafe retry/orchestration claim | Adjust orchestration/write semantics before deploy |
| Fingerprint mismatch | Plan digest does not match payload | Regenerate plan after upgrade; do not hand-edit fingerprints |
| Missing wire `schema` | Plan/report lacks `etlantic.plan/1` (etc.) | Regenerate with current CLI/SDK; do not strip `schema` |

Full catalog: [Diagnostics](../10_REFERENCE/DIAGNOSTICS.md).

## Production validation fails with `PMPLUG401`

The built-in `production` profile intentionally has an empty plugin allowlist
and fails closed. Create an explicit production Profile JSON with a non-empty
`plugin_allowlist` containing exact trusted plugin versions such as
`"etlantic-polars": "==0.24.0"`. The allowlist permits discovery; it does not
install plugins or resolve assets. See
[Production profiles](../06_EXECUTION/PRODUCTION_PROFILES.md).

## My memory source returns no records

Seed the exact **asset** name used by the pipeline (`Extract(asset=...)` /
`Load(asset=...)`):

```python
runtime.memory.seed("customer_source", records)
```

Read load output using its asset:

```python
runtime.memory.get("customer_sink")
```

## Unknown profile name fails (`PMCFG100`)

Bare profile names that are not built-in templates fail closed:

```bash
etlantic validate path.py:P --profile typo   # PMCFG100
etlantic validate path.py:P --profile typo --allow-adhoc-profile
```

SDK: `resolve_profile("typo", allow_adhoc_profile=True)`. Prefer an explicit
Profile JSON path for CI.

## Legacy profile `bindings` rejected (`PMCFG111`)

Profile JSON that only has `"bindings"` fails closed with `PMCFG111`. Prefer
`"assets"`. Migrate with `etlantic profile migrate PATH --write`, or load once
with `--accept-legacy-bindings` /
`Profile.from_dict(data, accept_legacy_bindings=True)`.

## Plan fingerprint or schema errors

Persisted plans and run reports must include a wire `"schema"` field
(`etlantic.plan/1` or `etlantic.run_report/1`). Missing or unknown schemas are
rejected. Fingerprints are verified on deserialize (default) and again before
compile/run—regenerate plans after upgrades that change participation rules.
See [Migration 0.18 → 0.19](../11_DEVELOPMENT/MIGRATION_0_18_TO_0_19.md).

## Planning and execution use different profiles

Use one profile name for the whole workflow. The CLI defaults to
`development` when `--profile` is omitted (or `default_profile` from optional
`etlantic.toml`). Pass `--profile` explicitly when you want a different name.

Do not silently switch profile names within one workflow.

## A Pandas, Polars, SQL, Spark, or Airflow example fails

Install the matching plugin and set the corresponding profile engine
(`dataframe_engine`, `sql_engine`, `spark_engine`, or `orchestrator`).

| Need | Install | Example |
|---|---|---|
| Polars portable kernel | `pip install 'etlantic-polars==0.24.0'` or `uv sync --group dataframes` | checkout `examples/portable_polars_kernel.py` |
| Polars / Pandas native | `pip install 'etlantic-polars==0.24.0' 'etlantic-pandas==0.24.0'` or `uv sync --group dataframes` | checkout `examples/dataframe_parity.py` |
| Polars ↔ Pandas Gate A | same as above | checkout `examples/interchange_polars_pandas.py` |
| SQL | `pip install 'etlantic-sql==0.24.0'` or `uv sync --group sql` | checkout `examples/sql_to_sql.py` |
| PySpark | `pip install 'etlantic-pyspark==0.24.0'` or `uv sync --group pyspark` | checkout `examples/pyspark_local.py` |
| Airflow compile | `pip install 'etlantic-airflow==0.24.0'` or `uv sync --group airflow` | checkout `examples/airflow_compile.py` |
| SparkForge adapter | `pip install 'etlantic-sparkforge==0.24.0'` or `uv sync --group sparkforge` | `tests/sparkforge/` |

Airflow compilation is available via `etlantic-airflow`. The shipped
`etlantic-prefect` local MVP is a direct-execution scheduler
(`ExecutionScheduler`), not a DAG compiler. Prefect deployment/serve and
Dagster compilers are not shipped.

## Gate A / Polars ↔ Pandas interchange fails

Gate A (`etlantic.interchange/1`) shipped in **0.18.0** for Polars ↔
Pandas boundaries and remains available in 0.23.

| Symptom | Fix |
|---|---|
| Plugin not discovered | Install `etlantic-polars==0.24.0` **and** `etlantic-pandas==0.24.0`; match core minor |
| Plan fails closed on descriptor / mechanism | Both plugins must advertise compatible `interchange_mechanisms`; see Plugin SDK |
| Expecting PySpark or SQL Gate A | Out of scope — stay on Polars↔Pandas or keep a single engine |
| Treating Arrow helpers as Gate A | Best-effort Arrow conversion is **not** the Gate A contract; use planned descriptors / evidence |
| `examples/interchange_polars_pandas.py` missing | Script is checkout-only; paste from docs or clone the repo |

See [Interchange Gate A FAQ](INTERCHANGE_GATE_A_FAQ.md) and
[Polars ↔ Pandas Interchange](../09_EXAMPLES/INTERCHANGE_POLARS_PANDAS.md).

## PySpark fails before ETLantic executes a step

PySpark requires a compatible Java runtime as well as
`etlantic-pyspark==0.24.0`. Check both from the same environment:

```bash
java -version
python -c "import pyspark; print(pyspark.__version__)"
```

Set `JAVA_HOME` to the supported JDK for your installed PySpark release. A
missing JVM, unsupported Java/PySpark pairing, or Python interpreter mismatch
must be fixed before ETLantic can create a local Spark session.

## SQL reports a missing or invalid connection URL

Install `etlantic-sql==0.24.0`, select `Profile(sql_engine="sql")`, and provide
the URL expected by your binding or example. For the reference PostgreSQL
path:

```bash
export ETLANTIC_SQL_URL='postgresql+psycopg://user:pass@localhost:5432/etlantic'
```

Treat that value as a placeholder and never commit real credentials. SQLite is
demo-only; the PostgreSQL plugin is the reference production path.

## Airflow compiles but the generated DAG does not run

`etlantic compile TARGET --target airflow` validates a plan and emits a DAG
artifact. It does not provision Airflow, install your pipeline and plugin
dependencies into workers, configure connections, or seed runtime data.
Install matching packages in the Airflow runtime and configure its external
resources separately.

## Commands in a design page do not exist

The shipped CLI includes:

`validate`, `inspect`, `plan`, `run`, `compile`, `generate`, `diff`,
`plugin`, `schema`, `reliability`, `viz`, `report`

See the [CLI reference](../10_REFERENCE/CLI.md). Pages marked **Future
design** may show commands that are not shipped—check
[Capabilities](CAPABILITIES.md) first.

## A virtual environment breaks after moving the repository

Virtual-environment entry points contain absolute paths. Delete and recreate
the environment after moving or renaming a checkout:

```bash
rm -rf .venv
uv sync --locked
```

Only run the removal command from the repository root after confirming
`.venv` is the project environment.

## A repository checkout shadows the installed wheel

Python puts the current directory early on `sys.path`. Running from an
ETLantic source checkout can therefore import checkout code instead of the
0.24.0 wheel in your environment. Check the imported path:

```bash
python -c "import etlantic; print(etlantic.__version__); print(etlantic.__file__)"
```

For wheel-user testing, leave the repository directory and run from a clean
project. For contributor testing, use `uv run ...` from the checkout and do
not mix it with a separately installed wheel.

## JSON / PipelineDefinition authoring

### Fingerprint mismatch on load

`etlantic.pipeline/1` documents include a fingerprint. If you hand-edit JSON
and change structure without refreshing the fingerprint, `verify=True` loads
fail closed. Prefer builders / `write_pipeline_json`, or recompute via
`pipeline_fingerprint` / `with_fingerprint` after intentional edits.

### Unsupported schema

Only `etlantic.pipeline/1` is accepted. A different `schema` string raises at
decode time—do not pass plan JSON (`etlantic.plan/1`) to definition loaders.

### Validate/plan works; run fails missing callable

Definitions store implementation **refs**, not live functions. Register before
run:

```python
etl.authoring.callable_registry().register(transformation_id, "local", fn)
```

Class pipelines resolve `@implementation` decorators without this step. See
[Programmatic authoring](../05_PIPELINES/PROGRAMMATIC_AUTHORING.md).

### CLI TARGET vs class

```bash
python -m etlantic validate pipeline.json --profile development
python -m etlantic generate module:MyPipeline --kind definition -o pipeline.json
```

Cross-check diagnostic codes in [Diagnostics](../10_REFERENCE/DIAGNOSTICS.md).

## Where to report a problem

Include the ETLantic version, Python version, command, complete traceback or
diagnostic code, and a minimal pipeline definition in the issue report. Never
include credentials or production data.
