# SparkForge migration

Medallantic provides a SparkForge-independent, secret-free migration IR. Use it
to inventory, compare, validate, and incrementally replace legacy definitions
without importing SparkForge or PySpark during analysis.

## Parse and adapt

```python
import json
from pathlib import Path

from medallantic.migrate.sparkforge import SparkForgePipelineSpec, adapt_pipeline

payload = json.loads(Path("pipeline.json").read_text(encoding="utf-8"))
spec, diagnostics = SparkForgePipelineSpec.parse(payload)

if any(item.severity.value == "error" for item in diagnostics):
    raise ValueError([item.message for item in diagnostics])

adapted = adapt_pipeline(spec)
```

The IR must not contain credentials, resolved secrets, data rows, sessions,
dataframes, or executable objects.

## What maps

- bronze sources to ETLantic extracts
- silver/gold transformations to steps and optional loads
- dependencies to typed graph edges
- assets to profile assets
- write modes to `WriteIntent`
- run modes and selections to `RunRequest`
- quality thresholds and rules to portable policy/evidence
- legacy results to `PipelineRunReport`

## Safe migration sequence

1. Export a secret-free legacy inventory.
2. Resolve parse, duplicate, dependency, and cycle diagnostics.
3. Compare graph order, layers, assets, write intents, and quality policy.
4. Generate and fingerprint deterministic ETLantic plans.
5. Normalize historical reports for differential comparison.
6. Replace transformation references with importable, tested callables.
7. Run engine-specific differential fixtures.
8. Move production execution only after parity and rollback gates pass.

Medallantic never removes an edge, changes a write mode, or substitutes an
engine to make migration appear successful.

