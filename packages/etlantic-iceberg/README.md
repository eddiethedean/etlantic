# etlantic-iceberg (Experimental)

Apache Iceberg connector for [ETLantic](https://github.com/eddiethedean/etlantic)
via PyIceberg.

**Current release:** 0.38.0.

**Maturity:** Experimental (Alpha classifier). CI uses an in-memory fake catalog;
live PyIceberg is optional (`pip install "etlantic-iceberg[pyiceberg]"`).

Iceberg **snapshot id** is the publication identity on `CommitReceipt`.

Advertised sink modes today: **append** and **overwrite**.
`write.partition_replace` is **not** claimed until partition-scoped replace is real.

## Install

```bash
pip install 'etlantic-iceberg==0.38.0'
```

Core dependency: `etlantic>=0.38.0,<0.39`.

## Entry points

| Group | Name | Factory |
|---|---|---|
| `etlantic.source_connectors` | `iceberg` | `etlantic_iceberg:create_source` |
| `etlantic.sink_connectors` | `iceberg` | `etlantic_iceberg:create_sink` |
| `etlantic.storage_connectors` | `iceberg` | `etlantic_iceberg:create_storage` |

## Links

[Source](https://github.com/eddiethedean/etlantic/tree/main/packages/etlantic-iceberg) ·
[Issues](https://github.com/eddiethedean/etlantic/issues)
