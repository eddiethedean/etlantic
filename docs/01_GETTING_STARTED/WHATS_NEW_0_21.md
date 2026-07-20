# What's New in 0.21

ETLantic **0.21.0** delivers a cohesive CLI and authoring experience: one
documented journey from project scaffold through durable local runs.

## Cohesive CLI journey

```bash
etlantic init
etlantic doctor --profile development
etlantic validate pipeline.py:SamplePipeline --profile development
etlantic plan pipeline.py:SamplePipeline --profile development
etlantic run pipeline.py:SamplePipeline --profile development
etlantic report list
etlantic report show <run_id>
```

No Python-side `runtime.memory.seed()` is required when profiles declare
file-backed assets (for example `json://data/sample.json`).

## New commands

| Command | Purpose |
|---|---|
| `etlantic init` | Scaffold pipeline, profile, sample data, workspace |
| `etlantic doctor` | Read-only environment, plugin, profile, workspace checks |
| `etlantic profile validate/show/diff/migrate` | Profile lifecycle |
| `etlantic plan diff` | Structural plan comparison |
| `etlantic report list` | List durable reports |

## Durable workspace

By default the CLI writes run reports to `.etlantic/reports/` and uses
`.etlantic/artifacts/` for durable materialization. Pass `--ephemeral` for
process-local behavior (0.20 default).

## Project configuration

Optional `etlantic.toml` sets `default_profile`. When absent, profiles resolve
from `profiles/{name}.json`, built-in templates, or JSON paths.

## Breaking changes

- Legacy profile JSON `bindings` keys fail closed unless
  `--accept-legacy-bindings` (use `etlantic profile migrate`).
- Production profiles enforce strict metadata extension namespaces.

See [Migration 0.20 → 0.21](../11_DEVELOPMENT/MIGRATION_0_20_TO_0_21.md).
