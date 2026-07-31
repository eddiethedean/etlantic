# etlantic-s3 (Experimental / Preview)

S3-compatible object-store connector for [ETLantic](https://github.com/eddiethedean/etlantic).

**Current release:** 0.38.0.

**Maturity:** Experimental (Alpha classifier). Fake/stub mode is the supported CI
path today. Live AWS opt-in lands later behind the `aws` extra and an explicit
profile allowlist — do not treat this package as production-ready.

Payload format today is **JSON** (not Parquet). Fake multipart staging buffers
records and serializes once at prepare/commit.

## Install

```bash
pip install 'etlantic-s3==0.38.0'
# Live AWS (opt-in later; not required for CI):
# pip install "etlantic-s3[aws]==0.38.0"
```

Core dependency: `etlantic>=0.38.0,<0.39`. Optional: `boto3`, `pyarrow`.

## Behavior

- Without `boto3`, factories use `InMemoryS3Fake` (multipart abort + conditional
  commit-pointer semantics).
- Immutable data objects; readers resolve only committed pointers.
- Overwrite/append replace the commit pointer; create/first-write modes keep
  conditional create (`If-None-Match`).
- Publication evidence carries ETag / operation metadata without secret endpoints.

## Entry points

| Group | Name | Factory |
|---|---|---|
| `etlantic.source_connectors` | `s3` | `etlantic_s3:create_source` |
| `etlantic.sink_connectors` | `s3` | `etlantic_s3:create_sink` |
| `etlantic.storage_connectors` | `s3` | `etlantic_s3:create_storage` |

## Links

[Source](https://github.com/eddiethedean/etlantic/tree/main/packages/etlantic-s3) ·
[Issues](https://github.com/eddiethedean/etlantic/issues)
