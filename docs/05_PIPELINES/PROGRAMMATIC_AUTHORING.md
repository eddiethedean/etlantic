# Programmatic Authoring

> **Status: Available in ETLantic 0.36.0** (introduced in 0.24).

Author pipelines with immutable builders or JSON — no class declarations
required. Class authoring remains fully supported and normalizes to the same
`PipelineDefinition` (`etlantic.pipeline/1`).

After `pip install 'etlantic==0.36.0'`, you can build, write JSON, and validate
with no repository checkout.

```text
Class  ──┐
Builders ┼──▶ PipelineDefinition ──▶ validate / plan ──▶ PipelinePlan
JSON   ──┘     (etlantic.pipeline/1)                    (etlantic.plan/1)
```

Plan JSON is **not** interchangeable with definition JSON.

## Pip-only: build → JSON → validate

```python
import etlantic as etl

raw_id = "demo:Row"
pid = "demo:Sample"

defn = etl.authoring.pipeline_definition(
    pid,
    "Sample",
    contracts=(
        etl.authoring.contract_definition(
            raw_id,
            "Row",
            fields=(
                etl.authoring.field_spec("id", "integer"),
                etl.authoring.field_spec("name", "string"),
            ),
        ),
    ),
    nodes=(
        etl.authoring.extract_node(
            "rows", asset="rows", contract_id=raw_id, pipeline_id=pid
        ),
        etl.authoring.load_node(
            "out", asset="out", contract_id=raw_id, pipeline_id=pid
        ),
    ),
    edges=(
        etl.authoring.edge(
            "rows",
            "result",
            "out",
            "input",
            producer_contract_id=raw_id,
            consumer_contract_id=raw_id,
        ),
    ),
)
etl.authoring.write_pipeline_json(defn, "pipeline.json")
```

```bash
python -m etlantic validate pipeline.json --profile development
python -m etlantic plan pipeline.json --profile development --format json
```

Optional from a checkout: `uv run python examples/pipeline_definition_json.py`.

## Expected output

The checkout companion writes a definition, round-trips it, validates it, and
plans it. The fingerprint is deterministic for a given definition:

```text
wrote pipeline.definition.json
fingerprint=<64-character sha256>
plan_pipeline_id=demo:CustomerPipeline
ok
```

For the CLI commands above, `validate` must exit zero before the JSON plan is
used. Machine-readable plan output includes
`"pipeline_id": "demo:Sample"` and `"schema": "etlantic.plan/1"`.

## End-to-end with a transform step

```python
import etlantic as etl

raw_id = "demo:RawCustomer"
cust_id = "demo:Customer"
xf_id = "demo:Normalize"
pid = "demo:CustomerPipeline"

defn = etl.authoring.pipeline_definition(
    pid,
    "CustomerPipeline",
    contracts=(
        etl.authoring.contract_definition(
            raw_id,
            "RawCustomer",
            fields=(
                etl.authoring.field_spec("customer_id", "integer"),
                etl.authoring.field_spec("first_name", "string"),
                etl.authoring.field_spec("last_name", "string"),
            ),
        ),
        etl.authoring.contract_definition(
            cust_id,
            "Customer",
            fields=(
                etl.authoring.field_spec("customer_id", "integer"),
                etl.authoring.field_spec("full_name", "string"),
            ),
        ),
    ),
    transformations=(
        etl.authoring.transformation_definition(
            xf_id,
            "NormalizeCustomers",
            ports=(
                etl.authoring.input_port("customers", raw_id),
                etl.authoring.output_port("result", cust_id),
            ),
            implementation_refs=(
                etl.authoring.implementation_ref("local", f"{xf_id}/local"),
            ),
        ),
    ),
    nodes=(
        etl.authoring.extract_node(
            "raw", asset="customer_source", contract_id=raw_id, pipeline_id=pid
        ),
        etl.authoring.step_node(
            "normalized",
            transformation_id=xf_id,
            transformation_name="NormalizeCustomers",
            pipeline_id=pid,
            inputs=(etl.authoring.input_port("customers", raw_id),),
            outputs=(etl.authoring.output_port("result", cust_id),),
        ),
        etl.authoring.load_node(
            "curated", asset="customer_sink", contract_id=cust_id, pipeline_id=pid
        ),
    ),
    edges=(
        etl.authoring.edge(
            "raw",
            "result",
            "normalized",
            "customers",
            producer_contract_id=raw_id,
            consumer_contract_id=raw_id,
        ),
        etl.authoring.edge(
            "normalized",
            "result",
            "curated",
            "input",
            producer_contract_id=cust_id,
            consumer_contract_id=cust_id,
        ),
    ),
)

text = etl.authoring.pipeline_to_json(defn)
etl.authoring.write_pipeline_json(defn, "pipeline.json")
loaded = etl.authoring.pipeline_from_json(text)
assert loaded.fingerprint == defn.fingerprint

report = etl.authoring.validate_pipeline_like(loaded, profile="development")
report.raise_for_errors()
plan = etl.authoring.plan_pipeline_like(loaded, profile="development")
```

## From an existing class

```python
import etlantic as etl

# From an init project or any Pipeline subclass in your app:
# from pipeline import SamplePipeline
# defn = etl.authoring.definition_from_pipeline(SamplePipeline)
# etl.authoring.write_pipeline_json(defn, "pipeline.json")
```

From a repository checkout you can also normalize
`examples/memory_customers.py:CustomerPipeline`.

## Callable registry (required to run definitions)

JSON and builders store **implementation refs**, not live callables. Before
`run`, register the function for each transformation/engine:

```python
etl.authoring.callable_registry().register(
    "demo:Normalize",  # transformation identity
    "local",
    normalize_fn,
)
```

Class-authored pipelines continue to resolve implementations from decorators
without this step.

## CLI

TARGET may be `module:Class`, `path.py:Class`, **or** a pipeline JSON file:

```bash
python -m etlantic generate pipeline.py:SamplePipeline \
  --kind definition -o pipeline.json
python -m etlantic validate pipeline.json --profile development
python -m etlantic plan pipeline.json --profile development
# run needs callables registered in-process (SDK) or a class target
```

See [CLI reference](../10_REFERENCE/CLI.md#pipeline-targets).

## What is not a definition

| Artifact | Role |
|---|---|
| `PipelineDefinition` / `etlantic.pipeline/1` | Authoring-complete, unresolved document |
| `PipelinePlan` / `etlantic.plan/1` | Resolved execution IR (secret-free) |
| Class `Pipeline` | Python authoring that normalizes to a definition |

Do not treat plan JSON as interchangeable with definition JSON.

## Related

- [Application integration](../08_VISUALIZATION/APPLICATION_INTEGRATION.md) — service + FastAPI
- [API — Authoring](../10_REFERENCE/API_AUTHORING.md) — mkdocstrings for `etlantic.authoring`
- [Cheatsheet](../10_REFERENCE/CHEATSHEET.md)
- [Troubleshooting](../01_GETTING_STARTED/TROUBLESHOOTING.md#json-pipelinedefinition-authoring) — fingerprints, schema, registry
- Exit-gate record (historical): [EXIT_GATE_0_24](../11_DEVELOPMENT/EXIT_GATE_0_24.md)
- Design plan (historical): [PROGRAMMATIC_AUTHORING_0_24](../11_DEVELOPMENT/PROGRAMMATIC_AUTHORING_0_24.md)
