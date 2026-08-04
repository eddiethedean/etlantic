# etlantic-snowflake (Experimental)

Native Snowflake connector for
[ETLantic](https://github.com/eddiethedean/etlantic) **0.43**. Install when
pipelines need Experimental `snowflake` source/sink/storage connectors. CI
uses an in-memory fake; live Snowflake is optional. Pin with core.

**Maturity:** Experimental (Alpha classifier). Fake path uses
`autocommit=False` transactional semantics and `query_id` evidence on
`CommitReceipt`.

## Install

```bash
pip install 'etlantic-snowflake==0.43.0'
# Live Snowflake (optional):
# pip install 'etlantic-snowflake[snowflake]==0.43.0'
# pip install 'etlantic==0.43.0'
```

Core dependency: `etlantic>=0.43.0,<0.44`.

## Entry points

| Group | Name | Factory |
|---|---|---|
| `etlantic.source_connectors` | `snowflake` | `etlantic_snowflake:create_source` |
| `etlantic.sink_connectors` | `snowflake` | `etlantic_snowflake:create_sink` |
| `etlantic.storage_connectors` | `snowflake` | `etlantic_snowflake:create_storage` |

## Links

[Source](https://github.com/eddiethedean/etlantic/tree/main/packages/etlantic-snowflake) ·
[Issues](https://github.com/eddiethedean/etlantic/issues)
