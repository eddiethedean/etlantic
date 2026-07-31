# Landing-Zone File Connector

> **Status: Available in ETLantic 0.38.0 (Preview).** Built-in `local-files`
> source connector for directory/glob CSV landing zones in snapshot and
> incremental modes. Continuous directory watching is **not** in core
> (compose submitters in **0.39+**).

## Modes

| Mode | Behavior |
|---|---|
| `snapshot` | Read all matching files for this run |
| `incremental` | Read only identities not yet committed in the landing ledger |

Switch modes on the **profile binding** — do not rewrite `Extract` topology.

## Profile example

```python
from etlantic import Profile

Profile(
    name="landing",
    assets={
        "landing_csv": {
            "provider": "local-files",
            "format": "csv",
            "root": "inbox",
            "root_ref": "landing",
            "glob": "*.csv",
            "mode": "incremental",
            "consume": "ledger",
            "checkpoint": "landing_csv_checkpoint",
        },
        "curated": "memory://curated",
    },
    safe_io={"approved_roots": ["/path/to/workspace"]},
)
```

Checkpoint schema id: `etlantic.landing_checkpoint/1` (no rows, credentials,
or absolute host paths).

## Plan vs runtime

- **Plan:** identity scheme + listing intent (`root_ref`, glob, mode)
- **Runtime:** `LandingReadManifest` with concrete identities after read

## Cloud profile swap

The same logical pipeline can swap storage/source bindings to Experimental
`s3` / `snowflake` / `iceberg` providers without changing graph topology.
See [Connector SDK](../07_PLUGIN_SDK/CONNECTOR_SDK.md) and
[What's New in 0.38](../01_GETTING_STARTED/WHATS_NEW_0_38.md).

## Related

- [Storage today](STORAGE_TODAY.md)
- [Storage plugins](STORAGE_PLUGINS.md)
- [Landing-zone plan](../11_DEVELOPMENT/LANDING_ZONE_CONNECTOR_PLAN.md)
- [ADR-015](../11_DEVELOPMENT/adr/ADR-015-CONNECTOR-PROTOCOLS.md)
