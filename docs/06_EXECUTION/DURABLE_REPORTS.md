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

## Managed artifact workspaces

Managed resume and checkpoint-backed repair can use their parent's artifact
workspace while retaining a distinct child run ID. Their reports record the
storage run ID in `etlantic.control_plane.artifact_storage_run_id` before the
first durable report write, including the result-publication fallback. Chained
resumes preserve that workspace identity. Listing, download, and artifact
retention resolve the same workspace inside the accepted tenant, workspace,
and security domain; the metadata contains no filesystem path or credentials.

Artifact retention expires each report's references separately from its run
status. A file shared with a still-retained report remains on disk until its
last retained reference expires. An expired reference cannot download that
file, even while another report retains it. Cleanup continues to limit the
number of artifacts touched per pass and records failures for later retry.
Deferred reports receive a retry time before batch selection, and already
expired pinned references do not hide unfinished or unrelated cleanup work.
A process-owned filesystem lock coordinates execution and result publication
with cleanup for each artifact workspace. Cleanup skips a busy workspace and
refreshes its scoped report inventory under the lock, including file providers
opened before another worker published a child. Workers sharing artifact files
must use the same artifact root; independent workspaces still execute in parallel.
Result reconciliation also skips busy workspaces, leaving their publication
records pending while the worker processes other publications and accepted runs.

Before report persistence, execution records hashed artifact ownership under the
workspace. An unexpired child remains visible to cleanup even while its result
exists only in durable publication. Cleanup keeps deferred physical work pending
until that child is published or its retention window ends, including across
restarts, so an unavailable report provider cannot cause either early deletion
or a permanent file leak. Cleanup discovers ownership records directly inside
the accepted artifact scope, including workspaces with no published report rows.
Unpublished cleanup shares the artifact batch limit and persists progress for
restart and deletion-failure recovery.
Result reconciliation preserves cleanup progress from the current report row;
reference tombstones alone never prove that deferred file deletion completed.

Reference expiry also writes a hashed tombstone under the artifact workspace.
Queries and result reconciliation consult this record, so an immutable fallback
snapshot cannot revive an expired reference during a report-provider outage.
Expired unpublished owners receive tombstones even when no stored report needs
file cleanup. Ownership and tombstone writes use the workspace's process-owned
lock, without additional lock files that could block recovery after a crash.
These small metadata records survive process restarts and remain with retained
report history; they contain neither source rows nor credentials.

Managed cleanup resolves untagged legacy reports from their accepted submission.
It retries references incorrectly marked expired or complete by the old child-
workspace cleanup. The packaged backend supplies this resolver automatically;
standalone cleanup callers can supply `report_resolver`, and execution hosts
resolve legacy final reports through their recorded submission ID. Unverifiable
legacy lifecycle reports fail closed. Ordinary legacy reports retain their own
workspace, and managed queries recover their storage tag from accepted evidence.

## CLI process boundaries

Use `--ephemeral` when you intentionally want process-local report storage
(0.20 behavior). Otherwise `report show`, `export`, and `list` read from
`.etlantic/reports/` automatically.

## Compare persisted reports

The Python comparison helper reports status, step-status, plan-fingerprint,
and artifact-count differences:

```python
from etlantic.reports import FileReportStore, compare_reports

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
