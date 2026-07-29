# Runtime and reports

## Run modes

Use `intent_from_sparkforge` to convert a legacy mode:

| SparkForge input | ETLantic intent |
|---|---|
| `standard` | `STANDARD` |
| `initial`, `initial_load`, `initialize` | `INITIALIZE` |
| `incremental` | `INCREMENTAL` |
| `full_refresh`, `refresh` | `REFRESH` |
| `validation`, `validation_only`, `validate` | `VALIDATE` |
| `backfill` | `BACKFILL` |
| `replay` | `REPLAY` |

Unknown modes raise `ValueError`.

## Selective execution

```python
from medallantic import debug_request_from_sparkforge

request = debug_request_from_sparkforge(
    mode="incremental",
    run_until="clean_orders",
    skip_writes=True,
    retry={
        "max_attempts": 3,
        "backoff_seconds": 1.0,
        "retry_on": ["TimeoutError"],
    },
    parameter_overrides={
        "clean_orders": {"minimum_date": "2026-01-01"},
    },
)
```

Only one of `run_until`, `run_one`, and `run_from` may be supplied.

`skip_writes=True` sets `RunRequest.no_write`. It does not silently change the
materialization policy. Validation intent also forces no-write behavior.

## Debug session

An adapted pipeline can use ETLantic's debug session:

```python
from medallantic import bind_debug_session

session = bind_debug_session(
    adapted.pipeline_cls,
    profile=adapted.profile,
)
```

Importable transformation references execute through the selected ETLantic
engine and can be debugged through the adapted pipeline. Symbolic legacy names
remain planning-only passthroughs and emit `MDL111`; replace them with
importable references before treating the migration as execution-equivalent.

## Normalize a legacy result

```python
from medallantic import adapt_run_result

report = adapt_run_result(
    {
        "pipeline": "orders",
        "run_id": "legacy-123",
        "mode": "incremental",
        "status": "succeeded",
        "records_in": 100,
        "records_out": 98,
        "steps": [
            {
                "name": "clean_orders",
                "status": "succeeded",
                "records_in": 100,
                "records_out": 98
            }
        ]
    }
)

print(report.to_dict())
```

The adapter normalizes run status, intent, timing, counts, step outcomes,
validations, artifacts/tables, and diagnostics.

Unknown run status fails closed to a failed report and adds diagnostic
`PMSF500`.

## Redaction

Result adaptation recursively redacts recognized secret fields and sensitive
text such as bearer tokens, credentials embedded in URLs/DSNs, and common
key-value secret patterns.

Redaction is defense in depth. Do not place source rows, resolved secrets, raw
credentials, or unbounded backend payloads in the legacy result dictionary.

## SparkForge-shaped explanation

For consumers that still expect a legacy-shaped summary:

```python
from medallantic import report_to_sparkforge_explain

legacy_summary = report_to_sparkforge_explain(report)
```

Use the normalized `PipelineRunReport` as the durable interface. The
SparkForge-shaped explanation exists for migration compatibility.
