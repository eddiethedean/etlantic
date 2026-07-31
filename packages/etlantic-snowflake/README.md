# etlantic-snowflake (Experimental)

Native Snowflake connector for [ETLantic](https://github.com/eddiethedean/etlantic).

**Current release:** 0.38.0.

**Maturity:** Experimental (Alpha classifier). CI uses an in-memory fake with
`autocommit=False` transactional semantics and `query_id` evidence on
`CommitReceipt`. Live Snowflake is optional:

```bash
pip install "etlantic-snowflake[snowflake]==0.38.0"
```

## Install

```bash
pip install 'etlantic-snowflake==0.38.0'
```

Core dependency: `etlantic>=0.38.0,<0.39`.

## Entry points

| Group | Name | Factory |
|---|---|---|
| `etlantic.source_connectors` | `snowflake` | `etlantic_snowflake:create_source` |
| `etlantic.sink_connectors` | `snowflake` | `etlantic_snowflake:create_sink` |
| `etlantic.storage_connectors` | `snowflake` | `etlantic_snowflake:create_storage` |

## Links

[Source](https://github.com/eddiethedean/etlantic/tree/main/packages/etlantic-snowflake) ·
[Issues](https://github.com/eddiethedean/etlantic/issues)
