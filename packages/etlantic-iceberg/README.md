# etlantic-iceberg (Experimental)

Apache Iceberg connector for [ETLantic](https://github.com/eddiethedean/etlantic)
via PyIceberg.

**Maturity:** Experimental (Alpha classifier). CI uses an in-memory fake catalog;
live PyIceberg is optional (`pip install "etlantic-iceberg[pyiceberg]"`).

Iceberg **snapshot id** is the publication identity on `CommitReceipt`.

## Install

```bash
pip install etlantic-iceberg
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
