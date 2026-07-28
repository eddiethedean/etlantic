# Medallantic

Engine-agnostic **medallion facade** on ETLantic: native bronze/silver/gold
authoring plus a SparkForge IR migrate path. Prefer `medallantic` over the
deprecated `etlantic-sparkforge` redirect.

Medallantic owns bronze/silver/gold authoring conventions; ETLantic owns
the portable contracts, graph, validation, planning, execution lifecycle, and
plugin coordination underneath it. **ETLantic core never gains medallion
types.**

**0.29 (M1)** ships `MedallionPipeline`, `MedallionBuilder`, `Bronze` /
`Silver` / `Gold`, and `medallantic.migrate.sparkforge`. **0.30 (M2)** enforces
portable `rules=` via `etlantic.quality/1` gates (Polars/Pandas/local live;
SQL/PySpark fail-closed). Transform callables remain **0.31**.

Documentation:

- [Documentation index](docs/README.md)
- [Getting started](docs/getting-started.md)
- [SparkForge migration](docs/sparkforge-migration.md)
- [Compatibility](docs/compatibility.md)
- [Architecture](docs/architecture.md)

## Install

```bash
pip install 'etlantic==0.30.0' 'medallantic==0.30.0'
# or
pip install 'etlantic[medallantic]'
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

## SparkForge IR migrate

Feed `SparkForgePipelineSpec` (JSON/YAML fixtures or hand-built dataclasses)
via `adapt_pipeline` or `medallantic.migrate.sparkforge`. There is **no** live
`pipeline_builder` / SparkForge Python API bridge in this release.

The adapted result supplies an ordinary ETLantic pipeline and profile; select
execution plugins such as `Profile.spark_engine="pyspark"` separately.
Production profiles must allowlist every trusted execution plugin.
