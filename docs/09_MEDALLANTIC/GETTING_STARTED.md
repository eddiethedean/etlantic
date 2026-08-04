# Getting started

## Install matching versions

Medallantic and ETLantic use matching minor versions:

```bash
python -m pip install \
  'etlantic==0.44.0' \
  'medallantic==0.44.0'
```

The ETLantic extra is equivalent:

```bash
python -m pip install 'etlantic[medallantic]==0.44.0'
```

Execution engines remain optional. Add only the plugins required by the target
profile.

## Build a pipeline

```python
from medallantic import MedallionBuilder

builder = (
    MedallionBuilder("orders", schema="analytics", engine="local")
    .bronze(
        "raw_orders",
        asset="bronze_orders",
        rules={"order_id": ["not_null"]},
    )
    .silver(
        "clean_orders",
        source="raw_orders",
        asset="silver_orders",
        transform_ref="my_project.transforms:clean_orders",
    )
    .gold(
        "daily_sales",
        source="clean_orders",
        asset="gold_daily_sales",
        transform_ref="my_project.transforms:daily_sales",
        write_mode="merge",
    )
)
```

`transform_ref` accepts an importable `module:attribute` reference. Keep
executable references out of serialized plans; ETLantic resolves execution
through its authorized runtime boundary.

## Lower, validate, and plan

```python
from etlantic.authoring import plan_pipeline_like, validate_pipeline_like

lowered = builder.lower()
definition = builder.build()

report = validate_pipeline_like(definition, profile=lowered.profile)
report.raise_for_errors()

plan = plan_pipeline_like(definition, profile=lowered.profile)
print(plan.plan_id)
```

`lowered` also exposes layer assignments, write intents, diagnostics, and the
generated ETLantic pipeline class.

## Inspect before execution

```python
print(lowered.layer_by_node)
print(lowered.write_intents)
print([item.code for item in lowered.diagnostics])
```

Production profiles must explicitly allowlist every trusted execution plugin.
Validation and planning must succeed before any write.

## Next

- [Native authoring](AUTHORING.md)
- [Quality rules](QUALITY.md)
- [Execution and reports](EXECUTION.md)
- [Compatibility](COMPATIBILITY.md)
