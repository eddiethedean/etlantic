"""Package import smoke tests."""

import pipelantic


def test_version() -> None:
    assert pipelantic.__version__ == "0.4.0"


def test_root_exports() -> None:
    assert hasattr(pipelantic, "Pipeline")
    assert hasattr(pipelantic, "Transformation")
    assert hasattr(pipelantic, "Data")
    assert hasattr(pipelantic, "Input")
    assert hasattr(pipelantic, "Output")
    assert hasattr(pipelantic, "Parameter")
    assert hasattr(pipelantic, "Source")
    assert hasattr(pipelantic, "Sink")
    assert hasattr(pipelantic, "OutputRef")
    assert hasattr(pipelantic, "PipelinePlan")
    assert hasattr(pipelantic, "PipelineRunReport")
    assert hasattr(pipelantic, "PipelineRuntime")
    assert hasattr(pipelantic, "RunRequest")
    assert hasattr(pipelantic, "SecretRef")
    assert hasattr(pipelantic, "SecretValue")
    assert hasattr(pipelantic, "Profile")
    assert hasattr(pipelantic, "ContractBundle")
    assert hasattr(pipelantic, "load_bundle")
    assert hasattr(pipelantic, "write_contracts")
    assert hasattr(pipelantic, "load_data_contract")
    assert hasattr(pipelantic, "diff_data_contracts")
    assert hasattr(pipelantic.Pipeline, "run")
    assert hasattr(pipelantic.Pipeline, "arun")
    assert hasattr(pipelantic.Pipeline, "debug")
