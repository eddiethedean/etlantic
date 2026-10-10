# etlantic-foundry

Experimental source, sink and storage connectors for Palantir Foundry Dataset
files. The package uses Foundry's public REST API v2 for paginated file
listing, file content, upload, and transaction create/commit/abort/status.

Install it alongside the matching ETLantic core version:

```bash
pip install 'etlantic-foundry==0.57.1'
```

## Configuration

Supply `base_url`, `dataset_rid`, and `branch_name` in an asset's public
configuration. Put the Foundry bearer token in a runtime secret and bind it
with ETLantic's normal `secret_ref`. Tokens are accepted only as a runtime
`SecretValue`; they are never accepted in configuration or connector plans.

Source bindings also require a committed `transaction_rid`. Source reads are
pinned to that transaction, paginate the file list, verify bounded file sizes,
and parse only CSV, JSON arrays of objects, or JSONL. Defaults cap a read at
1,000 files, 128 MiB total and 100,000 records. Limits can be lowered or raised
within documented package maxima. Formats, encodings and delimiters are
validated before a worker performs I/O.

Sink bindings support three file operations:

- `append` uploads a uniquely named effect file in an `APPEND` transaction.
- `replace` updates the configured `file_path` in an `UPDATE` transaction.
- `snapshot` publishes a uniquely named effect file in a `SNAPSHOT` transaction.

`overwrite` aliases `snapshot`. Foundry is a file provider here: `upsert` and
row-level merge are not advertised. A stable effect path and content digest
allow retries and lost-ack reconciliation to identify committed files. An
unknown outcome stays unknown until the transaction or exact effect file can
be read. Each configuration names its own dataset and branch, so two Foundry
configurations can be scoped independently.

Before a managed transfer writes, the provider resolves the pinned source file
identities and the exact destination file identity. These opaque identities
bind the normalized API origin, dataset, branch and file path without carrying
the bearer token or exposing resource names in execution reports. A match
rejects publication before opening a sink transaction; separate datasets,
branches and files remain distinct.

Storage inspection is read-only and returns CSV column names from one bounded
sample file. It does not provision datasets, branches or files.

## Managed connector actions

`etlantic_foundry.create_action_handlers(resolve_connection, preflight=...,
resolve_preview_resource=...)` provides asynchronous `connector.test` and
`connector.schema.inspect` action handlers for ETLantic's isolated action worker.
`resolve_connection` receives
the worker's trusted `ControlPlaneContext` and an opaque saved connection ID;
it returns the public Foundry binding separately from a runtime context that
contains the resolved `SecretValue`. Action requests never contain credentials.
The test action performs a bounded, read-only schema probe and returns only a
success flag and provider name. Schema inspection returns at most the typed
request's field limit and omits dataset and file names from its receipt.

The optional `preflight` callback receives the trusted context, definition ID,
and revision selector so the deployment can bind it to its own managed
definition and resource services. Register the returned handlers with
`ManagedBackendConfig.action_handlers`; run them using the backend's
`ActionExecutionHost`. Provider exceptions are converted to safe action
failures by that worker. The local Semblance action-worker test covers
connection testing, bounded schema inspection, preflight dispatch, credential
redaction, and the absence of write operations. When
`resolve_preview_resource` is supplied, the factory also registers
`connector.preview`. That callback resolves a trusted connection/resource pair
to one exact file path and pinned transaction. The public Foundry source
connector requires CSV, enforces the requested file-byte ceiling before
downloading, returns a bounded row sample with truncation status, and marks
credential-like column names sensitive for the action worker's redaction pass.

## Provider qualification

Provider qualification uses the local Semblance-backed Foundry API simulator to
verify JSON response schemas, bearer authentication, dataset/branch-scoped file
listing and content, uploads, and transaction commit/reconciliation over
loopback HTTP. The required two-scope and managed-worker pairing campaign also
runs against Semblance; no
live Foundry account, external credentials, or outbound network access is
required. `httpx2.MockTransport` remains useful for isolated timeout and
malformed-response cases.

Run the local simulator suite with `uv run pytest tests/foundry/test_simulator.py`.

The package and entry points remain Experimental until the complete Gate E
simulator-backed matrix, PostgreSQL evidence, and other phase release criteria
are recorded.
