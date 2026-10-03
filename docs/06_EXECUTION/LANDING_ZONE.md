# Landing-Zone File Connector

> **Status: ETLantic 0.55.0 Beta release (Preview).** Built-in `local-files`
> source connector for directory/glob CSV landing zones in snapshot and
> incremental modes. Continuous directory watching is **not** in core — compose
> a submitter outside `src/etlantic/` (0.39+).

Landing is **not** an extension of `CsvStorage`. Single-file CSV/JSON bindings
vs landing vs experimental cloud connectors:
[Storage today](STORAGE_TODAY.md).

## Modes

| Mode | Behavior |
|---|---|
| `snapshot` | Read all matching files for this run |
| `incremental` | Read only identities not yet committed in the landing ledger |
| continuous (submitter) | External poller/watch posts durable run accepts — **not** an Extract kind |

Switch `snapshot` / `incremental` on the **profile binding** — do not rewrite
`Extract` topology.

## CSV parsing

Parsing is explicit and deterministic: `encoding` defaults to `utf-8` and
supports `utf-8-sig`, `latin-1`, and `cp1252`; `delimiter` defaults to comma and
supports semicolon, tab, or pipe. Both values are recorded in the source plan;
the connector does not guess from file contents. Headers must be non-empty and
unique, every row must match the header width, and malformed quoting, decoding,
or contract values fail the read. File-count, per-file byte, total-byte, and row
limits apply before records are returned. The connector hashes each selected
file and verifies its identity again before parsing it.

The directory/glob connector records selection intent and resolves matching
files when the worker runs. It is useful for controlled landing zones; it does
not provide the owner-scoped immutable upload reference and retention lease
required by managed CSV upload workflows.

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
            "encoding": "utf-8",
            "delimiter": ",",
        },
        "curated": "memory://curated",
    },
    safe_io={"approved_roots": ["/path/to/workspace"]},
)
```

## Checkpoint

Checkpoint schema id: `etlantic.landing_checkpoint/1` (fingerprints/metadata
only — no rows, credentials, or absolute host paths).

- **Plan:** identity scheme + listing intent (`root_ref`, glob, mode)
- **Runtime:** `LandingReadManifest` with concrete identities after read

## Continuous = submitter outside core

Continuous watching must **not** live under `src/etlantic/`. Use
`etlantic_fastapi.landing_sensor.LandingWatchSubmitter` (stdlib polling; no
`watchdog` required) or the clone example:

```bash
# requires etlantic-fastapi and a running CP1 app
uv run python examples/landing_zone_watch_submitter.py \
  --watch ./inbox --definition landing_pipe --base-url http://127.0.0.1:8000
```

Submitters call durable `POST /v1/definitions/{id}/runs` with `local-files`
binding refs (`root_ref`, `glob`, `mode`, …). Never embed file bytes in plans or
submit bodies. See [Embeddable HTTP API](CONTROL_PLANE.md).

## Cloud profile swap

The same logical pipeline can swap storage/source bindings to Experimental
`s3` / `snowflake` / `iceberg` providers without changing graph topology.
See [Connector SDK](../07_PLUGIN_SDK/CONNECTOR_SDK.md) and
[What's New in 0.39](../01_GETTING_STARTED/WHATS_NEW_0_39.md).

## Related

- [Storage today](STORAGE_TODAY.md)
- [Embeddable HTTP API](CONTROL_PLANE.md)
- [Storage plugins](STORAGE_PLUGINS.md)
- [Landing-zone plan](../11_DEVELOPMENT/LANDING_ZONE_CONNECTOR_PLAN.md)
- [ADR-015](../11_DEVELOPMENT/adr/ADR-015-CONNECTOR-PROTOCOLS.md)
- Example: [`examples/landing_zone_watch_submitter.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/landing_zone_watch_submitter.py)
