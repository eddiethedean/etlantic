# Command-Line Interface

> **Status: Available in Pipelantic 0.6.0.** This page documents the commands
> implemented by the installed package.

```bash
pipelantic --help
pipelantic --version
```

Pipeline targets use `package.module:PipelineClass` or
`path/to/file.py:PipelineClass`.

## `validate`

Validate without executing transformation code:

```bash
pipelantic validate examples/quickstart.py:CustomerPipeline \
  --profile development
```

Options:

- `--profile`, `-p`: profile name; default `local`
- `--format`: `human` or `json`

Exit status is 0 for a valid pipeline and 1 for validation errors.

## `inspect`

Print the logical pipeline graph:

```bash
pipelantic inspect examples/quickstart.py:CustomerPipeline
pipelantic inspect examples/quickstart.py:CustomerPipeline --format json
```

## `plan`

Resolve a deterministic `PipelinePlan`:

```bash
pipelantic plan examples/quickstart.py:CustomerPipeline \
  --profile development
```

The default output format is JSON. Selection options are:

- `--run-one NODE`
- `--run-until NODE`
- `--nodes NAME,NAME`

`--run-one` and `--run-until` are mutually exclusive.

Explain resolution decisions with either form:

```bash
pipelantic plan explain examples/quickstart.py:CustomerPipeline \
  --profile development

pipelantic plan examples/quickstart.py:CustomerPipeline \
  --profile development --explain
```

## `run`

Validate, plan, and execute with the local runtime:

```bash
pipelantic run examples/quickstart.py:CustomerPipeline \
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
setup for CLI execution.

## `report`

```bash
pipelantic report show RUN_ID --format text
pipelantic report export RUN_ID --format json --output report.json
```

The built-in CLI report store is process-local. A report created by a previous
CLI process is not available to a new invocation.

## Commands not included in 0.4

`init`, `compile`, `generate`, `graph`, `plugins`, and `config` are future CLI
designs. Do not depend on them until they appear in this current-version
reference and in `pipelantic --help`.
