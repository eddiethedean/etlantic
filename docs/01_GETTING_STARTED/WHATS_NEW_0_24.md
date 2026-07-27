# What's New in ETLantic 0.24

ETLantic **0.24.0** makes pipelines fully authorable without class declarations
and introduces lossless `etlantic.pipeline/1` JSON.

## Highlights

- Canonical immutable `PipelineDefinition` shared by classes, functional
  builders, JSON, and visual editors (`etlantic.authoring`)
- Wire codec `etlantic.pipeline/1` with fingerprints, JSON Schema, and Safe I/O
- Functional builders: `pipeline_definition`, `extract_node`, `step_node`,
  `load_node`, `connect`, …
- Lifecycle accepts definitions: validate, plan, run, inspect, generate, viz
- CLI TARGET may be a pipeline JSON file; `etlantic generate --kind definition`
- Authoring catalog, immutable `EditCommand`s, and plan/validate previews
- Transport-neutral `etlantic.service.AuthoringService`
- Optional `etlantic-fastapi` reference adapter (not the 1.1 control plane)

## Not in 0.24

- Production GUI / multi-tenant control plane
- Replacing `etlantic.plan/1` (still the resolved execution IR)
- FastAPI as a core dependency

## Try it (10 lines)

```bash
# from a checkout with 0.24 installed
uv run python examples/pipeline_definition_json.py
python -m etlantic validate pipeline.definition.json --profile development
```

Or from a class:

```bash
python -m etlantic generate examples/memory_customers.py:CustomerPipeline \
  --kind definition -o pipeline.json
```

Full guide: [Programmatic authoring](../05_PIPELINES/PROGRAMMATIC_AUTHORING.md).
