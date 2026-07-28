# Command-Line Interface

> **Status: Available in ETLantic 0.26.0.** This page documents the commands
> implemented by the installed package.

```bash
python -m etlantic --help
python -m etlantic --version
```

Pipeline targets use `package.module:PipelineClass`,
`path/to/file.py:PipelineClass`, **or** a path to an
`etlantic.pipeline/1` JSON document. Prefer `python -m etlantic` so the active
interpreter is used.

## Global options

| Option | Purpose |
|---|---|
| `--workspace PATH` | Project/workspace root (default: cwd or `etlantic.toml` parent) |
| `--ephemeral` | Process-local stores instead of durable `.etlantic/` |
| `--profile`, `-p` | Default profile for commands that accept `--profile` |
| `--accept-legacy-bindings` | Allow deprecated profile JSON `bindings` (else `PMCFG111`) |
| `--verbose` / `-v`, `--quiet` / `-q` | Output verbosity |
| `--color` / `--no-color` | Colorized output |
| `--non-interactive` | Do not prompt for confirmation |

!!! note "Profile defaults"
    When `--profile` is omitted, the CLI defaults to **`development`** (or
    `default_profile` from optional `etlantic.toml`). Pass the same
    `--profile` for every command in a workflow.

!!! note "Durable workspace"
    By default the CLI writes run reports to `.etlantic/reports/` and uses
    `.etlantic/artifacts/` for durable materialization. Pass `--ephemeral`
    for process-local stores (0.20 behavior).

## Pipeline targets

| Form | Example | Notes |
|---|---|---|
| Module path | `pkg.mod:MyPipeline` | Importable class |
| File path | `pipeline.py:SamplePipeline` | Import-safe module |
| Definition JSON | `pipeline.json` | `etlantic.pipeline/1` document |

JSON targets load via `read_pipeline_json` (no code execution during decode).
`validate` and `plan` accept definition JSON. `run` of a definition still
needs live callables registered in-process (see
[Programmatic authoring](../05_PIPELINES/PROGRAMMATIC_AUTHORING.md)).

```bash
python -m etlantic validate pipeline.json --profile development
python -m etlantic plan pipeline.json --profile development --format json
```

## `init`

Scaffold a minimal import-safe pipeline project:

```bash
python -m etlantic init
python -m etlantic init --directory ./my-pipeline --name SamplePipeline --with-toml
```

Creates `pipeline.py`, `profiles/<profile>.json`, sample JSON under `data/`,
workspace dirs under `.etlantic/`, and optionally `etlantic.toml`.

## `doctor`

Read-only environment, plugin, profile, and workspace checks:

```bash
python -m etlantic doctor --profile development
python -m etlantic doctor pipeline.py:SamplePipeline --format json
```

Exits `0` when checks pass, `16` (`ENVIRONMENT_FAILURE`) when they fail.

## `validate`

Validate without executing transformation code:

```bash
python -m etlantic validate pipeline.py:SamplePipeline --profile development
python -m etlantic validate pipeline.json --profile development
```

!!! note "From a checkout"
    Repository demos such as `examples/memory_customers.py:CustomerPipeline`
    require a git checkout (not on the PyPI wheel). Prefer the init project or
    a definition JSON file for pip-only workflows.

Options:

- `--profile`, `-p`: profile name; default `development`
- `--format`: `human`, `json`, or `sarif`
- `--allow-adhoc-profile`: allow unknown bare profile names (default fails
  closed with `PMCFG100`)

Exit `0` when valid, `10` (`INVALID_MODEL`) on validation errors.

## `inspect`

Print the logical pipeline graph:

```bash
python -m etlantic inspect pipeline.py:SamplePipeline
python -m etlantic inspect pipeline.py:SamplePipeline --format json
```

## `plan`

Resolve a deterministic `PipelinePlan`:

```bash
python -m etlantic plan pipeline.py:SamplePipeline --profile development
python -m etlantic plan pipeline.json --profile development --format json
```

The default output format is JSON. Selection options are:

- `--run-one NODE`
- `--run-until NODE`
- `--nodes NAME,NAME`
- `--allow-adhoc-profile`: allow unknown bare profile names (`PMCFG100` otherwise)

`--run-one` and `--run-until` are mutually exclusive.

Explain resolution decisions with either form:

