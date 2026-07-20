# Command-Line Interface

> **Status: Available in ETLantic 0.21.0.** This page documents the commands
> implemented by the installed package.

```bash
etlantic --help
etlantic --version
```

Pipeline targets use `package.module:PipelineClass` or
`path/to/file.py:PipelineClass`.

!!! note "Profile defaults"
    CLI `validate`, `plan`, and `run` default to profile **`local`** when
    `--profile` is omitted. Tutorials use **`development`**. Pass the same
    `--profile` for every command in a workflow (for example
    `--profile development` on validate, plan, and run).

## `validate`

Validate without executing transformation code:

```bash
etlantic validate examples/quickstart.py:CustomerPipeline \
  --profile development
```

Options:

- `--profile`, `-p`: profile name; default `local`
- `--format`: `human`, `json`, or `sarif`
- `--allow-adhoc-profile`: allow unknown bare profile names (default fails
  closed with `PMCFG100`)

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
- `--allow-adhoc-profile`: allow unknown bare profile names (`PMCFG100` otherwise)

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

Validate, plan, and execute with the local runtime. The repository quickstart
requires process-local seeded data, so run its complete companion directly:

```bash
python examples/quickstart.py
```

Running `etlantic run examples/quickstart.py:CustomerPipeline --profile
development` in a fresh process is an expected failure because that CLI process
does not share the companion script's seeded in-memory runtime.

Supported report formats are `text`, `json`, and `html`. Additional options:

- `--run-one NODE`
- `--run-until NODE`
- `--intent INTENT`
- `--no-write`
- `--allow-adhoc-profile`: allow unknown bare profile names (`PMCFG100` otherwise)

CLI runs start with a new process-local runtime. A source that requires seeded
in-memory data is therefore better run through Python, as shown in the
quickstart. For durable JSON/CSV storage, use the
[file-storage tutorial](../06_EXECUTION/FILE_STORAGE_TUTORIAL.md) Python
companion—it registers bindings in-process and is not directly runnable with
`etlantic run` today. Keep pipeline modules import-safe (guard side effects
under `if __name__ == "__main__"`) so `validate` / `plan` do not execute during
import.

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
etlantic plugin list --profile ./profiles/prod.json --format json
etlantic plugin info polars --kind dataframe
```

Supported `--kind` values today: `dataframe`, `sql`, `spark`, `orchestrator`,
`scheduler`, `transform_compiler`.

Production profiles honor `Profile.plugin_allowlist` (fail closed). When trust
diagnostics include severity `error` (for example empty allowlist /
`PMPLUG401`), `plugin list` exits non-zero. `plugin info` accepts `--profile`
and honors the same allowlist.

## `schema`

Subcommands: `inspect`, `check`, `diff`, `history`, `impact`, `acknowledge`,
`propose`, `monitor`. History defaults to `.etlantic/schema-history/` and
stores fingerprints/metadata only—never source rows.

```bash
etlantic schema inspect module:MyContract --format json
etlantic schema check module:MyContract --subject orders --format json
etlantic schema diff PREV CURRENT --format json
etlantic schema history orders --format json
etlantic schema impact PREV CURRENT --format json
etlantic schema propose module:MyContract --subject orders
etlantic schema monitor module:MyContract --subject orders
etlantic schema acknowledge orders --note "accepted additive column"
```

`propose` records a candidate observation without mutating contracts.
`monitor` writes an observation into file history. `acknowledge` accepts a
known drift subject for subsequent checks.

## `reliability`

Subcommands: `freshness`, `partition-check`, `repair-explain`,
`backfill-preview`, `reconcile`, `plan-diff`, `env-diff`, `quality-trends`.
These are local ops helpers—not a managed reliability product.

```bash
etlantic reliability freshness orders --max-age 3600 --observed-age 120
etlantic reliability partition-check orders --keys dt,region --count 24 --minimum-count 24
etlantic reliability reconcile orders --left 100 --right 100
etlantic reliability plan-diff PREV.json CURRENT.json
etlantic reliability env-diff LEFT.json RIGHT.json
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

## Exit codes

| Code | Typical meaning |
|---|---|
| `0` | Success (validate/plan valid; run succeeded; diff non-breaking) |
| `1` | Validation/trust failure, run not succeeded, compile/plugin error, or breaking schema impact |

Exact meaning depends on the subcommand. Prefer `--format json` / SARIF in CI
and gate on `valid` / diagnostic severity rather than inventing additional
exit-code semantics.

## Mutations

| Command | Mutates workspace? |
|---|---|
| `validate`, `inspect`, `plan`, `diff`, `plugin`, `viz` | No (read-only analysis) |
| `generate` | Writes contract files to `-o` / output directory |
| `compile` | Writes orchestrator artifacts to `-o` |
| `run` | Executes pipeline side effects via bound storage |
| `schema monitor` / `acknowledge` | Writes schema history under `.etlantic/schema-history/` |
| `report export` | Writes the chosen `--output` file |

Never pass secret values on the CLI. Profiles and plans must keep secret
material as references only.
