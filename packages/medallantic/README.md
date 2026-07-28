# Medallantic

Engine-agnostic medallion pipelines built on ETLantic.

Medallantic owns bronze/silver/gold authoring and conventions. ETLantic owns
the portable contracts, graph, validation, planning, execution lifecycle, and
plugin coordination underneath it. **ETLantic core never gains medallion
types.**

The current release is the renamed SparkForge migration adapter. It maps
SparkForge IR onto ordinary ETLantic `Extract` / `Step` / `Load`, `Profile`,
`RunSelection` / `RunIntent`, and `PipelineRunReport` surfaces. A native
engine-agnostic builder and live Spark/SQL parity are planned; see the
[roadmap](ROADMAP.md).

Documentation:

- [Documentation index](docs/README.md)
- [Getting started](docs/getting-started.md)
- [SparkForge migration](docs/sparkforge-migration.md)
- [Compatibility](docs/compatibility.md)
- [Architecture](docs/architecture.md)

## Install

```bash
pip install 'etlantic==0.27.0' 'medallantic==0.27.0'
# or
pip install 'etlantic[medallantic]'
```

The shipped adapter is **IR-only**: feed `SparkForgePipelineSpec` (JSON/YAML
fixtures or hand-built dataclasses). There is **no** live
`pipeline_builder` / SparkForge Python API bridge in this release.

The adapter is registered explicitly by importing `medallantic` and
calling its conversion helpers. The adapted result supplies an ordinary
ETLantic pipeline and profile; select execution plugins such as
`Profile.spark_engine="pyspark"` separately. Production profiles must
allowlist every trusted execution plugin.

## Quick start (IR → Pipeline)

```python
from medallantic import (
    SparkForgePipelineSpec,
    SparkForgeStepSpec,
    StepKind,
    LayerKind,
    adapt_pipeline,
    debug_request_from_sparkforge,
    enrich_plan,
)
from etlantic.plan import plan_pipeline

spec = SparkForgePipelineSpec(
    name="ecommerce",
    schema="demo",
    steps=(
        SparkForgeStepSpec(
            name="orders",
            kind=StepKind.BRONZE_RULES,
            layer=LayerKind.BRONZE,
            table_name="bronze_orders",
        ),
        SparkForgeStepSpec(
            name="clean_orders",
            kind=StepKind.SILVER_TRANSFORM,
            layer=LayerKind.SILVER,
            source="orders",
            table_name="silver_orders",
            write_mode="overwrite",
        ),
    ),
)
adapted = adapt_pipeline(spec)
adapted.pipeline_cls.validate(profile=adapted.profile)
plan = enrich_plan(
    plan_pipeline(adapted.pipeline_cls, profile=adapted.profile),
    adapted,
)
request = debug_request_from_sparkforge(mode="incremental", skip_writes=True)
```

## Delivery direction

1. **Plan-only** — generate/inspect ETLantic plans from SparkForge IR
   (`strict_delta=False` to warn instead of fail when Delta caps are unknown)
2. **Dual reporting** — `adapt_run_result` → `PipelineRunReport`
3. **ETLantic planning** — selections/intents via `debug_request_from_sparkforge`
4. **Plugin execution** — `Profile.spark_engine="pyspark"` / SQL plugins
5. **Native facade** — Medallantic owns medallion authoring and retires the
   duplicated legacy engine-specific builders

`transform_ref` / bronze `rules` emit `PMSF411` warnings: the adapter builds
passthrough transforms for planning parity; it does not execute SparkForge
callables. Write intents (including MERGE) are attached via `enrich_plan` for
orchestration; the local runtime still gates materialization with
`RunRequest.no_write`.

See `docs/11_DEVELOPMENT/MIGRATION_0_9_TO_0_10.md`.

## Boundary

| Concern | Owner |
|---|---|
| bronze / silver / gold APIs | Medallantic |
| portable graph, plan, reports | ETLantic |
| legacy mapping + parity fixtures | Medallantic migration layer |
| physical execution | ETLantic engine and storage plugins |
