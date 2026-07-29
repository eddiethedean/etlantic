# SparkForge migration

The current Medallantic release provides a SparkForge-independent IR adapter.
It is intended for inventory, graph comparison, plan inspection, and gradual
migration.

## JSON input

A minimal JSON document looks like:

```json
{
  "name": "customers",
  "schema": "analytics",
  "engine": "sql",
  "min_bronze_rate": 90.0,
  "min_silver_rate": 97.0,
  "min_gold_rate": 99.0,
  "steps": [
    {
      "name": "raw_customers",
      "kind": "bronze_rules",
      "layer": "bronze",
      "table_name": "raw.customers"
    },
    {
      "name": "clean_customers",
      "kind": "silver_transform",
      "layer": "silver",
      "source": "raw_customers",
      "table_name": "analytics.clean_customers",
      "write_mode": "overwrite"
    }
  ]
}
```

Parse with diagnostics before adaptation:

```python
import json
from pathlib import Path

from medallantic import SparkForgePipelineSpec, adapt_pipeline

payload = json.loads(Path("pipeline.json").read_text(encoding="utf-8"))
spec, parse_diagnostics = SparkForgePipelineSpec.parse(payload)

if any(item.severity.value == "error" for item in parse_diagnostics):
    raise ValueError([item.message for item in parse_diagnostics])

adapted = adapt_pipeline(spec)
```

## Dependency behavior

`source` fields determine edges. Declaration order is used only to provide
deterministic ordering among otherwise equivalent nodes.

Adaptation rejects:

- duplicate step names
- missing or unknown upstream sources
- dependency cycles
- empty pipelines
- unsupported step kinds
- unsupported write modes

Medallantic never removes an edge to make a cyclic graph executable.

## What maps today

- Bronze steps become ETLantic extracts.
- Silver and gold steps become typed transformations.
- Non-`no_write` silver/gold steps gain loads.
- Layer thresholds become named validation-policy metadata.
- Table names become profile assets.
- Write modes become ETLantic write intents.
- Merge keys are read from `metadata.merge_keys` or `metadata.keys`.
- Declared Delta operations are capability-checked.

## Transformation execution

An importable `transform_ref` in `module:attribute` or dotted form resolves to
an ETLantic transformation and executes on the supported local, Polars,
Pandas, or PySpark path. A symbolic legacy name such as `clean_orders_fn`
cannot be imported; it emits `MDL111` (or the migration alias `PMSF411`) and
uses a planning-only passthrough. An import-looking reference that cannot be
resolved is an error.

Portable `rules` lower to explicit quality gates. Native PySpark Column and
Moltres rules require their declared capabilities and fail closed on the wrong
engine. Production migration still requires differential testing against the
legacy pipeline.

## Live builder bridge

When SparkForge is installed, adapt an existing builder without first
serializing IR:

```python
from medallantic.migrate.sparkforge import from_pipeline_builder

adapted = from_pipeline_builder(pipeline_builder)
```

The bridge extracts a secret-free definition. It must not serialize sessions,
resolved credentials, dataframes, or source rows.

## Recommended migration workflow

1. Export a secret-free IR inventory from the legacy project.
2. Parse and resolve all structural diagnostics.
3. Adapt and compare dependency order and layer assignments.
4. Inspect profile assets, quality thresholds, and write intents.
5. Generate deterministic ETLantic plans.
6. Normalize existing run results for report comparison.
7. Convert transformations only when their target engine path is supported.
8. Run differential fixtures before changing production execution.

## Diagnostic stability

Existing `PMSF` codes identify the SparkForge migration boundary and remain
stable until a documented major-version migration. New native Medallantic APIs
will use Medallantic-specific diagnostic families.
