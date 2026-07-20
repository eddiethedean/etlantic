# Durable Run Reports

As of **0.21.0**, the CLI uses a durable `FileReportStore` at
`.etlantic/reports/` by default. Pass `--ephemeral` for process-local behavior.

## CLI (default durable path)

```bash
etlantic run pipeline.py:SamplePipeline --profile development
etlantic report list
etlantic report show <run_id>
```

Reports survive separate shell invocations without stdout redirection.

## Persist reports during SDK execution

`FileReportStore` is exported from `etlantic.reports`:

```python
from pathlib import Path

from etlantic import PipelineRuntime
from etlantic.reports import FileReportStore
from package.pipeline import CustomerPipeline

store = FileReportStore(Path(".etlantic/reports"))
runtime = PipelineRuntime(reports=store)

report = CustomerPipeline.run(profile="development", runtime=runtime)
assert store.get(report.run_id) is not None
```

The store creates its root directory and writes one JSON file per `run_id`.
On construction it reloads valid `*.json` reports from that directory. Invalid
or unrelated JSON files are skipped. `get()` and `list()` then use the
process-local index populated from disk.

You can also persist a report explicitly:

```python
store.put(report)
recent = store.list(pipeline_id=report.pipeline_id, limit=10)
```

Choose a directory with appropriate access control. Reports are designed to be
secret-free, but they can contain pipeline identities, diagnostics, artifact
references, and operational metadata.

## CLI process boundaries

Use `--ephemeral` when you intentionally want process-local report storage
(0.20 behavior). Otherwise `report show`, `export`, and `list` read from
`.etlantic/reports/` automatically.

## Compare persisted reports

The Python comparison helper reports status, step-status, plan-fingerprint,
and artifact-count differences:

```python
from etlantic.reports.file_store import FileReportStore, compare_reports

store = FileReportStore(".etlantic/reports")
left = store.get("run-left")
right = store.get("run-right")
if left is None or right is None:
    raise LookupError("report not found")

comparison = compare_reports(left, right)
print(comparison)
```

The CLI can compare run IDs from a file store:

```bash
etlantic report compare run-left run-right \
  --store .etlantic/reports --format json
```

It can also compare two report JSON paths without `--store`:

```bash
etlantic report compare reports/before.json reports/after.json --format json
```

See [Run Reports](RUN_REPORTS.md), [Logging](LOGGING.md), and
[Pilot Walkthrough](PILOT_WALKTHROUGH.md).
