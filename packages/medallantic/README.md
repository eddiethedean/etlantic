# Medallantic

Engine-agnostic **medallion facade** on ETLantic: native bronze/silver/gold
authoring plus a SparkForge IR migrate path. Prefer `medallantic` over the
deprecated `etlantic-sparkforge` redirect.

Medallantic owns bronze/silver/gold authoring conventions; ETLantic owns
the portable contracts, graph, validation, planning, execution lifecycle, and
plugin coordination underneath it. **ETLantic core never gains medallion
types.**

The current **0.46** line includes native authoring, portable quality
gates, importable transform execution, lifecycle/write semantics, PySpark and
Delta differential coverage, SQLAlchemy relational parity, observability
providers, durable run history, event consumers, production conformance, and
the completed M7 migration plus joint compatibility burn-in.
Native PySpark Column and Moltres rules remain explicitly capability-gated.

Documentation:

- [Documentation index](https://github.com/eddiethedean/etlantic/blob/main/packages/medallantic/docs/README.md)
- [Getting started](https://github.com/eddiethedean/etlantic/blob/main/packages/medallantic/docs/getting-started.md)
- [SparkForge migration](https://github.com/eddiethedean/etlantic/blob/main/packages/medallantic/docs/sparkforge-migration.md)
- [Compatibility](https://github.com/eddiethedean/etlantic/blob/main/packages/medallantic/docs/compatibility.md)
- [Architecture](https://github.com/eddiethedean/etlantic/blob/main/packages/medallantic/docs/architecture.md)

## Install

```bash
pip install medallantic
```

## Native authoring

```python
from medallantic import MedallionBuilder

defn = (
    MedallionBuilder("ecommerce", schema="demo")
    .bronze("orders", asset="bronze_orders")
    .silver("clean", source="orders", asset="silver_orders")
    .gold("kpis", source="clean", asset="gold_kpis", write_mode="merge")
    .build()
)
```

## Migration bridges

Feed `SparkForgePipelineSpec` (JSON/YAML fixtures or hand-built dataclasses)
via `adapt_pipeline` or `medallantic.migrate.sparkforge`. Existing live
builders can use:

```python
from medallantic.migrate.sparkforge import from_pipeline_builder
from medallantic.migrate.sql import from_sql_pipeline_builder
```

The adapted result supplies an ordinary ETLantic pipeline and profile; select
execution plugins such as `Profile.spark_engine="pyspark"` separately.
Production profiles must allowlist every trusted execution plugin.

## Links

[Documentation](https://github.com/eddiethedean/etlantic/tree/main/packages/medallantic/docs) ·
[Source](https://github.com/eddiethedean/etlantic/tree/main/packages/medallantic) ·
[Issues](https://github.com/eddiethedean/etlantic/issues)
