# Medallantic (runnable migration adapter)

> **Status: Available.** The current release provides the SparkForge IR
> migration adapter and parity suite under `tests/medallantic/`.

Map medallion SparkForge IR onto ordinary ETLantic `Extract` / `Step` /
`Load` graphs without putting bronze/silver/gold types in core.

## Setup

```bash
git clone https://github.com/eddiethedean/etlantic.git
cd etlantic
uv sync --group medallantic
```

## Run the parity suite

```bash
uv run pytest -q tests/medallantic -m medallantic
```

## Minimal adapt

```python
import json
from pathlib import Path

from etlantic.plan import plan_pipeline
from medallantic import (
    SparkForgePipelineSpec,
    adapt_pipeline,
    debug_request_from_sparkforge,
    enrich_plan,
)

data = json.loads(
    Path("tests/medallantic/fixtures/ecommerce.json").read_text(encoding="utf-8")
)
spec = SparkForgePipelineSpec.from_dict(data)
adapted = adapt_pipeline(spec)
adapted.pipeline_cls.validate(profile=adapted.profile).raise_for_errors()
plan = enrich_plan(
    plan_pipeline(adapted.pipeline_cls, profile=adapted.profile),
    adapted,
)
request = debug_request_from_sparkforge(mode="incremental", skip_writes=True)
print(adapted.pipeline_cls.__name__, plan.plan_id, request.intent)
```

## Boundary

- Layer names stay in adapter metadata (`layer_by_node`), not core enums
- Transforms may be passthrough for planning parity (`PMSF411` warnings)
- MERGE write intents are for plan/orchestration via `enrich_plan`; local
  runtime still gates writes with `RunRequest.no_write`

## See also

- Package README: `packages/medallantic/README.md`
- [Migration 0.9 → 0.10](../11_DEVELOPMENT/MIGRATION_0_9_TO_0_10.md)
- [SparkForge Feature Adoption](../11_DEVELOPMENT/SPARKFORGE_ADOPTION.md)
