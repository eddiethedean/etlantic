# Getting started

## Requirements

- Python 3.11 or newer
- Matching Medallantic and ETLantic minor versions

Install the current release:

```bash
python -m pip install \
  'etlantic==0.35.0' \
  'medallantic==0.35.0'
```

The equivalent ETLantic extra is:

```bash
python -m pip install 'etlantic[medallantic]==0.35.0'
```

Execution engines remain optional. Install the engine separately when moving
beyond plan-only workflows, for example `etlantic-pyspark` or `etlantic-sql`.

## Define a migration specification

```python
from medallantic import (
    LayerKind,
    SparkForgePipelineSpec,
    SparkForgeStepSpec,
    StepKind,
)

spec = SparkForgePipelineSpec(
    name="orders",
    schema="analytics",
    engine="spark",
    min_bronze_rate=90.0,
    min_silver_rate=97.0,
    min_gold_rate=99.0,
    steps=(
        SparkForgeStepSpec(
            name="raw_orders",
            kind=StepKind.BRONZE_RULES,
            layer=LayerKind.BRONZE,
            table_name="raw.orders",
            rules={"order_id": ["not_null"]},
        ),
        SparkForgeStepSpec(
            name="clean_orders",
            kind=StepKind.SILVER_TRANSFORM,
            layer=LayerKind.SILVER,
            source="raw_orders",
            table_name="analytics.clean_orders",
            transform_ref="clean_orders_fn",
            write_mode="overwrite",
        ),
        SparkForgeStepSpec(
            name="order_metrics",
            kind=StepKind.GOLD_TRANSFORM,
            layer=LayerKind.GOLD,
            source="clean_orders",
            table_name="analytics.order_metrics",
            transform_ref="order_metrics_fn",
            write_mode="merge",
            metadata={"merge_keys": ["metric_date"]},
        ),
    ),
)
```

The IR must not contain credentials, resolved secrets, data rows, sessions,
dataframes, or executable callables.

## Adapt and validate

```python
from medallantic import adapt_pipeline

adapted = adapt_pipeline(spec)
report = adapted.pipeline_cls.validate(profile=adapted.profile)

if not report.valid:
    raise RuntimeError(report.to_dict())
```

`adapt_pipeline` fails closed with `AdapterError` for invalid graphs, unknown
write modes, unsupported step kinds, or unmet strict Delta requirements.

Inspect adapter-specific information:

```python
print(adapted.layer_by_node)
print(adapted.write_intents)
print([diagnostic.code for diagnostic in adapted.diagnostics])
```

## Create an enriched plan

```python
from etlantic.plan import plan_pipeline

plan = plan_pipeline(adapted.pipeline_cls, profile=adapted.profile)
plan = adapted.enrich_plan(plan)

print(plan.plan_id)
print(plan.intents["write_intents"])
```

Enrichment records intended writes for orchestration and inspection. It does
not itself execute the pipeline. Importable `module:attribute`
`transform_ref` values execute through ETLantic; symbolic names remain
planning-only passthroughs with `MDL111`.

## Plan-only Delta inspection

Strict adaptation rejects Delta operations unless matching plugin capabilities
are supplied. For non-executing migration analysis, warnings can be requested:

```python
adapted = adapt_pipeline(spec, strict_delta=False)
```

Never use `strict_delta=False` as proof that an execution environment supports
Delta. Validate the actual selected plugin capabilities before mutation.

## Next steps

- Read [SparkForge migration](sparkforge-migration.md) for JSON IR conversion.
- Read [Runtime and reports](runtime-and-reports.md) for run-request mappings.
- Review [Compatibility](compatibility.md) before expecting execution parity.
