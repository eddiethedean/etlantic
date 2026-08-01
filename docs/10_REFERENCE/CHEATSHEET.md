# CLI and SDK cheatsheet

> **Status: Available in ETLantic 0.41.0.** Day-0 reminders only—see
> [CLI](CLI.md) and [API Reference](API_REFERENCE.md) for full detail.

Prefer `python -m etlantic` and `import etlantic as etl`.

## CLI verbs

| Command | Purpose |
|---|---|
| `init` | Scaffold empty-dir project (`--force` if needed) |
| `doctor` | Environment / plugin / profile checks |
| `profile` | List / show / write profiles |
| `validate TARGET` | Validate without executing transforms |
| `inspect TARGET` | Print logical graph |
| `plan TARGET` | Emit secret-free `PipelinePlan` |
| `plan explain` | Human/JSON plan explanation |
| `plan diff` | Diff two plans / targets |
| `run TARGET` | Execute in-process |
| `compile TARGET` | Compile (e.g. Airflow; needs plugin) |
| `generate TARGET` | Contracts, or `--kind definition` JSON |
| `diff` | Diff contracts / pipelines |
| `plugin` | List / info / compatibility |
| `schema` | Schema history (fingerprints only) |
| `reliability` | Reliability helpers |
| `viz` | Diagrams |
| `report` | Durable run reports |

`TARGET` = `module:Class`, `path.py:Class`, or `pipeline.json`
(`etlantic.pipeline/1`).

```bash
python -m etlantic validate pipeline.py:SamplePipeline --profile development
python -m etlantic generate module:MyPipeline --kind definition -o pipeline.json
python -m etlantic validate pipeline.json --profile development --format json
```

## SDK namespaces

```python
import etlantic as etl

etl.Pipeline / etl.Transformation / etl.Data   # curated root
etl.authoring   # PipelineDefinition, builders, JSON, catalog, edits
etl.service     # AuthoringService, PolicyContext
etl.transform   # portable authoring helpers
etl.dataframe / etl.sql / etl.spark
etl.orchestration / etl.viz / etl.secrets / etl.testing / etl.quality
```

Minimal definition path:

```python
defn = etl.authoring.definition_from_pipeline(MyPipeline)
etl.authoring.write_pipeline_json(defn, "pipeline.json")
etl.authoring.validate_pipeline_like(defn, profile="development")
```

## Related

- [Programmatic authoring](../05_PIPELINES/PROGRAMMATIC_AUTHORING.md)
- [Quickstart](../01_GETTING_STARTED/QUICKSTART.md)
- [Application integration](../08_VISUALIZATION/APPLICATION_INTEGRATION.md)