```bash
python -m etlantic plan explain pipeline.py:SamplePipeline --profile development
python -m etlantic plan pipeline.py:SamplePipeline --profile development --explain
```

Explain output includes bindings, implementations, capability decisions, and
(when selected) portable `implementation_kind`, `ir_fingerprint`, and compiler
identity for Polars kernel compilation.

### `plan diff`

Compare two resolved plans structurally (targets or plan JSON paths):

```bash
python -m etlantic plan diff LEFT RIGHT --profile development --format json
```

Exit `0` when equal, `15` (`BREAKING_CHANGE`) when they differ.

## `profile`

Profile lifecycle helpers:

```bash
python -m etlantic profile validate profiles/development.json
python -m etlantic profile show development --format json
python -m etlantic profile diff LEFT.json RIGHT.json
python -m etlantic profile migrate profiles/legacy.json --write
```

| Subcommand | Purpose |
|---|---|
| `validate` | Schema + semantic checks |
| `show` | Print resolved profile |
| `diff` | Compare two profiles |
| `migrate` | Rewrite legacy `bindings` → `assets` |

## `run`

Validate, plan, and execute with the local runtime:

```bash
python -m etlantic run pipeline.py:SamplePipeline --profile development
python -m etlantic run pipeline.py:SamplePipeline --profile development --preview
```

Supported report formats are `text`, `json`, and `html`. Additional options:

- `--run-one NODE`
- `--run-until NODE`
- `--intent INTENT`
- `--no-write`
- `--preview`: show mutation scope only (no execution)
- `--allow-adhoc-profile`: allow unknown bare profile names (`PMCFG100` otherwise)

Reports are written to `.etlantic/reports/` unless `--ephemeral` is set. Keep
pipeline modules import-safe (guard side effects under
`if __name__ == "__main__"`) so `validate` / `plan` do not execute during
import. In-memory sources that require seeded data still need a Python
companion; file-backed assets (for example `json://data/sample.json` from
`etlantic init`) run directly via CLI.

## `compile`

Compile a planned pipeline to an external orchestrator artifact
(requires the matching plugin, e.g. `etlantic-airflow`):

```bash
python -m etlantic compile pipeline.py:SamplePipeline \
  --target airflow -o dags/ --profile development
python -m etlantic compile pipeline.py:SamplePipeline \
  --target airflow -o dags/ --preview
```

!!! note "From a checkout"
    The repository also ships `examples/memory_customers.py:CustomerPipeline`
    for compile demos; that path is not on the PyPI wheel.

`--preview` shows mutation scope without writing artifacts.

## `generate`

Generate ODCS/DTCS/DPCS contract bundles, or emit a pipeline definition JSON:

```bash
python -m etlantic generate pipeline.py:SamplePipeline -o contracts/
python -m etlantic generate pipeline.py:SamplePipeline --sqlmodel
python -m etlantic generate pipeline.py:SamplePipeline \
  --kind definition -o pipeline.json
```

`--kind definition` writes an `etlantic.pipeline/1` document (Available in
0.24). `--sqlmodel` requires `etlantic-sqlmodel`. Definition kind works from a
class target or an existing definition JSON.

## `diff`

Diff data contracts, transformations, or pipelines:

```bash
python -m etlantic diff PREV CURRENT --kind pipeline --format json
python -m etlantic diff PREV CURRENT --kind data --format sarif
```

## `plugin`

```bash
python -m etlantic plugin list --profile ./profiles/prod.json --format json
python -m etlantic plugin info polars --kind dataframe
python -m etlantic plugin compatibility etlantic-polars --format json
python -m etlantic plugin compatibility --format human
```

Supported `--kind` values today: `dataframe`, `sql`, `spark`, `orchestrator`,
`scheduler`, `transform_compiler`.

`plugin compatibility` evaluates installed plugin packages (static
`etlantic-plugin-manifest.json` plus packaging metadata) against the core
version, protocol ranges, capability vocabulary (`etlantic.capabilities/1`),
plan schema (`etlantic.plan/1`), Requires-Python, the plugin's `etlantic`
pin, and (when `--profile` is given) allowlist status. Pass/fail findings use
`PMPLUG44x` codes. Exit code is non-zero when any plugin fails.

