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

## Adapt an installed builder

When SparkForge is installed and the builder is already available in memory,
use the explicit live bridge:

```python
from medallantic.migrate.sparkforge import from_pipeline_builder

adapted = from_pipeline_builder(pipeline_builder)
```

The bridge extracts the same secret-free migration representation. It does not
authorize plugins, resolve credentials, or prove backend parity by itself.

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

## Inventory and safe generation (0.35 / M7)

```bash
python -m medallantic migrate inventory PATH
python -m medallantic migrate generate path/to/pipeline.json
```

```python
from medallantic.migrate import scan_project, generate_from_path

report = scan_project("legacy-project/")
result = generate_from_path("pipeline.json")
```

Analysis is static and secret-free. Generated definitions stamp
`etlantic.definition_provenance` with generator id, source fingerprint, and
facade protocol version `1`. Manual conversion points emit `MDL210`;
unsupported paths emit `MDL220`.

## Deprecation timeline

Transitional SparkForge adapters (`medallantic.migrate.sparkforge` / `.sql`,
`etlantic-sparkforge`, live builder bridges) remain supported in 0.36 and are
**not** removed before a documented major release.
