# Connector SDK

> **Status: Available in ETLantic 0.42.0.** Public source, sink, and storage
> connector protocols under `etlantic.connectors`.

## Protocols

| Family | Protocol id | Entry-point group |
|---|---|---|
| Source | `etlantic.source/1` | `etlantic.source_connectors` |
| Sink | `etlantic.sink/1` | `etlantic.sink_connectors` |
| Storage | `etlantic.storage/1` | `etlantic.storage_connectors` |

Import the public package:

```python
import etlantic as etl
from etlantic.connectors import (
    SourceConnector,
    SinkConnector,
    StorageConnector,
    create_local_files_source,
)
```

## Capability vocabulary

Advertise only frozen tokens (see
[ADR-015](../11_DEVELOPMENT/adr/ADR-015-CONNECTOR-PROTOCOLS.md)). Landing-zone
tokens include `source.batch_snapshot`, `source.incremental_cursor`,
`source.file_glob`, `format.csv`, `idempotency`, and `cleanup`.

## Authoring shape

Keep `Extract` / `Load` topology stable. Swap providers and modes on the
profile:

```python
from etlantic import Profile

Profile(
    name="landing-dev",
    assets={
        "orders": {
            "provider": "local-files",
            "format": "csv",
            "root": "inbox",
            "root_ref": "landing",
            "glob": "*.csv",
            "mode": "snapshot",  # or incremental + checkpoint
        },
        "curated": "memory://curated",
    },
)
```

Static plans record identity **scheme** only — never a live file list.
Runtime evidence uses `LandingReadManifest`.

## Conformance

```bash
# Public fake suite (first-party + optional packages)
python scripts/check_connector_conformance.py --fake

# From application code
from etlantic.testing import run_source_connector_conformance_suite
```

## Reference providers

| Provider | Package | Maturity |
|---|---|---|
| `local-files` | built-in | Preview |
| `s3` | `etlantic-s3` | Experimental |
| `iceberg` | `etlantic-iceberg` | Experimental |
| `snowflake` | `etlantic-snowflake` | Experimental |
| `postgresql` | `etlantic-sql` | Experimental connector path |

See [Landing-zone guide](../06_EXECUTION/LANDING_ZONE.md) and the
[capability matrix](../11_DEVELOPMENT/CONNECTOR_CAPABILITY_MATRIX_0_38.json).

## Related

- [Building a plugin](BUILDING_A_PLUGIN.md)
- [Storage plugin](STORAGE_PLUGIN.md)
- [Testing plugins](TESTING_PLUGINS.md)
- [Capability vocabulary](CAPABILITY_VOCABULARY.md)
- [What's New in 0.39](../01_GETTING_STARTED/WHATS_NEW_0_39.md)
