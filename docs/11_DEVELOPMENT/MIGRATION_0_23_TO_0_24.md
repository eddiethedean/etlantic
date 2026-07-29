# Migration 0.23 → 0.24

## Compatible by default

Class authoring (`Pipeline` / `Transformation` / `Extract` / `Load`) is unchanged.
Existing `etlantic.plan/1` and run-report codecs remain valid.

## New recommended surfaces

```python
import etlantic as etl

defn = etl.authoring.definition_from_pipeline(MyPipeline)
text = etl.authoring.pipeline_to_json(defn)
loaded = etl.authoring.pipeline_from_json(text)
etl.authoring.validate_pipeline_like(loaded, profile="development")
```

CLI:

```bash
etlantic generate module:MyPipeline --kind definition -o pipeline.json
etlantic validate pipeline.json --profile development
etlantic plan pipeline.json --profile development
```

## Behavioral notes

- JSON deserialization is inert: no imports, plugin loads, or secret resolution.
- Native implementations are host-registered (`callable_registry`) or harvested
  from classes before run.
- [DPCS](../05_PIPELINES/DPCS.md) remains standards interchange and may still generate classes; it is not
  the lossless authoring codec (`etlantic.pipeline/1` is).

## Optional package

```bash
pip install etlantic-fastapi==0.24.0
```
