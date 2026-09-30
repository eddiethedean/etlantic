# etlantic-foundry

Experimental live source, sink and storage connectors for Palantir Foundry
Dataset files. The package uses Foundry's public REST API v2 for paginated file
listing, file content, upload, and transaction create/commit/abort/status.

Install it alongside the matching ETLantic core version:

```bash
pip install 'etlantic-foundry==0.55.0'
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

Storage inspection is read-only and returns CSV column names from one bounded
sample file. It does not provision datasets, branches or files.

## Provider qualification

Unit tests use `httpx.MockTransport` and verify the REST contract without a
Foundry tenant. Live provider qualification still requires an isolated account
and dataset with separate read/write scopes, exact Foundry version, overlap,
permission-denial, lost-ack, and reconciliation evidence. The package and
entry points are Experimental until that Gate E evidence is recorded.
