# Execution and reports

Medallantic lowers medallion intent; ETLantic validates, plans, and coordinates
execution. Runtime plugins perform physical work.

## Validate and plan first

```python
from etlantic.authoring import plan_pipeline_like, validate_pipeline_like

lowered = builder.lower()
definition = builder.build()

validation = validate_pipeline_like(definition, profile=lowered.profile)
validation.raise_for_errors()
plan = plan_pipeline_like(definition, profile=lowered.profile)
```

Planning is secret-free and must not read source rows or load unapproved
plugins.

## Run intent and selection

Migration helpers normalize legacy modes:

```python
from medallantic import debug_request_from_sparkforge

request = debug_request_from_sparkforge(
    mode="incremental",
    run_until="clean_orders",
    skip_writes=True,
)
```

Only one of `run_until`, `run_one`, and `run_from` may be supplied.
`skip_writes=True` produces an explicit no-write request; it does not mutate the
pipeline definition.

## Transform references

Since 0.31, Medallantic executes resolvable `module:attribute` transformation
references through ETLantic's runtime path. Missing or invalid references fail
with diagnostics instead of becoming a production passthrough.

Keep functions import-safe and free of module-import side effects. Secrets and
backend sessions belong in authorized runtime resources, not module globals or
serialized metadata.

## Reports

ETLantic's `PipelineRunReport` is the durable result model. Existing legacy
results can be normalized:

```python
from medallantic import adapt_run_result

report = adapt_run_result(legacy_result)
print(report.to_dict())
```

Use `report_to_sparkforge_explain()` only for migration-facing presentation.
Unknown legacy statuses fail closed. Report adaptation redacts common secret
patterns, but callers must never put credentials or source rows in result
metadata.