Production profiles honor `Profile.plugin_allowlist` (fail closed). When trust
diagnostics include severity `error` (for example empty allowlist /
`PMPLUG401`), `plugin list` exits non-zero. `plugin info` accepts `--profile`
and honors the same allowlist.

## `schema`

Subcommands: `inspect`, `check`, `diff`, `history`, `impact`, `acknowledge`,
`propose`, `monitor`. History defaults to `.etlantic/schema-history/` and
stores fingerprints/metadata only—never source rows.

```bash
python -m etlantic schema inspect module:MyContract --format json
python -m etlantic schema check module:MyContract --subject orders --format json
python -m etlantic schema diff PREV CURRENT --format json
python -m etlantic schema history orders --format json
python -m etlantic schema impact PREV CURRENT --format json
python -m etlantic schema propose module:MyContract --subject orders
python -m etlantic schema monitor module:MyContract --subject orders
python -m etlantic schema acknowledge orders --note "accepted additive column"
```

`propose` records a candidate observation without mutating contracts.
`monitor` writes an observation into file history. `acknowledge` accepts a
known drift subject for subsequent checks.

## `reliability`

Subcommands: `freshness`, `partition-check`, `repair-explain`,
`backfill-preview`, `reconcile`, `plan-diff`, `env-diff`, `quality-trends`.
These are local ops helpers—not a managed reliability product.

```bash
python -m etlantic reliability freshness orders --max-age 3600 --observed-age 120
python -m etlantic reliability partition-check orders --keys dt,region --count 24 --minimum-count 24
python -m etlantic reliability reconcile orders --left 100 --right 100
python -m etlantic reliability env-diff LEFT.json RIGHT.json
```

`reliability plan-diff` is deprecated; prefer `etlantic plan diff`.

## `viz`

```bash
python -m etlantic viz dot examples/memory_customers.py:CustomerPipeline -o pipeline.dot
python -m etlantic viz html examples/memory_customers.py:CustomerPipeline -o lineage.html
python -m etlantic viz lineage examples/memory_customers.py:CustomerPipeline --format json
```

## `report`

```bash
python -m etlantic report list
python -m etlantic report show RUN_ID --format text
python -m etlantic report export RUN_ID --format json --output report.json
python -m etlantic report compare LEFT RIGHT --store .etlantic/reports
```

By default `list` / `show` / `export` read the durable store at
`.etlantic/reports/` (or under `--workspace`). Separate shell invocations see
the same runs. Pass `--ephemeral` on `run` (and later `report` commands) only
when you intentionally want process-local storage. `report compare --store`
reads an explicit file-store root.

## Exit codes

Documented in `etlantic.cli.exit_codes`:

| Code | Name | Typical meaning |
|---|---|---|
| `0` | `SUCCESS` | Command succeeded |
| `1` | `GENERAL_FAILURE` | Unclassified failure |
| `2` | `USAGE_ERROR` | Bad arguments / usage |
| `10` | `INVALID_MODEL` | Validation or profile model errors |
| `11` | `TRUST_FAILURE` | Plugin trust / allowlist failure |
| `12` | `PLANNING_FAILURE` | Planning failed |
| `13` | `EXECUTION_FAILURE` | Run failed, timed out, or cancelled |
| `14` | `PARTIAL_RUN` | Run completed with partial success |
| `15` | `BREAKING_CHANGE` | Diff / impact / plan-diff breaking |
| `16` | `ENVIRONMENT_FAILURE` | Doctor / environment / missing tooling |

Prefer `--format json` / SARIF in CI and gate on `valid` / diagnostic severity
in addition to exit codes.

## Mutations

| Command | Mutates workspace? |
|---|---|
| `validate`, `inspect`, `plan`, `diff`, `plugin`, `viz`, `doctor` | No (read-only analysis) |
| `init` | Writes scaffold files and `.etlantic/` layout |
| `generate` | Writes contract files to `-o` / output directory |
| `compile` | Writes orchestrator artifacts to `-o` (unless `--preview`) |
| `run` | Executes pipeline side effects; writes `.etlantic/reports/` (unless `--ephemeral` / `--preview`) |
| `profile migrate --write` | Rewrites profile JSON |
| `schema monitor` / `acknowledge` | Writes schema history under `.etlantic/schema-history/` |
| `report export` | Writes the chosen `--output` file |

Never pass secret values on the CLI. Profiles and plans must keep secret
material as references only.
