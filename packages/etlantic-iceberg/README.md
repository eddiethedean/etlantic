# etlantic-iceberg (Experimental)


Version **0.44.0** (lockstep with ETLantic core).
Apache Iceberg connector for
[ETLantic](https://github.com/eddiethedean/etlantic) **0.43** via PyIceberg.
Install when pipelines need Experimental `iceberg` source/sink/storage
connectors. CI uses an in-memory fake catalog; live PyIceberg is optional.
Pin with core.

**Maturity:** Experimental (Alpha classifier). Iceberg **snapshot id** is the
publication identity on `CommitReceipt`. Advertised sink modes today:
**append** and **overwrite**. `write.partition_replace` is **not** claimed
until partition-scoped replace is real.

## Install

```bash
pip install 'etlantic-iceberg==0.44.0'
# Optional live PyIceberg:
# pip install 'etlantic-iceberg[pyiceberg]==0.44.0'
# pip install 'etlantic==0.44.0'
```

Core dependency: `etlantic>=0.44.0,<0.45`.

## Entry points

| Group | Name | Factory |
|---|---|---|
| `etlantic.source_connectors` | `iceberg` | `etlantic_iceberg:create_source` |
| `etlantic.sink_connectors` | `iceberg` | `etlantic_iceberg:create_sink` |
| `etlantic.storage_connectors` | `iceberg` | `etlantic_iceberg:create_storage` |

## Links

[Source](https://github.com/eddiethedean/etlantic/tree/main/packages/etlantic-iceberg) ·
[Issues](https://github.com/eddiethedean/etlantic/issues)
