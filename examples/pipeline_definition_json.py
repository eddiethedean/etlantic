"""Build a PipelineDefinition, write JSON, validate, and plan.

Run from a repository checkout:

    uv run python examples/pipeline_definition_json.py
"""

from __future__ import annotations

from pathlib import Path

import etlantic as etl

raw_id = "demo:RawCustomer"
cust_id = "demo:Customer"
xf_id = "demo:Normalize"
pid = "demo:CustomerPipeline"


def build_definition():
    return etl.authoring.pipeline_definition(
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


def main() -> None:
    defn = build_definition()
    out = Path("pipeline.definition.json")
    written = etl.authoring.write_pipeline_json(defn, out)
    loaded = etl.authoring.read_pipeline_json(written)
    assert loaded.fingerprint == defn.fingerprint
    report = etl.authoring.validate_pipeline_like(loaded, profile="development")
    report.raise_for_errors()
    plan = etl.authoring.plan_pipeline_like(loaded, profile="development")
    print(f"wrote {written}")
    print(f"fingerprint={loaded.fingerprint}")
    print(f"plan_pipeline_id={plan.pipeline_id}")
    print("ok")


if __name__ == "__main__":
    main()
