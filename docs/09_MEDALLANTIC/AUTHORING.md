# Native authoring

Medallantic provides class-style and fluent-builder authoring. Both lower to
the same public ETLantic definition and must preserve the same graph meaning.

## Fluent builder

```python
from medallantic import MedallionBuilder

definition = (
    MedallionBuilder("customers", schema="analytics")
    .bronze("raw", asset="bronze_customers")
    .silver("clean", source="raw", asset="silver_customers")
    .gold(
        "segments",
        source="clean",
        asset="gold_customer_segments",
        write_mode="overwrite",
    )
    .build()
)
```

Use `.to_document()` for the facade-owned document, `.lower()` for the complete
lowering result, `.build()` for a sealed `PipelineDefinition`, or
`.as_pipeline()` for a generated `MedallionPipeline` subclass.

## Class-style authoring

```python
from medallantic import Bronze, Gold, MedallionPipeline, Silver


class Customers(MedallionPipeline):
    __medallion_name__ = "customers"
    __medallion_schema__ = "analytics"
    __medallion_engine__ = "local"

    raw = Bronze(
        asset="bronze_customers",
        rules={"customer_id": ["not_null"]},
    )
    clean = Silver(
        source="raw",
        asset="silver_customers",
        transform_ref="my_project.transforms:clean_customers",
    )
    segments = Gold(
        source="clean",
        asset="gold_customer_segments",
    )


definition = Customers.to_definition()
lowered = Customers.lower()
```

## Layer behavior

| Layer | Lowered role | Default lifecycle intent |
|---|---|---|
| Bronze | Extract and optional quality gate | Preserve |
| Silver | Transformation and optional load | Refresh |
| Gold | Transformation and publication load | Publish |

Defaults are Medallantic policy expressed through domain-neutral ETLantic
intents. They do not add medallion fields to ETLantic core schemas.

## Dependencies and branching

`source` names the upstream step. Multiple bronze roots and branches are
supported. Cycles, duplicate names, and unknown sources fail with structured
`MDL*` diagnostics; declaration order never repairs an invalid graph.

Use `source="step.port"` when a named output port is required.

## Writes

Supported portable intents include `append`, `overwrite`, `merge`, `upsert`,
and `no_write`. Backend support is still capability-driven. Medallantic never
approximates an unsupported write with a different mode.

