"""Package import smoke tests."""

import etlantic


def test_version() -> None:
    assert etlantic.__version__ == "0.11.0"


def test_root_exports() -> None:
    assert hasattr(etlantic, "Pipeline")
    assert hasattr(etlantic, "Transformation")
    assert hasattr(etlantic, "Data")
    assert hasattr(etlantic, "Input")
    assert hasattr(etlantic, "Output")
    assert hasattr(etlantic, "Parameter")
    assert hasattr(etlantic, "Source")
    assert hasattr(etlantic, "Sink")
    assert hasattr(etlantic, "OutputRef")
    assert hasattr(etlantic, "PipelinePlan")
    assert hasattr(etlantic, "PipelineRunReport")
    assert hasattr(etlantic, "PipelineRuntime")
    assert hasattr(etlantic, "RunRequest")
    assert hasattr(etlantic, "SecretRef")
    assert hasattr(etlantic, "SecretValue")
    assert hasattr(etlantic, "Profile")
    assert hasattr(etlantic, "ContractBundle")
    assert hasattr(etlantic, "load_bundle")
    assert hasattr(etlantic, "write_contracts")
    assert hasattr(etlantic, "load_data_contract")
    assert hasattr(etlantic, "diff_data_contracts")
    assert hasattr(etlantic, "RelationRef")
    assert hasattr(etlantic, "discover_sql_plugins")
    assert hasattr(etlantic, "SQL_PROTOCOL_VERSION")
    assert hasattr(etlantic, "SPARK_PROTOCOL_VERSION")
    assert hasattr(etlantic, "STREAMING_STABILITY")
    assert hasattr(etlantic, "discover_spark_plugins")
    assert hasattr(etlantic, "DatasetRef")
    assert hasattr(etlantic, "ORCHESTRATION_PROTOCOL_VERSION")
    assert hasattr(etlantic, "compile_plan")
    assert hasattr(etlantic, "discover_orchestrator_plugins")
    assert hasattr(etlantic, "col")
    assert hasattr(etlantic, "concat")
    assert hasattr(etlantic, "select")
    assert hasattr(etlantic.Pipeline, "run")
    assert hasattr(etlantic.Pipeline, "arun")
    assert hasattr(etlantic.Pipeline, "debug")
