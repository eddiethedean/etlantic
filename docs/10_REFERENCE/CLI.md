# Command-Line Interface

> **Status: Available in ETLantic 0.14.0.** This page documents the commands
> implemented by the installed package.

```bash
etlantic --help
etlantic --version
```

Pipeline targets use `package.module:PipelineClass` or
`path/to/file.py:PipelineClass`.

## `validate`

Validate without executing transformation code:

```bash
etlantic validate examples/quickstart.py:CustomerPipeline \
  --profile development
```

Options:

- `--profile`, `-p`: profile name; default `local`
- `--format`: `human`, `json`, or `sarif`

Exit status is 0 for a valid pipeline and 1 for validation errors.

## `inspect`

Print the logical pipeline graph:

```bash
etlantic inspect examples/quickstart.py:CustomerPipeline
etlantic inspect examples/quickstart.py:CustomerPipeline --format json
```

## `plan`

Resolve a deterministic `PipelinePlan`:

```bash
etlantic plan examples/quickstart.py:CustomerPipeline \
  --profile development
```

The default output format is JSON. Selection options are:

- `--run-one NODE`
- `--run-until NODE`
- `--nodes NAME,NAME`

`--run-one` and `--run-until` are mutually exclusive.

Explain resolution decisions with either form:

```bash
etlantic plan explain examples/quickstart.py:CustomerPipeline \
  --profile development

etlantic plan examples/quickstart.py:CustomerPipeline \
  --profile development --explain
```

Explain output includes bindings, implementations, capability decisions, and
(when selected) portable `implementation_kind`, `ir_fingerprint`, and compiler
identity for Polars kernel compilation.

## `run`

Validate, plan, and execute with the local runtime:

```bash
etlantic run examples/quickstart.py:CustomerPipeline \
  --profile development
```

Supported report formats are `text`, `json`, and `html`. Additional options:

- `--run-one NODE`
- `--run-until NODE`
- `--intent INTENT`
- `--no-write`

CLI runs start with a new process-local runtime. A source that requires seeded
in-memory data is therefore better run through Python, as shown in the
quickstart. Use JSON, CSV, callable bindings, or application-owned runtime
setup for CLI execution. The
[file-storage tutorial](../06_EXECUTION/FILE_STORAGE_TUTORIAL.md) provides a
complete CLI-runnable example.

## `compile`

Compile a planned pipeline to an external orchestrator artifact
(requires the matching plugin, e.g. `etlantic-airflow`):

```bash
etlantic compile examples/quickstart.py:CustomerPipeline \
  --target airflow -o dags/ --profile development
```

## `generate`

Generate ODCS/DTCS/DPCS contract bundles:

```bash
etlantic generate examples/quickstart.py:CustomerPipeline -o contracts/
etlantic generate examples/quickstart.py:CustomerPipeline --sqlmodel
```

`--sqlmodel` requires `etlantic-sqlmodel`.

## `diff`

Diff data contracts, transformations, or pipelines:

```bash
etlantic diff PREV CURRENT --kind pipeline --format json
etlantic diff PREV CURRENT --kind data --format sarif
```

## `plugin`

```bash
etlantic plugin list --profile production --format json
etlantic plugin info polars --kind dataframe
```

Supported `--kind` values today: `dataframe`, `sql`, `spark`, `orchestrator`.
Transform compilers discovered under `etlantic.transform_compilers` are not yet
listed by this CLI—inspect them in Python via
`etlantic.transform.discovery.discover_transform_compilers()`.

Production profiles honor `Profile.plugin_allowlist` (fail closed). When trust
diagnostics include severity `error` (for example empty allowlist /
`PMPLUG401`), `plugin list` exits non-zero.

## `schema`

Schema inspect / check / diff / history / impact / acknowledge / propose /
monitor. History defaults to `.etlantic/schema-history/` and never stores
source rows.

```bash
etlantic schema inspect module:MyContract --format json
etlantic schema monitor module:MyContract --subject orders
etlantic schema acknowledge orders --note "accepted additive column"
```

## `reliability`

Ops helpers for freshness, partition checks, repair explanation, backfill
preview, reconciliation, plan/env diff, and quality trends.

```bash
etlantic reliability freshness orders --max-age 3600 --observed-age 120
etlantic reliability reconcile orders --left 100 --right 100
```

## `viz`

```bash
etlantic viz dot examples/quickstart.py:CustomerPipeline -o pipeline.dot
etlantic viz html examples/quickstart.py:CustomerPipeline -o lineage.html
etlantic viz lineage examples/quickstart.py:CustomerPipeline --format json
```

## `report`

```bash
etlantic report show RUN_ID --format text
etlantic report export RUN_ID --format json --output report.json
etlantic report compare LEFT RIGHT --store .etlantic/reports
```

`show` and `export` read the **process-local** CLI runtime store created in the
same Python process. A separate `etlantic run` invocation cannot see that
report. Persist across processes with a Python `FileReportStore` on
`PipelineRuntime(reports=...)`, or use `report compare --store` against a file
store root that your application already wrote.
