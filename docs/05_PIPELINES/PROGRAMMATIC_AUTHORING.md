# Programmatic Authoring (0.24)

Author pipelines with immutable builders or JSON — no class declarations
required. Class authoring remains fully supported and normalizes to the same
`PipelineDefinition`.

```python
import etlantic as etl

defn = etl.authoring.pipeline_definition(
    "demo:pipeline",
    "Demo",
    contracts=(...),
    transformations=(...),
    nodes=(...),
    edges=(...),
)
text = etl.authoring.pipeline_to_json(defn)
loaded = etl.authoring.pipeline_from_json(text)
etl.authoring.validate_pipeline_like(loaded, profile="development")
plan = etl.authoring.plan_pipeline_like(loaded, profile="development")
```

From an existing class:

```python
defn = etl.authoring.definition_from_pipeline(MyPipeline)
etl.authoring.write_pipeline_json(defn, "pipeline.json")
```

CLI:

```bash
etlantic generate module:MyPipeline --kind definition -o pipeline.json
etlantic validate pipeline.json
etlantic plan pipeline.json
```

See [Exit gate 0.24](../11_DEVELOPMENT/EXIT_GATE_0_24.md) and the
[0.24 plan](../11_DEVELOPMENT/PROGRAMMATIC_AUTHORING_0_24.md).
